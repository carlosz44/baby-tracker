# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Private pregnancy tracking app for two users (couple). Django 5.2 + HTMX + Tailwind CSS + PostgreSQL + S3-compatible storage (Cloudflare R2 in prod, MinIO locally). Authentication is Google OAuth SSO restricted to a whitelist of two Gmail addresses (`ALLOWED_LOGIN_EMAILS`).

## Development Commands

```bash
# Start all services (web on :8000, postgres on :5432, minio on :9000/:9001)
docker compose up --build

# Run migrations
docker compose exec web python manage.py migrate

# Run tests
docker compose exec web pytest

# Run a single test file
docker compose exec web pytest apps/baby/tests.py

# Run a single test by name
docker compose exec web pytest -k "test_name"

# Django shell
docker compose exec web python manage.py shell

# Create MinIO bucket (first time setup)
docker compose exec web python manage.py create_minio_bucket

# Build Tailwind CSS manually (normally handled by start.sh watcher)
tailwindcss -i static/css/input.css -o static/css/output.css

# Diagnose Google Calendar sync state per user (token presence, refresh token,
# live API ping). Useful when sync isn't working for one of the two accounts.
docker compose exec web python manage.py check_calendar_sync
```

## Architecture

### Settings

Split settings in `config/settings/`: `base.py` (shared), `local.py` (debug toolbar, console email), `production.py` (security hardening). `manage.py` defaults to `config.settings.local`. Environment variables loaded via `python-decouple`.

### Django Apps (under `apps/`)

- **accounts** — Custom `User` model (email as USERNAME_FIELD), `Profile` model with due date and pregnancy week calculations. `WhitelistSocialAccountAdapter` in `adapters.py` restricts login to allowed emails.
- **appointments** — `Appointment` model with Google Calendar sync. `signals.py` auto-creates/deletes calendar events on save/delete via `calendar_service.py` (uses allauth's `SocialToken` for OAuth credentials).
- **files** — `PregnancyFile` model with S3-backed `FileField` (upload to `pregnancy-files/%Y/%m/`). Signed URLs expire after 1 hour.
- **baby** — `WeeklyLog` (weight, blood pressure, symptoms, mood), `KickCount` (daily kick sessions), `BirthPlan` (one per user).
- **notifications** — Generic `Notification` model (`kind`, `severity`, `payload`, `dedupe_key`, optional `user`) for surfacing async/background failures to the UI. `registry.py` holds a `kind → handler` map (`@register_handler`); each app registers its own handlers in its `apps.py:ready()`. `services.py` exposes `record_notification` (dedupes on unresolved key, bumps `attempts`), `mark_resolved`, `retry_notification`, and `unresolved_count`. The notifications page at `/notifications/` lists pending issues with HTMX retry/dismiss, plus a "Run diagnostics" button (calls `calendar_service.run_calendar_diagnostics`) and a "Resincronizar" button (calls `calendar_service.resync_future_appointments`, scoped to `date__gte=now`).

### Frontend

- Templates in `templates/` (not per-app). `base.html` has sidebar nav (desktop) + bottom nav (mobile).
- Tailwind CSS v4 via standalone CLI (no Node.js). Source: `static/css/input.css`, output: `static/css/output.css` (gitignored). `input.css` contains `@import "tailwindcss";` and must be excluded from `collectstatic` with `--ignore="input.css"` — otherwise `ManifestStaticFilesStorage` tries to resolve the import and 500s.
- Dark mode via `class` strategy with `localStorage` persistence. Dark palette uses **zinc** (neutral gray); light uses **slate** (blue-tinged gray).
- HTMX loaded from CDN. django-htmx middleware enabled.
- Forms rendered with crispy-forms + crispy-tailwind.

### Key Patterns

- Models are **not scoped per-user** (this is a 2-person app). Appointments and files are shared; `WeeklyLog` and `KickCount` track `logged_by`.
- Profile `due_date` stores first day of last menstrual period (FUR/LMP). `pregnancy_week` and `days_remaining` are computed properties.
- Google Calendar integration is fire-and-forget: failures are logged but don't block the request (signal handler catches all exceptions). Failures also record a `Notification` so the user sees them at `/notifications/` — `CALENDAR_AUTH_REQUIRED` (severity error, no retry handler — needs re-login) for `MissingCalendarAuth` cases (no token, no refresh token, `invalid_scope`, generic `RefreshError`); `CALENDAR_SYNC_FAILED` (severity warning, retryable) for transient errors. Successful sync resolves any prior notification with the same `dedupe_key` (`appointment:<id>:user:<id>:<action>`).
- Refreshed Google access tokens are persisted back to `SocialToken` (`token`, `expires_at`) inside `_persist_refreshed_credentials`, so the access token doesn't have to refresh on every API call. Refresh-time failures bubble up as `MissingCalendarAuth` via `_classify_refresh_error` — translated to user-facing strings by `auth_required_message(reason)`, which is the single source of truth for both the sync notification message and the diagnostics page.
- Timezone is hardcoded to `America/Lima` with `USE_TZ=True`. For date calculations that represent "today" to the user, use `timezone.localdate()` — **not** `timezone.now().date()` (which returns UTC) or `date.today()` (which returns system-local, flaky in CI).

## CI/CD

GitHub Actions (`.github/workflows/deploy.yml`): pushes to `main` run pytest with a Postgres service container, then build Tailwind CSS on the runner, `scp` the minified `output.css` to the VPS, and SSH-deploy. The SSH script **rewrites `/var/www/baby-tracker/.env` from GitHub Secrets on every deploy** (heredoc populated from `secrets.*`), sources it, runs migrate, `touch static/css/output.css` (so `collectstatic` doesn't skip on mtime), `collectstatic --no-input --clear --ignore="input.css"`, and restarts `gunicorn-baby-tracker`. Tailwind is built in CI (not on the VPS) because budget VPSes OOM-kill tailwindcss during the build. `DEBUG=False`, `AWS_S3_REGION_NAME=auto`, and `DJANGO_SETTINGS_MODULE=config.settings.production` are hardcoded in the workflow's heredoc; everything else comes from Secrets (`SECRET_KEY`, `ALLOWED_HOSTS`, `ALLOWED_LOGIN_EMAILS`, `DATABASE_URL`, `AWS_*` minus region, `GOOGLE_CLIENT_ID/SECRET`, plus `VPS_HOST`/`VPS_SSH_KEY`). The deploy SSH user is hardcoded as `deploy`.

Production uses `ManifestStaticFilesStorage` (set in `config/settings/production.py`): `collectstatic` content-hashes static filenames (`output.css` → `output.a1b2c3d4.css`) and writes `staticfiles.json`. Combined with Nginx's `expires 30d` + `Cache-Control: public, immutable` on `/static/`, this gives permanent-cache for unchanged assets and instant invalidation when content changes. Any `{% static %}` reference to a file missing from the manifest raises `ValueError` at render time — a 500 on all pages.

`scripts/bootstrap-vps.sh` provisions a fresh Ubuntu/Debian VPS end-to-end: installs Python/Postgres/Nginx/Certbot/Tailwind CLI, creates the `deploy` user with `NOPASSWD` sudo scoped to `systemctl restart gunicorn-baby-tracker`, sets up the DB, clones the repo, writes `.env`, runs migrations + collectstatic, installs the `gunicorn-baby-tracker` systemd unit, configures Nginx, issues a Let's Encrypt cert, and enables UFW. Idempotent — safe to re-run.

Deploy-time constants (`DEPLOY_USER=deploy`, `PYTHON_BIN=python3`, `APP_DIR=/var/www/baby-tracker`, `DB_NAME=babytracker`, `DB_USER=baby`, `R2_BUCKET=baby-tracker`, `SERVICE_NAME=gunicorn-baby-tracker`) are hardcoded in the script. `REPO_URL` auto-detects from the checked-out repo's `origin` remote. Required values (`DOMAIN`, `EMAIL`, `ALLOWED_EMAILS`, `GOOGLE_CLIENT_ID/SECRET`, `R2_ACCESS_KEY/SECRET/ENDPOINT`) are prompted for interactively, or can be passed as env vars. Invoke as root: `sudo -E bash scripts/bootstrap-vps.sh`. After bootstrap, copy values from `/var/www/baby-tracker/.env` into GitHub Secrets so CI deploys work.

Bootstrap also installs `/etc/cron.d/baby-tracker-backup`: nightly `scripts/backup_db.sh` (sources `.env`, then `scripts/backup_db.py` uses the app's venv + boto3) runs `pg_dump -Fc` and uploads to R2 at `db-backups/babytracker-YYYY-MM-DD.dump`, pruning anything older than 30 days. Logs to `/var/log/baby-tracker-backup.log`. The TrueNAS Cloud Sync then mirrors both `pregnancy-files/` and `db-backups/` prefixes locally. Disaster-recovery restore: `pg_restore -d babytracker --clean --if-exists <dump>` after re-running bootstrap.
