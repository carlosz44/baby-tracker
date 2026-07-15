#!/bin/bash
# Nightly cron: pg_dump from the db container piped to R2 via the web image.
set -euo pipefail

cd /srv/baby-tracker

docker compose -f compose.prod.yml exec -T db \
  pg_dump -Fc --no-owner --no-acl -U baby -d babytracker \
  | docker compose -f compose.prod.yml run --rm -T web \
      python scripts/backup_db.py --stdin
