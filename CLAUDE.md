# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Private pregnancy tracking app for two users (couple). Django 5.2 + HTMX + Tailwind CSS + PostgreSQL + Cloudflare R2 for media (prod and local dev use separate buckets). Authentication is Google OAuth SSO restricted to a whitelist of two Gmail addresses (`ALLOWED_LOGIN_EMAILS`).

## Development Commands

```bash
# Start all services (web on :8000, postgres on :5432)
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

Production runs in Docker at `/srv/baby-tracker/` on the VPS: `caddy` (80/443, automatic Let's Encrypt HTTPS, 100MB request body limit), `web` (`ghcr.io/carlosz44/baby-tracker:latest`, gunicorn 3 workers), `db` (`postgres:16-alpine`, named volume `pgdata`). Config files live in the repo under `deploy/` (`compose.prod.yml`, `Caddyfile`, `backup_db.sh`) and are copied to the VPS on every deploy — infra changes ship via push to `main`, no manual SSH.

GitHub Actions (`.github/workflows/deploy.yml`), on push to `main`: (1) pytest with a Postgres service container; (2) build the production image (multi-stage `Dockerfile`, target `prod` — Tailwind build + `collectstatic` baked in at build time with dummy env vars) and push to GHCR (`latest` + commit SHA tags, GHA layer cache); (3) SSH as `deploy`, copy `deploy/*` files, **rewrite `/srv/baby-tracker/.env` from GitHub Secrets on every deploy** (single source of truth), `docker compose pull && up -d`, `migrate`, image prune. `DEBUG=False`, `AWS_S3_REGION_NAME=auto`, `DJANGO_SETTINGS_MODULE=config.settings.production` are hardcoded in the workflow heredoc. Secrets: `SECRET_KEY`, `ALLOWED_HOSTS` (single domain — doubles as the Caddy site address), `ALLOWED_LOGIN_EMAILS`, `DATABASE_URL` (host `db`), `POSTGRES_PASSWORD`, `ACME_EMAIL`, `AWS_*` minus region, `GOOGLE_CLIENT_ID/SECRET`, `VPS_HOST`, `VPS_SSH_KEY` (authorized for both `deploy` and `root`).

`.github/workflows/provision.yml` (manual `workflow_dispatch`) provisions any fresh Ubuntu/Debian host as root: installs Docker, UFW (22/80/443), fail2ban, creates the `deploy` user in the `docker` group, installs the backup cron. One-time cutover inputs: `migrate_db` (legacy host Postgres → container, with prior safety dump to R2), `decommission_legacy` (stops old nginx/gunicorn/host-postgres; legacy stack at `/var/www/baby-tracker` kept as cold backup).

Static files use WhiteNoise's `CompressedManifestStaticFilesStorage` (set in `config/settings/production.py`, middleware inserted after SecurityMiddleware): content-hashed filenames + `staticfiles.json` manifest + gzip/brotli, served from inside the web container with immutable cache headers — Caddy is a pure proxy. Any `{% static %}` reference to a file missing from the manifest raises `ValueError` at render time — a 500 on all pages. Static is baked into the image at CI build; there is no collectstatic on the VPS.

Nightly backups: `/etc/cron.d/baby-tracker-backup` runs `/srv/baby-tracker/backup_db.sh` at 3am — `pg_dump -Fc` inside the db container piped to `scripts/backup_db.py --stdin` in the web image (boto3), uploading to R2 `db-backups/babytracker-YYYY-MM-DD.dump` with 30-day pruning. The script validates the `PGDMP` magic bytes so a failed dump never overwrites a good backup. Logs to `/var/log/baby-tracker-backup.log`. R2 is the only backup location (no TrueNAS sync configured). Restore: `docker compose -f compose.prod.yml exec -T db pg_restore -U baby -d babytracker --clean --if-exists < <dump>`.
