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

### Server Setup

On your VPS (Ubuntu/Debian):

```bash
# Create project directory
sudo mkdir -p /var/www/baby-tracker
sudo chown $USER:$USER /var/www/baby-tracker

# Clone repo and set up venv
cd /var/www/baby-tracker
git clone <your-repo-url> .
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements/production.txt

# Install Tailwind CLI
curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64
chmod +x tailwindcss-linux-x64
sudo mv tailwindcss-linux-x64 /usr/local/bin/tailwindcss

# Build CSS, migrate, collect static
cp .env.example .env  # Edit with production values
tailwindcss -i static/css/input.css -o static/css/output.css --minify
python manage.py migrate
python manage.py collectstatic --no-input
```

### Gunicorn systemd Service

Create `/etc/systemd/system/gunicorn-baby.service`:

```ini
[Unit]
Description=Baby Tracker Gunicorn
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/baby-tracker
ExecStart=/var/www/baby-tracker/venv/bin/gunicorn config.wsgi:application \
    --bind unix:/var/www/baby-tracker/gunicorn.sock \
    --workers 3 \
    --timeout 120
EnvironmentFile=/var/www/baby-tracker/.env
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable gunicorn-baby
sudo systemctl start gunicorn-baby
```

### Nginx Configuration

Create `/etc/nginx/sites-available/baby-tracker`:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location /static/ {
        alias /var/www/baby-tracker/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://unix:/var/www/baby-tracker/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 20M;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/baby-tracker /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### SSL with Certbot

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

### GitHub Actions CI/CD

The project includes `.github/workflows/deploy.yml` which:
1. Runs tests on push to `main`
2. SSHs into the VPS to pull, install deps, build CSS, migrate, and restart Gunicorn

Required GitHub Secrets:
- `VPS_HOST` — Server IP or hostname
- `VPS_USER` — SSH username
- `VPS_SSH_KEY` — Private SSH key

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
