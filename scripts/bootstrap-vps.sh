#!/bin/bash
# Baby Tracker — VPS bootstrap script
#
# Provisions a fresh Ubuntu/Debian VPS: installs dependencies, sets up
# PostgreSQL + Nginx + Gunicorn + Let's Encrypt, clones the repo, creates
# the .env, runs migrations, and enables the systemd service.
#
# Run ONCE on a fresh VPS as root (or with sudo). Clone the repo first,
# then either copy `scripts/bootstrap.env.example` to `scripts/bootstrap.env`
# and fill it in, or pass values as env vars:
#   sudo -E bash scripts/bootstrap-vps.sh
#
# REPO_URL is auto-detected from the checked-out repo. Any missing required
# values will be prompted for interactively.
#
# Safe to re-run: each step checks whether it's already done.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── Config ───────────────────────────────────────────────────────────────────
# Precedence: existing shell env vars > scripts/bootstrap.env > scripts/bootstrap.env.example
# Each file-loader only sets vars that aren't already set, so callers can
# override anything with `FOO=bar sudo -E bash scripts/bootstrap-vps.sh`.
load_env_file() {
  local file="$1"
  [ -f "$file" ] || return 0
  while IFS='=' read -r key value; do
    [[ "$key" =~ ^[[:space:]]*(#|$) ]] && continue
    key="${key// /}"
    value="${value%\"}"; value="${value#\"}"
    value="${value%\'}"; value="${value#\'}"
    [ -z "${!key:-}" ] && export "$key=$value"
  done < "$file"
}

load_env_file "$SCRIPT_DIR/bootstrap.env"
load_env_file "$SCRIPT_DIR/bootstrap.env.example"

# Auto-detect REPO_URL from the checked-out repo if not set.
if [ -z "${REPO_URL:-}" ] && git -C "$SCRIPT_DIR" rev-parse --is-inside-work-tree &>/dev/null; then
  REPO_URL="$(git -C "$SCRIPT_DIR" remote get-url origin 2>/dev/null || true)"
fi

# ─── Helpers ──────────────────────────────────────────────────────────────────
log()  { echo -e "\033[1;34m==>\033[0m $*"; }
warn() { echo -e "\033[1;33m!!\033[0m  $*"; }
die()  { echo -e "\033[1;31mXX\033[0m  $*" >&2; exit 1; }

prompt() {
  local var="$1" message="$2" secret="${3:-false}"
  if [ -z "${!var}" ]; then
    if [ "$secret" = "true" ]; then
      read -rsp "$message: " "$var"; echo
    else
      read -rp "$message: " "$var"
    fi
    export "$var"
  fi
}

# ─── Preflight ────────────────────────────────────────────────────────────────
[ "$EUID" -eq 0 ] || die "Run as root (or with sudo)"
command -v apt-get >/dev/null || die "This script only supports Debian/Ubuntu"

log "Baby Tracker VPS bootstrap"
echo

prompt DOMAIN "Subdomain (e.g. bb.example.com)"
prompt EMAIL "Email for Let's Encrypt notices"
prompt REPO_URL "Git repo URL to clone"
prompt ALLOWED_EMAILS "Allowed login emails (comma-separated)"
prompt GOOGLE_CLIENT_ID "Google OAuth Client ID"
prompt GOOGLE_CLIENT_SECRET "Google OAuth Client Secret" true
prompt R2_ACCESS_KEY "R2 Access Key ID"
prompt R2_SECRET_KEY "R2 Secret Access Key" true
prompt R2_ENDPOINT "R2 endpoint URL (https://<account>.r2.cloudflarestorage.com)"

if [ -z "$DB_PASSWORD" ]; then
  DB_PASSWORD="$(openssl rand -base64 24 | tr -d '+/=' | head -c 32)"
  log "Generated DB password (stored in .env on server)"
fi

# ─── System packages ──────────────────────────────────────────────────────────
log "Installing system packages…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  "$PYTHON_BIN" "$PYTHON_BIN-venv" "$PYTHON_BIN-dev" \
  postgresql postgresql-contrib \
  nginx certbot python3-certbot-nginx \
  git curl ufw fail2ban

# ─── Deploy user ──────────────────────────────────────────────────────────────
if id "$DEPLOY_USER" &>/dev/null; then
  log "Deploy user '$DEPLOY_USER' already exists"
else
  log "Creating deploy user '$DEPLOY_USER'…"
  adduser --disabled-password --gecos "" "$DEPLOY_USER"
  usermod -aG www-data "$DEPLOY_USER"
fi

# Propagate root's authorized_keys so you can SSH in as deploy
if [ -f /root/.ssh/authorized_keys ] && [ ! -f "/home/$DEPLOY_USER/.ssh/authorized_keys" ]; then
  log "Copying SSH keys to deploy user"
  mkdir -p "/home/$DEPLOY_USER/.ssh"
  cp /root/.ssh/authorized_keys "/home/$DEPLOY_USER/.ssh/authorized_keys"
  chown -R "$DEPLOY_USER:$DEPLOY_USER" "/home/$DEPLOY_USER/.ssh"
  chmod 700 "/home/$DEPLOY_USER/.ssh"
  chmod 600 "/home/$DEPLOY_USER/.ssh/authorized_keys"
fi

# Sudoers: allow gunicorn restart without password (for CI)
SUDOERS_FILE="/etc/sudoers.d/baby-tracker-deploy"
if [ ! -f "$SUDOERS_FILE" ]; then
  log "Allowing '$DEPLOY_USER' to restart gunicorn without password"
  echo "$DEPLOY_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart gunicorn-baby" > "$SUDOERS_FILE"
  chmod 440 "$SUDOERS_FILE"
fi

# ─── PostgreSQL ───────────────────────────────────────────────────────────────
log "Setting up PostgreSQL…"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"

sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

sudo -u postgres psql -d "$DB_NAME" -c "GRANT ALL ON SCHEMA public TO $DB_USER;" >/dev/null

# ─── Tailwind CLI ─────────────────────────────────────────────────────────────
if [ ! -x /usr/local/bin/tailwindcss ]; then
  log "Installing Tailwind CSS CLI…"
  ARCH=$(dpkg --print-architecture)
  if [ "$ARCH" = "arm64" ]; then TW_ARCH=linux-arm64; else TW_ARCH=linux-x64; fi
  curl -sSL "https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-${TW_ARCH}" \
    -o /usr/local/bin/tailwindcss
  chmod +x /usr/local/bin/tailwindcss
fi

# ─── Clone repo ───────────────────────────────────────────────────────────────
mkdir -p "$APP_DIR"
chown "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR"

if [ ! -d "$APP_DIR/.git" ]; then
  log "Cloning $REPO_URL"
  sudo -u "$DEPLOY_USER" git clone "$REPO_URL" "$APP_DIR"
else
  log "Repo already present, pulling latest"
  sudo -u "$DEPLOY_USER" git -C "$APP_DIR" pull --ff-only
fi

# ─── venv + deps ──────────────────────────────────────────────────────────────
if [ ! -d "$APP_DIR/venv" ]; then
  log "Creating Python venv…"
  sudo -u "$DEPLOY_USER" "$PYTHON_BIN" -m venv "$APP_DIR/venv"
fi

log "Installing production dependencies…"
sudo -u "$DEPLOY_USER" "$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
sudo -u "$DEPLOY_USER" "$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements/production.txt"

# ─── .env ─────────────────────────────────────────────────────────────────────
ENV_FILE="$APP_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  log "Writing $ENV_FILE"
  SECRET_KEY="$($APP_DIR/venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(50))')"
  cat > "$ENV_FILE" <<EOF
SECRET_KEY=$SECRET_KEY
DEBUG=False
ALLOWED_HOSTS=$DOMAIN
ALLOWED_LOGIN_EMAILS=$ALLOWED_EMAILS
DATABASE_URL=postgres://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME
AWS_ACCESS_KEY_ID=$R2_ACCESS_KEY
AWS_SECRET_ACCESS_KEY=$R2_SECRET_KEY
AWS_STORAGE_BUCKET_NAME=$R2_BUCKET
AWS_S3_ENDPOINT_URL=$R2_ENDPOINT
AWS_S3_REGION_NAME=auto
GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET=$GOOGLE_CLIENT_SECRET
DJANGO_SETTINGS_MODULE=config.settings.production
EOF
  chown "$DEPLOY_USER:$DEPLOY_USER" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
else
  log ".env already exists, leaving alone"
fi

# ─── Build assets + migrate ───────────────────────────────────────────────────
log "Building Tailwind CSS…"
sudo -u "$DEPLOY_USER" tailwindcss -i "$APP_DIR/static/css/input.css" -o "$APP_DIR/static/css/output.css" --minify

log "Running migrations…"
sudo -u "$DEPLOY_USER" bash -c "cd $APP_DIR && set -a && source .env && set +a && venv/bin/python manage.py migrate --no-input"

log "Collecting static files…"
sudo -u "$DEPLOY_USER" bash -c "cd $APP_DIR && set -a && source .env && set +a && venv/bin/python manage.py collectstatic --no-input"

log "Setting Site domain…"
sudo -u "$DEPLOY_USER" bash -c "cd $APP_DIR && set -a && source .env && set +a && venv/bin/python manage.py shell -c \"
from django.contrib.sites.models import Site
Site.objects.update_or_create(id=1, defaults={'domain': '$DOMAIN', 'name': 'Baby Tracker'})
\""

# ─── Gunicorn systemd service ─────────────────────────────────────────────────
SERVICE_FILE="/etc/systemd/system/gunicorn-baby.service"
if [ ! -f "$SERVICE_FILE" ]; then
  log "Creating gunicorn-baby systemd service…"
  cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Baby Tracker Gunicorn
After=network.target postgresql.service

[Service]
User=$DEPLOY_USER
Group=www-data
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/gunicorn config.wsgi:application \\
    --bind unix:$APP_DIR/gunicorn.sock \\
    --workers 3 \\
    --timeout 120
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
fi

systemctl enable --now gunicorn-baby
systemctl restart gunicorn-baby

# ─── Nginx ────────────────────────────────────────────────────────────────────
NGINX_CONF="/etc/nginx/sites-available/baby-tracker"
if [ ! -f "$NGINX_CONF" ]; then
  log "Creating nginx config…"
  cat > "$NGINX_CONF" <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    location /static/ {
        alias $APP_DIR/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://unix:$APP_DIR/gunicorn.sock;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        client_max_body_size 20M;
    }
}
EOF
  ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/baby-tracker
  rm -f /etc/nginx/sites-enabled/default
fi

nginx -t
systemctl reload nginx

# ─── Let's Encrypt ────────────────────────────────────────────────────────────
if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
  log "Issuing Let's Encrypt certificate for $DOMAIN…"
  certbot --nginx --non-interactive --agree-tos --redirect \
    --email "$EMAIL" -d "$DOMAIN"
else
  log "Certificate already exists for $DOMAIN"
fi

# ─── Firewall ─────────────────────────────────────────────────────────────────
log "Configuring firewall (UFW)…"
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow "Nginx Full"
ufw --force enable

# ─── Done ─────────────────────────────────────────────────────────────────────
echo
log "Bootstrap complete!"
echo
echo "  App URL:     https://$DOMAIN"
echo "  App dir:     $APP_DIR"
echo "  Deploy user: $DEPLOY_USER"
echo "  DB:          postgres://$DB_USER:***@localhost:5432/$DB_NAME"
echo
echo "Next steps (manual):"
echo "  1. Create a superuser:"
echo "       sudo -u $DEPLOY_USER bash -c 'cd $APP_DIR && set -a && source .env && set +a && venv/bin/python manage.py createsuperuser'"
echo "  2. Add https://$DOMAIN/accounts/google/login/callback/ to your Google OAuth redirect URIs"
echo "  3. Add GitHub secrets: VPS_HOST, VPS_USER=$DEPLOY_USER, VPS_SSH_KEY (deploy SSH private key)"
echo "  4. Point DNS A record for $DOMAIN to this server's IP"
echo "  5. Visit https://$DOMAIN and log in via Google"
