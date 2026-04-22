# Baby Tracker

A private pregnancy tracking app for you and your partner. Track weekly logs, medical appointments (synced to Google Calendar), upload ultrasound images and lab results to cloud storage, count kicks, and write your birth plan — all in one warm, mobile-friendly interface.

Built with Django, HTMX, Tailwind CSS, PostgreSQL, and Cloudflare R2.

## Features

- **Dashboard** — Current pregnancy week, days until due date, upcoming appointments, recent files
- **Appointments** — CRUD with Google Calendar sync (auto-creates events with reminders)
- **Files** — Upload ultrasounds, lab results, prescriptions, belly photos to S3-compatible storage (R2/MinIO)
- **Weekly Logs** — Track weight, blood pressure, symptoms, mood per pregnancy week
- **Kick Counter** — Log daily kick count sessions with duration tracking
- **Birth Plan** — Write and edit your birth preferences
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
- **minio** on http://localhost:9000 (S3-compatible storage, console at :9001)

### 3. Run migrations and create the storage bucket

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py create_minio_bucket
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
| `AWS_ACCESS_KEY_ID` | S3/R2/MinIO access key | `minioadmin` |
| `AWS_SECRET_ACCESS_KEY` | S3/R2/MinIO secret key | `minioadmin` |
| `AWS_STORAGE_BUCKET_NAME` | Bucket name | `baby-tracker` |
| `AWS_S3_ENDPOINT_URL` | S3-compatible endpoint | `http://minio:9000` |
| `AWS_S3_REGION_NAME` | S3 region (use `auto` for R2) | `auto` |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | `123...apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | `GOCSPX-...` |

## Running Tests

```bash
docker compose exec web pytest
```

## Production Deployment

### One-shot VPS provisioning

`scripts/bootstrap-vps.sh` provisions a fresh Ubuntu/Debian VPS end-to-end: apt packages, Postgres, Nginx, systemd, Certbot, UFW, the `deploy` user with narrowly-scoped `NOPASSWD` sudo, the `.env` file, migrations, and the `gunicorn-baby` service. It's idempotent — safe to re-run.

```bash
# On the VPS, after cloning the repo to /tmp:
cd /tmp/baby-tracker
cp scripts/bootstrap.env.example scripts/bootstrap.env
$EDITOR scripts/bootstrap.env      # fill in DOMAIN, EMAIL, OAuth, R2, etc.
sudo -E bash scripts/bootstrap-vps.sh
```

Values not set in `scripts/bootstrap.env` are prompted for interactively. See `scripts/bootstrap.env.example` for the full list (`DOMAIN`, `EMAIL`, `ALLOWED_EMAILS`, `GOOGLE_CLIENT_ID/SECRET`, `R2_ACCESS_KEY/SECRET/ENDPOINT`, plus optional overrides).

Heads-up for tiny VPSes (≤1GB RAM): add a swap file before running bootstrap, otherwise the kernel OOM-kills processes. `fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile`, then add `/swapfile none swap sw 0 0` to `/etc/fstab`.

### GitHub Actions CI/CD

`.github/workflows/deploy.yml`:
1. On push to `main`, runs `pytest` against a Postgres service container.
2. On success, downloads the Tailwind CLI on the GitHub runner, builds `output.css --minify`, and `scp`s it to the VPS (Tailwind can't build on a 1GB VPS without OOM).
3. SSHes in, `git pull`, sources `.env` (so `DJANGO_SETTINGS_MODULE=production`), `pip install`, `migrate`, `touch` + `collectstatic --clear --ignore="input.css"`, restart gunicorn.

Required GitHub Secrets:
- `VPS_HOST` — Server IP or hostname
- `VPS_USER` — SSH username (`deploy`)
- `VPS_SSH_KEY` — Private SSH key for the deploy user

### Static file caching

Production uses `ManifestStaticFilesStorage`: `collectstatic` renames files to `output.a1b2c3d4.css` based on content hash, with Nginx serving `/static/` as `immutable` for 30 days. Cache-busting is automatic on every CSS change — no hard-reloads needed. `input.css` is excluded from collectstatic via `--ignore="input.css"` because it's the Tailwind source, not a runtime asset.

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

### TrueNAS Cloud Sync (Nightly R2 Backup)

To back up R2 files to your local TrueNAS:

1. TrueNAS Web UI → Credentials → Cloud Credentials → Add
   - Provider: S3-compatible (Cloudflare R2)
   - Endpoint: `https://<account-id>.r2.cloudflarestorage.com`
   - Access Key / Secret Key from R2 API token
2. Data Protection → Cloud Sync Tasks → Add
   - Direction: PULL
   - Transfer mode: SYNC
   - Remote: your R2 credential, bucket `baby-tracker`
   - Local: target dataset path (e.g., `/mnt/pool/backups/baby-tracker`)
   - Schedule: Daily at 3:00 AM
3. Test the task with "Dry Run", then save

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
