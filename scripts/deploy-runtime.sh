#!/usr/bin/env bash
set -euo pipefail

DESIRED="/srv/myos-config/desired-state.json"
if [ ! -f "$DESIRED" ]; then
  echo "Missing desired-state file: $DESIRED"
  exit 1
fi

APP_ROOT=$(jq -r '.machine.paths.app_root' "$DESIRED")
RUNTIME_USER=$(jq -r '.machine.runtime_user' "$DESIRED")
BRANCH=$(jq -r '.gitops.runtime_branch' "$DESIRED")
COMPOSE_FILE=$(jq -r '.deployment.compose_file' "$DESIRED")

install -d -m 0755 "$APP_ROOT"
python3 /usr/local/bin/reconcile-operators.py || true
/usr/local/bin/fetch-secrets-from-vault.sh

# Clone/pull repo using GitHub App installation token if available.
if [ -f /run/myos-secrets/github_app_id ] && [ -f /run/myos-secrets/github_app_private_key.pem ] && [ -f /run/myos-secrets/github_app_installation_id ]; then
  TOKEN=$(python3 /usr/local/bin/github_app_token.py)
  REPO_URL=$(jq -r '.gitops.repo_url // empty' "$DESIRED")
  if [ -n "$REPO_URL" ]; then
    AUTH_URL=$(echo "$REPO_URL" | sed "s#https://#https://x-access-token:${TOKEN}@#")
    if [ ! -d "$APP_ROOT/.git" ]; then
      sudo -u "$RUNTIME_USER" git clone "$AUTH_URL" "$APP_ROOT"
    fi
    pushd "$APP_ROOT" >/dev/null
    sudo -u "$RUNTIME_USER" git remote set-url origin "$AUTH_URL"
    sudo -u "$RUNTIME_USER" git fetch origin
    sudo -u "$RUNTIME_USER" git checkout "$BRANCH"
    sudo -u "$RUNTIME_USER" git reset --hard "origin/$BRANCH"
    popd >/dev/null
  fi
fi

# Deploy if compose file exists.
if [ -f "$APP_ROOT/$COMPOSE_FILE" ]; then
  pushd "$APP_ROOT" >/dev/null
  docker compose -f "$COMPOSE_FILE" up -d --build
  popd >/dev/null
fi

echo "runtime deploy complete"
