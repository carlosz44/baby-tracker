"""Load kick sessions from JSON (file or stdin), skipping ones already stored.

Rows: {"started_at": ISO 8601, "count": int, "minutes": int|null, "notes": str}.
The repo is public, so session data is piped in over SSH rather than committed.
"""
import json
import sys
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.baby.models import KickSession
from apps.baby.services import COMPARED_FIELDS, upsert_sessions


class Command(BaseCommand):
    help = "Load kick sessions from a JSON file or stdin; existing sessions are left untouched."

    def add_arguments(self, parser):
        parser.add_argument("path", nargs="?", help="JSON file (default: stdin)")
        parser.add_argument("--source", required=True, choices=[c for c, _ in KickSession.SOURCE_CHOICES])
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        if options["path"]:
            with open(options["path"]) as f:
                raw = f.read()
        else:
            raw = sys.stdin.read()

        try:
            rows = [self._parse(row) for row in json.loads(raw)]
        except (ValueError, KeyError, TypeError) as exc:
            raise CommandError(f"Invalid input: {exc}") from exc

        with transaction.atomic():
            result = upsert_sessions(rows, source=options["source"])
            if options["dry_run"]:
                transaction.set_rollback(True)

        for current, incoming in result.conflicts:
            diffs = ", ".join(
                f"{f}: {getattr(current, f)!r} → {getattr(incoming, f)!r}"
                for f in COMPARED_FIELDS
                if getattr(current, f) != getattr(incoming, f)
            )
            started = timezone.localtime(current.started_at)
            self.stdout.write(self.style.WARNING(f"conflict {started:%Y-%m-%d %H:%M} ({diffs})"))

        prefix = "[dry run] " if options["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}created {len(result.created)}, unchanged {len(result.unchanged)}, "
            f"conflicts {len(result.conflicts)}"
        ))

    @staticmethod
    def _parse(row):
        started_at = datetime.fromisoformat(row["started_at"])
        if timezone.is_naive(started_at):
            started_at = timezone.make_aware(started_at)
        minutes = row.get("minutes")
        return {
            "started_at": started_at,
            "count": int(row["count"]),
            "duration_seconds": minutes * 60 if minutes is not None else None,
            "notes": row.get("notes", ""),
        }
