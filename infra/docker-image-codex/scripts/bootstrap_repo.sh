#!/usr/bin/env bash
set -euo pipefail

DEV_USERNAME="${DEV_USERNAME:-dev}"
WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
GIT_REPO_URL="${GIT_REPO_URL:-}"
GIT_REF="${GIT_REF:-main}"
BOOTSTRAP_GIT_SYNC_MODE="${BOOTSTRAP_GIT_SYNC_MODE:-resume}"

if [[ -z "${GIT_REPO_URL}" ]]; then
  echo "[bootstrap] GIT_REPO_URL not set; skipping repo bootstrap"
  exit 0
fi

if [[ ! -d "${WORKSPACE_DIR}/.git" ]]; then
  echo "[bootstrap] cloning ${GIT_REPO_URL} into ${WORKSPACE_DIR}"
  rm -rf "${WORKSPACE_DIR:?}"/* "${WORKSPACE_DIR:?}"/.[!.]* "${WORKSPACE_DIR:?}"/..?* 2>/dev/null || true
  su - "${DEV_USERNAME}" -c "git clone --branch '${GIT_REF}' '${GIT_REPO_URL}' '${WORKSPACE_DIR}'"
else
  echo "[bootstrap] repo already exists at ${WORKSPACE_DIR}; mode=${BOOTSTRAP_GIT_SYNC_MODE}"
  if [[ "${BOOTSTRAP_GIT_SYNC_MODE}" == "fetch" ]]; then
    su - "${DEV_USERNAME}" -c "cd '${WORKSPACE_DIR}' && git fetch --all --prune && git checkout '${GIT_REF}' && git pull --ff-only origin '${GIT_REF}'"
  elif [[ "${BOOTSTRAP_GIT_SYNC_MODE}" == "reset" ]]; then
    su - "${DEV_USERNAME}" -c "cd '${WORKSPACE_DIR}' && git fetch --all --prune && git checkout '${GIT_REF}' && git reset --hard 'origin/${GIT_REF}'"
  fi
fi

# Ensure current branch if it already exists.
su - "${DEV_USERNAME}" -c "cd '${WORKSPACE_DIR}' && git rev-parse --is-inside-work-tree >/dev/null"
