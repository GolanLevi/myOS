#!/usr/bin/env bash
set -euo pipefail

action="${1:-get}"
if [[ "${action}" != "get" ]]; then
  exit 0
fi

if [[ -z "${GITHUB_APP_ID:-}" || -z "${GITHUB_APP_INSTALLATION_ID:-}" ]]; then
  exit 0
fi

if [[ ! -f "${GH_APP_PRIVATE_KEY_PATH:-/run/secrets/github_app_private_key.pem}" ]]; then
  exit 0
fi

token="$(/opt/pyenv/bin/python /opt/bootstrap/github_app_token.py)"
if [[ -z "${token}" ]]; then
  exit 1
fi

printf 'username=x-access-token\n'
printf 'password=%s\n' "${token}"
