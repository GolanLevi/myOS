#!/usr/bin/env bash
set -euo pipefail

DEV_USERNAME="${DEV_USERNAME:-dev}"
WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
CODEX_HOME="${CODEX_HOME:-/home/${DEV_USERNAME}}"
DEV_PATH="${DEV_PATH:-/opt/pyenv/bin:/usr/local/bin:/usr/bin:/bin}"
GIT_REPO_URL="${GIT_REPO_URL:-}"
GIT_REF="${GIT_REF:-main}"
BOOTSTRAP_GIT_SYNC_MODE="${BOOTSTRAP_GIT_SYNC_MODE:-resume}"

run_as_dev() {
  env -i \
    HOME="${CODEX_HOME}" \
    USER="${DEV_USERNAME}" \
    LOGNAME="${DEV_USERNAME}" \
    SHELL=/bin/bash \
    PATH="${DEV_PATH}" \
    WORKSPACE_DIR="${WORKSPACE_DIR}" \
    GITHUB_APP_ID="${GITHUB_APP_ID:-}" \
    GITHUB_APP_INSTALLATION_ID="${GITHUB_APP_INSTALLATION_ID:-}" \
    GH_APP_PRIVATE_KEY_PATH="${GH_APP_PRIVATE_KEY_PATH:-/run/secrets/github_app_private_key.pem}" \
    GITHUB_API_URL="${GITHUB_API_URL:-https://api.github.com}" \
    GIT_TERMINAL_PROMPT=0 \
    su - "${DEV_USERNAME}" -c "$1"
}

if [[ -z "${GIT_REPO_URL}" ]]; then
  echo "[bootstrap] GIT_REPO_URL not set; skipping repo bootstrap"
  exit 0
fi

echo "[bootstrap] target repo=${GIT_REPO_URL} ref=${GIT_REF} mode=${BOOTSTRAP_GIT_SYNC_MODE}"

if [[ ! -d "${WORKSPACE_DIR}/.git" ]]; then
  echo "[bootstrap] cloning ${GIT_REPO_URL} into ${WORKSPACE_DIR}"
  rm -rf "${WORKSPACE_DIR:?}"/* "${WORKSPACE_DIR:?}"/.[!.]* "${WORKSPACE_DIR:?}"/..?* 2>/dev/null || true
  run_as_dev "git clone --branch '${GIT_REF}' '${GIT_REPO_URL}' '${WORKSPACE_DIR}'"
else
  echo "[bootstrap] repo already exists at ${WORKSPACE_DIR}; mode=${BOOTSTRAP_GIT_SYNC_MODE}"
  if [[ "${BOOTSTRAP_GIT_SYNC_MODE}" == "fetch" ]]; then
    run_as_dev "cd '${WORKSPACE_DIR}' && git fetch --all --prune && git checkout '${GIT_REF}' && git pull --ff-only origin '${GIT_REF}'"
  elif [[ "${BOOTSTRAP_GIT_SYNC_MODE}" == "reset" ]]; then
    run_as_dev "cd '${WORKSPACE_DIR}' && git fetch --all --prune && git checkout '${GIT_REF}' && git reset --hard 'origin/${GIT_REF}'"
  fi
fi

# Ensure current branch if it already exists.
run_as_dev "cd '${WORKSPACE_DIR}' && git rev-parse --is-inside-work-tree >/dev/null"
