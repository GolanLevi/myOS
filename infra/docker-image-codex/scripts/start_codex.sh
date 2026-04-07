#!/usr/bin/env bash
set -euo pipefail

WORKDIR="${WORKSPACE_DIR:-/workspace}"
CODEX_SANDBOX_MODE="${CODEX_SANDBOX_MODE:-danger-full-access}"
CODEX_APPROVAL_POLICY="${CODEX_APPROVAL_POLICY:-never}"
CODEX_ENABLE_WEB_SEARCH="${CODEX_ENABLE_WEB_SEARCH:-false}"

mkdir -p "${WORKDIR}"
cd "${WORKDIR}"

args=()
if [[ -n "${CODEX_SANDBOX_MODE}" ]]; then
  args+=("--sandbox" "${CODEX_SANDBOX_MODE}")
fi
if [[ -n "${CODEX_APPROVAL_POLICY}" ]]; then
  args+=("--ask-for-approval" "${CODEX_APPROVAL_POLICY}")
fi
if [[ "${CODEX_ENABLE_WEB_SEARCH}" == "true" ]]; then
  args+=("--search")
fi

exec codex "${args[@]}"
