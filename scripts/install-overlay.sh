#!/usr/bin/env bash
set -euo pipefail

OVERLAY_SRC="${1:-/tmp/myos-overlay}"
INSTALL_ROOT="/opt/myos-overlay"

install -d -m 0755 "$INSTALL_ROOT"
rsync -a --delete "$OVERLAY_SRC"/ "$INSTALL_ROOT"/

install -m 0644 "$INSTALL_ROOT/systemd/myos-deploy.service" /etc/systemd/system/myos-deploy.service
install -m 0644 "$INSTALL_ROOT/systemd/myos-deploy.timer" /etc/systemd/system/myos-deploy.timer
install -m 0644 "$INSTALL_ROOT/systemd/myos-reconcile.service" /etc/systemd/system/myos-reconcile.service

install -m 0755 "$INSTALL_ROOT/scripts/deploy-runtime.sh" /usr/local/bin/deploy-runtime.sh
install -m 0755 "$INSTALL_ROOT/scripts/fetch-secrets-from-vault.sh" /usr/local/bin/fetch-secrets-from-vault.sh
install -m 0755 "$INSTALL_ROOT/scripts/reconcile-operators.py" /usr/local/bin/reconcile-operators.py
install -m 0755 "$INSTALL_ROOT/scripts/github_app_token.py" /usr/local/bin/github_app_token.py

# Seed default config if not present
install -d -m 0755 /srv/myos-config
[ -f /srv/myos-config/desired-state.json ] || install -m 0644 "$INSTALL_ROOT/config/desired-state.json" /srv/myos-config/desired-state.json
[ -f /srv/myos-config/app-config.json ] || install -m 0644 "$INSTALL_ROOT/config/app-config.json" /srv/myos-config/app-config.json
[ -f /srv/myos-config/secret-manifest.json ] || install -m 0644 "$INSTALL_ROOT/config/secret-manifest.json" /srv/myos-config/secret-manifest.json

systemctl daemon-reload
systemctl enable myos-deploy.timer
systemctl start myos-deploy.timer
systemctl start myos-reconcile.service || true

echo "install-overlay complete"
