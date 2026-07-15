# Baby Tracker

A private pregnancy tracking app for you and your partner. Track weekly logs, medical appointments (synced to Google Calendar), upload ultrasound images and lab results to cloud storage, count kicks, and write your birth plan — all in one warm, mobile-friendly interface.

Built with Django, HTMX, Tailwind CSS, PostgreSQL, and Cloudflare R2.

## Features

- **Dashboard** — Current pregnancy week, days until due date, upcoming appointments, recent files
- **Appointments** — CRUD with Google Calendar sync (auto-creates events with reminders)
- **Files** — Upload ultrasounds, lab results, prescriptions, belly photos and videos to Cloudflare R2
- **Weekly Logs** — Track weight, blood pressure, symptoms, mood per pregnancy week
- **Kick Counter** — Log daily kick count sessions with duration tracking
- **Birth Plan** — Write and edit your birth preferences
- **Notifications & Diagnostics** — Calendar sync failures (e.g. expired Google grant, missing calendar permission) surface as retryable notifications at `/notifications/`, with live per-user auth diagnostics and a one-click resync for future appointments
- **Google OAuth SSO** — Login restricted to a whitelist of 2 Gmail addresses
- **Dark Mode** — Toggle with localStorage persistence, no flash on reload
- **Mobile-first** — Bottom nav on mobile, sidebar on desktop

## Prerequisites

- Docker & Docker Compose
- A Google Cloud project with OAuth 2.0 credentials and Calendar API enabled

## Local Development Setup

### 1. Clone and configure

```bash
git clone <your-repo-url>
cd baby-tracker
cp .env.example .env
```

Edit `.env` with your values. At minimum:

```
SECRET_KEY=some-random-secret-key
ALLOWED_LOGIN_EMAILS=you@gmail.com,partner@gmail.com
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

### 2. Start services

```bash
docker compose up --build
```

This starts:
- **web** on http://localhost:8000 (Django + Tailwind watcher)
- **db** on port 5432 (PostgreSQL 16)

File storage points at Cloudflare R2 (set the `AWS_*` vars in `.env`).

### 3. Run migrations

```bash
docker compose exec web python manage.py migrate
```

### 4. Create a Django Site

django-allauth requires a Site object. In the Django shell:

```bash
docker compose exec web python manage.py shell -c "
from django.contrib.sites.models import Site
Site.objects.update_or_create(id=1, defaults={'domain': 'localhost:8000', 'name': 'Baby Tracker'})
"
```

### 5. Configure Google OAuth in Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. **Enable APIs**: Calendar API
4. **OAuth consent screen**: External, add your two Gmail addresses as test users
5. **Credentials** → Create OAuth 2.0 Client ID:
   - Application type: Web application
   - Authorized redirect URIs:
     - `http://localhost:8000/accounts/google/login/callback/` (local)
     - `https://yourdomain.com/accounts/google/login/callback/` (production)
6. Copy the Client ID and Client Secret into your `.env`

### 6. Set up the SocialApp in Django Admin

```bash
docker compose exec web python manage.py createsuperuser
```

Then go to http://localhost:8000/admin/ → Social Applications → Add:
- Provider: Google
- Name: Google
- Client ID: (from Google Console)
- Secret key: (from Google Console)
- Sites: select your site

### 7. Visit the app

Open http://localhost:8000 — you'll be redirected to Google OAuth login.

## Environment Variables

| Variable | Description | Example |
|---|---|---|
| `SECRET_KEY` | Django secret key | `your-random-secret` |
| `DEBUG` | Debug mode | `True` |
| `ALLOWED_HOSTS` | Comma-separated hostnames | `localhost,127.0.0.1` |
| `ALLOWED_LOGIN_EMAILS` | Whitelisted Gmail addresses | `you@gmail.com,partner@gmail.com` |
| `DATABASE_URL` | PostgreSQL connection string | `postgres://baby:baby@db:5432/babytracker` |
| `AWS_ACCESS_KEY_ID` | R2 access key | `<r2-access-key-id>` |
| `AWS_SECRET_ACCESS_KEY` | R2 secret key | `<r2-secret-access-key>` |
| `AWS_STORAGE_BUCKET_NAME` | Bucket name | `baby-tracker` |
| `AWS_S3_ENDPOINT_URL` | S3-compatible endpoint | `https://<account>.r2.cloudflarestorage.com` |
| `AWS_S3_REGION_NAME` | S3 region (use `auto` for R2) | `auto` |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | `123...apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | `GOCSPX-...` |
| `DJANGO_SETTINGS_MODULE` | Settings module (`config.settings.local` or `.production`) | `config.settings.local` |

## Running Tests

```bash
docker compose exec web pytest
```

## Production Deployment

Production runs entirely in Docker on the VPS at `/srv/baby-tracker/`:

- **caddy** (ports 80/443) — reverse proxy with automatic Let's Encrypt HTTPS
- **web** — `ghcr.io/carlosz44/baby-tracker:latest` (gunicorn; WhiteNoise serves static files)
- **db** — `postgres:16-alpine` with a named volume

GitHub Secrets are the single source of truth: `.env` on the VPS is rewritten from them on every deploy.

### Provisioning a host

Run the **Provision VPS** workflow (Actions → Provision VPS → Run workflow). It SSHes as root and idempotently installs Docker, configures UFW/fail2ban, creates the `deploy` user (in the `docker` group), and installs the nightly backup cron. No manual server setup.

One-time cutover inputs (already used for the original migration): `migrate_db` copies the legacy host Postgres into the container (taking a safety dump to R2 first); `decommission_legacy` stops nginx/gunicorn/host-postgres and hands 80/443 to Caddy.

### GitHub Actions CI/CD

`.github/workflows/deploy.yml`, on push to `main`:
1. `pytest` against a Postgres service container.
2. Builds the production image (Tailwind build + `collectstatic` baked in) and pushes to GHCR.
3. SSHes in as `deploy`: copies `deploy/compose.prod.yml`, `deploy/Caddyfile` and `deploy/backup_db.sh` to `/srv/baby-tracker/`, rewrites `.env` from Secrets, `docker compose pull && up -d`, runs `migrate`.

Required GitHub Secrets:

| Secret | Description |
|---|---|
| `VPS_HOST` | Server IP or hostname |
| `VPS_SSH_KEY` | Private SSH key (authorized for both `deploy` and `root`) |
| `SECRET_KEY` | Django secret key |
| `ALLOWED_HOSTS` | The public domain (single value — Caddy uses it as site address) |
| `ALLOWED_LOGIN_EMAILS` | Whitelisted Gmail addresses |
| `DATABASE_URL` | `postgres://baby:<pwd>@db:5432/babytracker` |
| `POSTGRES_PASSWORD` | Same `<pwd>` as in `DATABASE_URL` |
| `ACME_EMAIL` | Email for Let's Encrypt notices |
| `AWS_ACCESS_KEY_ID` | R2 access key |
| `AWS_SECRET_ACCESS_KEY` | R2 secret key |
| `AWS_STORAGE_BUCKET_NAME` | Bucket name (e.g. `baby-tracker`) |
| `AWS_S3_ENDPOINT_URL` | `https://<account>.r2.cloudflarestorage.com` |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |

`DEBUG=False`, `AWS_S3_REGION_NAME=auto`, and `DJANGO_SETTINGS_MODULE=config.settings.production` are hardcoded by the workflow.

### Static files

Built into the image at CI time: Tailwind minified CSS + `collectstatic` with WhiteNoise's `CompressedManifestStaticFilesStorage` (content-hashed filenames, gzip/brotli, `immutable` cache headers). `input.css` is excluded via `--ignore="input.css"` because it's the Tailwind source, not a runtime asset.

### Migrating to a new host (e.g. Proxmox home server)

1. Point `VPS_HOST` at the new machine (root SSH with `VPS_SSH_KEY`).
2. Run the Provision VPS workflow.
3. Re-run the deploy workflow (or push to `main`).
4. Restore the latest dump from R2: `docker compose -f compose.prod.yml exec -T db pg_restore -U baby -d babytracker --clean --if-exists < babytracker-YYYY-MM-DD.dump`
5. Point DNS at the new IP — Caddy issues the cert automatically.

### Cloudflare R2 Setup (Production Storage)

1. In Cloudflare dashboard → R2 → Create bucket: `baby-tracker`
2. Create an R2 API token with read/write permissions
3. Set in your production `.env`:
   ```
   AWS_ACCESS_KEY_ID=<r2-access-key-id>
   AWS_SECRET_ACCESS_KEY=<r2-secret-access-key>
   AWS_STORAGE_BUCKET_NAME=baby-tracker
   AWS_S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
   AWS_S3_REGION_NAME=auto
   ```

### Nightly DB backups to R2

`/srv/baby-tracker/backup_db.sh` runs nightly via `/etc/cron.d/baby-tracker-backup` (installed by the provision workflow). It `pg_dump`s from the db container (`-Fc` custom format) and pipes the dump to `scripts/backup_db.py` in the web image, which uploads to R2 under `db-backups/babytracker-YYYY-MM-DD.dump` and prunes anything older than 30 days. Logs to `/var/log/baby-tracker-backup.log`.

Test manually: `ssh deploy@<vps> /srv/baby-tracker/backup_db.sh` (you should see an `uploaded db-backups/...` line and a new object in the R2 bucket).

### TrueNAS Cloud Sync (optional, not currently enabled)

To back up R2 files to a local TrueNAS:

1. TrueNAS Web UI → Credentials → Cloud Credentials → Add
   - Provider: S3-compatible (Cloudflare R2)
   - Endpoint: `https://<account-id>.r2.cloudflarestorage.com`
   - Access Key / Secret Key from R2 API token
2. Data Protection → Cloud Sync Tasks → Add
   - Direction: PULL
   - Transfer mode: SYNC (mirrors R2 — files deleted from R2 also disappear from TrueNAS) or COPY (additive — old DB dumps survive past 30 days; use this if you want longer retention than R2's prune window)
   - Remote: your R2 credential, bucket `baby-tracker`
   - Local: target dataset path (e.g., `/mnt/pool/backups/baby-tracker`)
   - Schedule: Daily at 3:30 AM (after the DB-dump cron at 3:00 AM)
3. Test the task with "Dry Run", then save

The bucket holds two prefixes: `pregnancy-files/` (user uploads) and `db-backups/` (nightly Postgres dumps). The sync pulls both.

## Google Cloud Console Setup

1. Create a new project at https://console.cloud.google.com/
2. **APIs & Services → Library**: Enable "Google Calendar API"
3. **APIs & Services → OAuth consent screen**:
   - User type: External
   - App name: Baby Tracker
   - Scopes: `email`, `profile`, `https://www.googleapis.com/auth/calendar`
   - Test users: add both Gmail addresses
4. **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**:
   - Application type: Web application
   - Authorized redirect URIs:
     - `http://localhost:8000/accounts/google/login/callback/`
     - `https://yourdomain.com/accounts/google/login/callback/`
5. Copy Client ID and Client Secret to your `.env` file
6. Note: While in "Testing" mode, only listed test users can log in. Submit for verification when ready for production (though for a private 2-user app, testing mode works fine).
