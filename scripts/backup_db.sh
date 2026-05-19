#!/bin/bash
# Cron entrypoint for the nightly DB backup. Loads .env, then hands off
# to backup_db.py (which uses the app's venv + boto3 already installed).
set -euo pipefail

APP_DIR=/var/www/baby-tracker
cd "$APP_DIR"

set -a
source .env
set +a

exec "$APP_DIR/venv/bin/python" "$APP_DIR/scripts/backup_db.py"
