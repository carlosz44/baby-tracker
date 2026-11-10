# CLAUDE.md

Adds to `~/Dev/CLAUDE.md` and never contradicts it.

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

# Build Tailwind CSS manually (start.sh runs a watcher, but it misses edits made from
# the macOS host through the bind mount, so rerun this when new classes don't apply)
tailwindcss -i static/css/input.css -o static/css/output.css

# Load kick sessions from JSON on stdin (idempotent, --dry-run to preview).
# The repo is PUBLIC: personal data is never committed. Pipe it in over SSH for prod:
#   ssh admin@<vps> 'cd /srv/baby-tracker && sudo docker compose -f compose.prod.yml exec -T web python manage.py load_kick_sessions --source screenshot' < sessions.json
docker compose exec -T web python manage.py load_kick_sessions --source screenshot < sessions.json

# Diagnose Google Calendar sync state per user (token presence, refresh token,
# live API ping). Useful when sync isn't working for one of the two accounts.
docker compose exec web python manage.py check_calendar_sync
```

## Architecture

### Settings

Split settings in `config/settings/`: `base.py` (shared), `local.py` (debug toolbar, console email), `production.py` (security hardening). `manage.py` defaults to `config.settings.local`. Environment variables loaded via `python-decouple`.

### Django Apps (under `apps/`)

- **accounts**: custom `User` model (email as USERNAME_FIELD), `Profile` model with due date and pregnancy week calculations. `WhitelistSocialAccountAdapter` in `adapters.py` restricts login to allowed emails.
- **appointments**: `Appointment` model with Google Calendar sync. `signals.py` auto-creates/deletes calendar events on save/delete via `calendar_service.py` (uses allauth's `SocialToken` for OAuth credentials).
- **files**: `PregnancyFile` model with S3-backed `FileField` (upload to `pregnancy-files/%Y/%m/`). Signed URLs expire after 1 hour.
- **baby**: `WeeklyLog` (weight, blood pressure, symptoms, mood), `KickSession` ("count to 10" sessions keyed by unique `started_at`, with `date` auto-derived in Lima on save and `source` = manual/screenshot/counter), `BirthPlan` (one per user). `services.upsert_sessions` inserts sessions idempotently (an existing `started_at` → unchanged or conflict, never overwritten). History, edit/delete and manual entry live at `/baby/kick-counter/history/`, and charts at `/baby/kick-counter/stats/`. `analytics.py` computes everything server-side: the 7-day rolling baseline, the "slow session" flag (over 2× baseline, or 2 h without reaching 10), time-of-day buckets and the adherence calendar. `static/js/kick_stats.js` draws them with Chart.js 4.4.1 from cdnjs, pinned with SRI. The dashboard tile and alert banner reuse `recent_overview`. The tap counter on `/baby/kick-counter/` (`static/js/kick_counter.js`) keeps the running session in `localStorage` (survives reload/lock) and POSTs JSON once to `kick_session_save`, validated by `KickCounterForm`. Per-kick times go to `kick_offsets`, and `set_goal()` derives `time_to_goal_seconds` from the 10th kick.
- **notifications**: generic `Notification` model (`kind`, `severity`, `payload`, `dedupe_key`, optional `user`) for surfacing async/background failures to the UI. `registry.py` holds a `kind → handler` map (`@register_handler`), and each app registers its own handlers in its `apps.py:ready()`. `services.py` exposes `record_notification` (dedupes on unresolved key, bumps `attempts`), `mark_resolved`, `retry_notification`, and `unresolved_count`. The notifications page at `/notifications/` lists pending issues with HTMX retry/dismiss, plus a "Run diagnostics" button (calls `calendar_service.run_calendar_diagnostics`) and a "Resincronizar" button (calls `calendar_service.resync_future_appointments`, scoped to `date__gte=now`).

### Frontend

- Templates in `templates/` (not per-app). `base.html` has sidebar nav (desktop) + bottom nav (mobile). The mobile bottom nav holds only the 5 main destinations (`partials/_bottom_nav_item.html`, where the active item gets a pill driven by the `nav_section` context processor in `apps/accounts/context_processors.py`) and pads for the iPhone home indicator via `env(safe-area-inset-bottom)` (`viewport-fit=cover`). The mobile top bar has Avisos (with badge) + Perfil. The theme switch and logout live on the profile page.
- Tailwind CSS v4 via standalone CLI (no Node.js). Source: `static/css/input.css`, output: `static/css/output.css` (gitignored). `input.css` contains `@import "tailwindcss";` and must be excluded from `collectstatic` with `--ignore="input.css"`. Otherwise `ManifestStaticFilesStorage` tries to resolve the import and 500s.
- Dark mode via `class` strategy with `localStorage` persistence (set from the Claro/Oscuro switch on `/accounts/profile/`). Dark palette uses **zinc** (neutral gray), light uses **slate** (blue-tinged gray).
- HTMX loaded from CDN. django-htmx middleware enabled.
- Forms rendered with crispy-forms + crispy-tailwind.

### Key Patterns

- Models are **not scoped per-user** (this is a 2-person app). Appointments and files are shared, while `WeeklyLog` and `KickSession` track `logged_by` (nullable on `KickSession` for backfilled rows).
- Profile `due_date` stores first day of last menstrual period (FUR/LMP). `pregnancy_week` and `days_remaining` are computed properties. The actual scheduled birth is a separate field, `scheduled_birth_at`, set on the profile page. When it is present, the dashboard shows a live countdown (`static/js/birth_countdown.js`) instead of the FUR-based estimate tile. The repo is public, so the real date is never committed.
- Google Calendar integration is fire-and-forget: failures are logged but don't block the request (signal handler catches all exceptions). Failures also record a `Notification` so the user sees them at `/notifications/`: `CALENDAR_AUTH_REQUIRED` (severity error, no retry handler, needs a re-login) for `MissingCalendarAuth` cases (no token, no refresh token, `invalid_scope`, generic `RefreshError`), and `CALENDAR_SYNC_FAILED` (severity warning, retryable) for transient errors. A successful sync resolves any prior notification with the same `dedupe_key` (`appointment:<id>:user:<id>:<action>`).
- Refreshed Google access tokens are persisted back to `SocialToken` (`token`, `expires_at`) inside `_persist_refreshed_credentials`, so the access token doesn't have to refresh on every API call. Refresh-time failures bubble up as `MissingCalendarAuth` via `_classify_refresh_error`, and `auth_required_message(reason)` translates them to user-facing strings. It is the single source of truth for both the sync notification message and the diagnostics page.
- Timezone is hardcoded to `America/Lima` with `USE_TZ=True`. For date calculations that represent "today" to the user, use `timezone.localdate()`, **not** `timezone.now().date()` (which returns UTC) or `date.today()` (which returns system-local, flaky in CI).

## CI/CD

Production runs in Docker at `/srv/baby-tracker/` on the VPS: `caddy` (80/443, automatic Let's Encrypt HTTPS, 100MB request body limit), `web` (`ghcr.io/carlosz44/baby-tracker:latest`, gunicorn 3 workers), `db` (`postgres:16-alpine`, named volume `pgdata`). Config files live in the repo under `deploy/` (`compose.prod.yml`, `Caddyfile`, `backup_db.sh`) and are copied to the VPS on every deploy, so infra changes ship via push to `main`, with no manual SSH.

GitHub Actions (`.github/workflows/deploy.yml`) runs three steps on push to `main`. (1) pytest with a Postgres service container. (2) Build the production image (multi-stage `Dockerfile`, target `prod`: Tailwind build + `collectstatic` baked in at build time with dummy env vars) and push it to GHCR (`latest` + commit SHA tags, GHA layer cache). (3) SSH as `deploy`, copy the `deploy/*` files, **rewrite `/srv/baby-tracker/.env` from GitHub Secrets on every deploy** (single source of truth), pull the images, start `db` and wait until it is healthy, run `migrate` in a one-off `web` container from the new image, then `up -d` and prune images. Migrating first means the old containers keep serving if a migration fails. `DEBUG=False`, `AWS_S3_REGION_NAME=auto`, `DJANGO_SETTINGS_MODULE=config.settings.production` are hardcoded in the workflow heredoc. Secrets: `SECRET_KEY`, `ALLOWED_HOSTS` (single domain, which doubles as the Caddy site address), `ALLOWED_LOGIN_EMAILS`, `DATABASE_URL` (host `db`), `POSTGRES_PASSWORD`, `ACME_EMAIL`, `AWS_*` minus region, `GOOGLE_CLIENT_ID/SECRET`, `VPS_HOST`, `VPS_SSH_KEY` (authorized for `admin`, and copied to `deploy` by `provision.yml`).

`.github/workflows/provision.yml` (manual `workflow_dispatch`) provisions any fresh Ubuntu/Debian host over SSH as `admin` with sudo (root SSH has been disabled since 2026-07-14): installs Docker, UFW (22/80/443), fail2ban, creates the `deploy` user in the `docker` group, installs the backup cron. The legacy host stack from before the 2026-07-14 cutover was deleted on 2026-09-30, so there is nothing to roll back to.

Static files use WhiteNoise's `CompressedManifestStaticFilesStorage` (set in `config/settings/production.py`, middleware inserted after SecurityMiddleware): content-hashed filenames + `staticfiles.json` manifest + gzip/brotli, served from inside the web container with immutable cache headers. Caddy is a pure proxy. Any `{% static %}` reference to a file missing from the manifest raises `ValueError` at render time, which is a 500 on all pages. Static is baked into the image at CI build, and there is no collectstatic on the VPS.

Nightly backups: `/etc/cron.d/baby-tracker-backup` runs `/srv/baby-tracker/backup_db.sh` at 3am: `pg_dump -Fc` inside the db container, piped to `scripts/backup_db.py --stdin` in the web image (boto3), uploading to R2 `db-backups/babytracker-YYYY-MM-DD.dump` with 30-day pruning. The script validates the `PGDMP` magic bytes so a failed dump never overwrites a good backup. Logs to `/var/log/baby-tracker-backup.log`. R2 is the only backup location (no TrueNAS sync configured). Restore: `docker compose -f compose.prod.yml exec -T db pg_restore -U baby -d babytracker --clean --if-exists < <dump>`.
