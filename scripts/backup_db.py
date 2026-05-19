#!/usr/bin/env python
"""Nightly Postgres dump → R2, with pruning.

Invoked by `scripts/backup_db.sh` (which sources `.env` first). Reads
DATABASE_URL + R2 creds from env, runs `pg_dump -Fc` into a temp file,
uploads under `db-backups/<dbname>-YYYY-MM-DD.dump`, then deletes anything
older than KEEP_DAYS from the same prefix.

Restoration:
    pg_restore -h localhost -U baby -d babytracker --clean --if-exists <file>
"""
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import boto3

KEEP_DAYS = 30
PREFIX = "db-backups"


def main() -> int:
    db = urlparse(os.environ["DATABASE_URL"])
    db_name = db.path.lstrip("/")
    bucket = os.environ["AWS_STORAGE_BUCKET_NAME"]

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["AWS_S3_ENDPOINT_URL"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("AWS_S3_REGION_NAME", "auto"),
    )

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"{PREFIX}/{db_name}-{stamp}.dump"

    with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as f:
        dump_path = Path(f.name)

    try:
        subprocess.run(
            [
                "pg_dump",
                "-h", db.hostname or "localhost",
                "-p", str(db.port or 5432),
                "-U", db.username or "",
                "-d", db_name,
                "-Fc",
                "--no-owner",
                "--no-acl",
                "-f", str(dump_path),
            ],
            env={**os.environ, "PGPASSWORD": db.password or ""},
            check=True,
        )
        size = dump_path.stat().st_size
        s3.upload_file(str(dump_path), bucket, key)
        print(f"[{datetime.utcnow().isoformat()}Z] uploaded {key} ({size} bytes)")
    finally:
        dump_path.unlink(missing_ok=True)

    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    to_delete = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=f"{PREFIX}/"):
        for obj in page.get("Contents", []):
            if obj["LastModified"] < cutoff:
                to_delete.append({"Key": obj["Key"]})

    if to_delete:
        s3.delete_objects(Bucket=bucket, Delete={"Objects": to_delete})
        print(f"[{datetime.utcnow().isoformat()}Z] pruned {len(to_delete)} backups older than {KEEP_DAYS}d")

    return 0


if __name__ == "__main__":
    sys.exit(main())
