#!/bin/bash
# One-shot: rename the systemd unit `gunicorn-baby` -> `gunicorn-baby-tracker`
# and update the matching NOPASSWD sudoers entry.
#
# Run once on the VPS as root after pulling the corresponding changes to
# bootstrap-vps.sh and .github/workflows/deploy.yml. Safe to re-run.

set -euo pipefail

OLD_SERVICE=gunicorn-baby
NEW_SERVICE=gunicorn-baby-tracker
OLD_UNIT=/etc/systemd/system/${OLD_SERVICE}.service
NEW_UNIT=/etc/systemd/system/${NEW_SERVICE}.service
SUDOERS=/etc/sudoers.d/baby-tracker-deploy
DEPLOY_USER=deploy

log() { echo -e "\033[1;34m==>\033[0m $*"; }

[ "$EUID" -eq 0 ] || { echo "Run as root (or with sudo)"; exit 1; }

if [ -f "$NEW_UNIT" ]; then
  log "$NEW_SERVICE already installed — nothing to do"
  exit 0
fi

[ -f "$OLD_UNIT" ] || { echo "$OLD_UNIT not found — cannot migrate"; exit 1; }

log "Stopping and disabling $OLD_SERVICE"
systemctl stop "$OLD_SERVICE" || true
systemctl disable "$OLD_SERVICE" || true

log "Moving unit file → $NEW_UNIT"
mv "$OLD_UNIT" "$NEW_UNIT"

log "Rewriting $SUDOERS for $NEW_SERVICE"
echo "$DEPLOY_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart $NEW_SERVICE" > "$SUDOERS"
chmod 440 "$SUDOERS"
visudo -cf "$SUDOERS" >/dev/null

log "Reloading systemd and starting $NEW_SERVICE"
systemctl daemon-reload
systemctl enable --now "$NEW_SERVICE"
systemctl restart "$NEW_SERVICE"

log "Verifying"
sleep 1
systemctl is-active --quiet "$NEW_SERVICE" \
  || { echo "$NEW_SERVICE failed to start — check: journalctl -u $NEW_SERVICE -n 50"; exit 1; }

log "Done. Status: $(systemctl is-active "$NEW_SERVICE")"
