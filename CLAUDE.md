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
```

## Architecture

### Settings

Split settings in `config/settings/`: `base.py` (shared), `local.py` (debug toolbar, console email), `production.py` (security hardening). `manage.py` defaults to `config.settings.local`. Environment variables loaded via `python-decouple`.

### Django Apps (under `apps/`)

- **accounts** — Custom `User` model (email as USERNAME_FIELD), `Profile` model with due date and pregnancy week calculations. `WhitelistSocialAccountAdapter` in `adapters.py` restricts login to allowed emails.
- **appointments** — `Appointment` model with Google Calendar sync. `signals.py` auto-creates/deletes calendar events on save/delete via `calendar_service.py` (uses allauth's `SocialToken` for OAuth credentials).
- **files** — `PregnancyFile` model with S3-backed `FileField` (upload to `pregnancy-files/%Y/%m/`). Signed URLs expire after 1 hour.
- **baby** — `WeeklyLog` (weight, blood pressure, symptoms, mood), `KickCount` (daily kick sessions), `BirthPlan` (one per user).

### Frontend

- Templates in `templates/` (not per-app). `base.html` has sidebar nav (desktop) + bottom nav (mobile).
- Tailwind CSS v4 via standalone CLI (no Node.js). Source: `static/css/input.css`, output: `static/css/output.css` (gitignored). `input.css` contains `@import "tailwindcss";` and must be excluded from `collectstatic` with `--ignore="input.css"` — otherwise `ManifestStaticFilesStorage` tries to resolve the import and 500s.
- Dark mode via `class` strategy with `localStorage` persistence. Dark palette uses **zinc** (neutral gray); light uses **slate** (blue-tinged gray).
- HTMX loaded from CDN. django-htmx middleware enabled.
- Forms rendered with crispy-forms + crispy-tailwind.

### Key Patterns

- Models are **not scoped per-user** (this is a 2-person app). Appointments and files are shared; `WeeklyLog` and `KickCount` track `logged_by`.
- Profile `due_date` stores first day of last menstrual period (FUR/LMP). `pregnancy_week` and `days_remaining` are computed properties.
- Google Calendar integration is fire-and-forget: failures are logged but don't block the request (signal handler catches all exceptions).
- Timezone is hardcoded to `America/Lima` with `USE_TZ=True`. For date calculations that represent "today" to the user, use `timezone.localdate()` — **not** `timezone.now().date()` (which returns UTC) or `date.today()` (which returns system-local, flaky in CI).

## CI/CD

GitHub Actions (`.github/workflows/deploy.yml`): pushes to `main` run pytest with a Postgres service container, then build Tailwind CSS on the runner, `scp` the minified `output.css` to the VPS, and SSH-deploy. The SSH script `source .env` (so `DJANGO_SETTINGS_MODULE=config.settings.production` is set for `manage.py`), then runs migrate, `touch static/css/output.css` (so `collectstatic` doesn't skip on mtime), `collectstatic --no-input --clear --ignore="input.css"`, and restarts gunicorn. Tailwind is built in CI (not on the VPS) because budget VPSes OOM-kill tailwindcss during the build.

Production uses `ManifestStaticFilesStorage` (set in `config/settings/production.py`): `collectstatic` content-hashes static filenames (`output.css` → `output.a1b2c3d4.css`) and writes `staticfiles.json`. Combined with Nginx's `expires 30d` + `Cache-Control: public, immutable` on `/static/`, this gives permanent-cache for unchanged assets and instant invalidation when content changes. Any `{% static %}` reference to a file missing from the manifest raises `ValueError` at render time — a 500 on all pages.

`scripts/bootstrap-vps.sh` provisions a fresh Ubuntu/Debian VPS end-to-end: installs Python/Postgres/Nginx/Certbot/Tailwind CLI, creates the `deploy` user with `NOPASSWD` sudo scoped to `systemctl restart gunicorn-baby`, sets up the DB, clones the repo, writes `.env`, runs migrations + collectstatic, installs the `gunicorn-baby` systemd unit, configures Nginx, issues a Let's Encrypt cert, and enables UFW. Idempotent — safe to re-run.

Config is loaded with precedence `shell env > scripts/bootstrap.env > scripts/bootstrap.env.example`. Copy `scripts/bootstrap.env.example` to `scripts/bootstrap.env` (gitignored) and fill it in, or pass values as env vars. `REPO_URL` auto-detects from the checked-out repo's `origin` remote. Missing required values are prompted interactively. Invoke as root: `sudo -E bash scripts/bootstrap-vps.sh`.
