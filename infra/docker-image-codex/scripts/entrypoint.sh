#!/usr/bin/env bash
set -euo pipefail

DEV_USERNAME="${DEV_USERNAME:-dev}"
DEV_UID="${DEV_UID:-1001}"
DEV_GID="${DEV_GID:-1001}"
SSH_PUBLIC_KEY="${SSH_PUBLIC_KEY:-}"
WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
CODEX_HOME="${CODEX_HOME:-/home/${DEV_USERNAME}}"
AUTO_ATTACH_TMUX="${AUTO_ATTACH_TMUX:-true}"
CODEX_AUTO_START="${CODEX_AUTO_START:-true}"
TMUX_SESSION_NAME="${TMUX_SESSION_NAME:-codex}"
CODEX_SANDBOX_MODE="${CODEX_SANDBOX_MODE:-danger-full-access}"
CODEX_APPROVAL_POLICY="${CODEX_APPROVAL_POLICY:-never}"
CODEX_ENABLE_WEB_SEARCH="${CODEX_ENABLE_WEB_SEARCH:-false}"
MYOS_OPERATOR_INSTRUCTIONS="${MYOS_OPERATOR_INSTRUCTIONS:-}"
GIT_REPO_URL="${GIT_REPO_URL:-}"
GIT_REF="${GIT_REF:-main}"
GIT_USER_NAME="${GIT_USER_NAME:-myOS Agent}"
GIT_USER_EMAIL="${GIT_USER_EMAIL:-myos-agent@users.noreply.github.com}"
GH_APP_PRIVATE_KEY_PATH="${GH_APP_PRIVATE_KEY_PATH:-/run/secrets/github_app_private_key.pem}"
DEV_PATH="/opt/pyenv/bin:/usr/local/bin:/usr/bin:/bin"

. /opt/bootstrap/sanitize-env.sh

# Create group/user if needed.
if ! getent group "${DEV_GID}" >/dev/null 2>&1; then
  groupadd -g "${DEV_GID}" "${DEV_USERNAME}"
fi
if ! id -u "${DEV_USERNAME}" >/dev/null 2>&1; then
  useradd -m -u "${DEV_UID}" -g "${DEV_GID}" -s /bin/bash "${DEV_USERNAME}"
fi
usermod -aG sudo "${DEV_USERNAME}" || true
printf '%s ALL=(ALL) NOPASSWD:ALL\n' "${DEV_USERNAME}" >/etc/sudoers.d/90-${DEV_USERNAME}
chmod 0440 /etc/sudoers.d/90-${DEV_USERNAME}

mkdir -p "${CODEX_HOME}/.ssh" "${WORKSPACE_DIR}" /run/secrets
chown -R "${DEV_USERNAME}:${DEV_GID}" "${CODEX_HOME}" "${WORKSPACE_DIR}"
chmod 700 "${CODEX_HOME}/.ssh"

if [[ -n "${SSH_PUBLIC_KEY}" ]]; then
  printf '%s\n' "${SSH_PUBLIC_KEY}" >"${CODEX_HOME}/.ssh/authorized_keys"
  chown "${DEV_USERNAME}:${DEV_GID}" "${CODEX_HOME}/.ssh/authorized_keys"
  chmod 600 "${CODEX_HOME}/.ssh/authorized_keys"
fi

# SSHD config.
mkdir -p /etc/ssh/sshd_config.d
cat >/etc/ssh/sshd_config.d/99-devbox.conf <<CFG
PasswordAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys
AllowUsers ${DEV_USERNAME}
X11Forwarding no
AllowTcpForwarding yes
UsePAM yes
PrintMotd no
AcceptEnv LANG LC_*
CFG

cat >/etc/profile.d/codex-devbox-env.sh <<EOF
export WORKSPACE_DIR="${WORKSPACE_DIR}"
export CODEX_HOME="${CODEX_HOME}"
export AUTO_ATTACH_TMUX="${AUTO_ATTACH_TMUX}"
export CODEX_AUTO_START="${CODEX_AUTO_START}"
export TMUX_SESSION_NAME="${TMUX_SESSION_NAME}"
export CODEX_SANDBOX_MODE="${CODEX_SANDBOX_MODE}"
export CODEX_APPROVAL_POLICY="${CODEX_APPROVAL_POLICY}"
export CODEX_ENABLE_WEB_SEARCH="${CODEX_ENABLE_WEB_SEARCH}"
export MYOS_OPERATOR_INSTRUCTIONS="${MYOS_OPERATOR_INSTRUCTIONS}"
export GIT_REPO_URL="${GIT_REPO_URL}"
export GIT_REF="${GIT_REF}"
export GITHUB_APP_ID="${GITHUB_APP_ID:-}"
export GITHUB_APP_INSTALLATION_ID="${GITHUB_APP_INSTALLATION_ID:-}"
export GH_APP_PRIVATE_KEY_PATH="${GH_APP_PRIVATE_KEY_PATH}"
export GITHUB_API_URL="${GITHUB_API_URL:-https://api.github.com}"
EOF
chmod 0644 /etc/profile.d/codex-devbox-env.sh

cat >"${CODEX_HOME}/AGENTS.md" <<EOF
# Codex Dev Box Instructions

This home directory is only the operator shell entrypoint.
Do your actual work in \`${WORKSPACE_DIR}\`.

## Required loading order
1. Read \`${WORKSPACE_DIR}/AGENTS.md\`
2. Read \`${WORKSPACE_DIR}/docs/instructions/10-project.md\`
3. If \`MYOS_OPERATOR_INSTRUCTIONS\` is set and \`${WORKSPACE_DIR}/docs/instructions/users/\${MYOS_OPERATOR_INSTRUCTIONS}.md\` exists, read that file too
4. Read \`${WORKSPACE_DIR}/docs/tasks/current-sprint.md\`

## Additional scope
- When editing under \`${WORKSPACE_DIR}/infra/docker-image-codex\`, also follow \`${WORKSPACE_DIR}/infra/docker-image-codex/AGENTS.md\`
- Keep secrets out of Git and out of Codex-visible repo paths
- Prefer the repo-managed bootstrap and docs over ad hoc container tweaks
EOF
chown "${DEV_USERNAME}:${DEV_GID}" "${CODEX_HOME}/AGENTS.md"
chmod 0644 "${CODEX_HOME}/AGENTS.md"

# Helpful shell setup.
if [[ ! -f "${CODEX_HOME}/.bashrc" ]]; then
  cp /opt/bootstrap/dev.bashrc "${CODEX_HOME}/.bashrc"
else
  if ! grep -q '^# Do nothing special for non-interactive shells\.$' "${CODEX_HOME}/.bashrc"; then
    tmp_bashrc="$(mktemp)"
    cat >"${tmp_bashrc}" <<'RC'
# Do nothing special for non-interactive shells.
# Required for VS Code Remote-SSH and ssh -T commands.
case $- in
  *i*) ;;
  *) return ;;
esac

RC
    cat "${CODEX_HOME}/.bashrc" >>"${tmp_bashrc}"
    mv "${tmp_bashrc}" "${CODEX_HOME}/.bashrc"
  fi

  if ! grep -q 'source /opt/bootstrap/on-login.sh' "${CODEX_HOME}/.bashrc"; then
    cat >>"${CODEX_HOME}/.bashrc" <<'RC'

# codex dev-box login behavior
source /opt/bootstrap/on-login.sh
RC
  fi
fi
chown "${DEV_USERNAME}:${DEV_GID}" "${CODEX_HOME}/.bashrc"
chmod 0644 "${CODEX_HOME}/.bashrc"

mkdir -p "${CODEX_HOME}/.codex"
CODEX_CONFIG_FILE="${CODEX_HOME}/.codex/config.toml"
touch "${CODEX_CONFIG_FILE}"
if ! grep -Fq "[projects.\"${CODEX_HOME}\"]" "${CODEX_CONFIG_FILE}"; then
  cat >>"${CODEX_CONFIG_FILE}" <<EOF

[projects."${CODEX_HOME}"]
trust_level = "trusted"
EOF
fi
if ! grep -Fq "[projects.\"${WORKSPACE_DIR}\"]" "${CODEX_CONFIG_FILE}"; then
  cat >>"${CODEX_CONFIG_FILE}" <<EOF

[projects."${WORKSPACE_DIR}"]
trust_level = "trusted"
EOF
fi
chown -R "${DEV_USERNAME}:${DEV_GID}" "${CODEX_HOME}/.codex"
chmod 0600 "${CODEX_CONFIG_FILE}"

# Git defaults for the dev user. Clear inherited helpers and use GitHub App only.
cat >"${CODEX_HOME}/.gitconfig" <<EOF
[user]
	name = ${GIT_USER_NAME}
	email = ${GIT_USER_EMAIL}
[init]
	defaultBranch = main
[pull]
	ff = only
[credential]
	helper =
	helper = /opt/bootstrap/git-credential-ghapp.sh
	interactive = never
[core]
	editor = vi
	askPass =
EOF
chown "${DEV_USERNAME}:${DEV_GID}" "${CODEX_HOME}/.gitconfig"
chmod 0600 "${CODEX_HOME}/.gitconfig"

# Bootstrap / update repo if configured.
if [[ -n "${GIT_REPO_URL}" ]]; then
  if ! DEV_USERNAME="${DEV_USERNAME}" \
    WORKSPACE_DIR="${WORKSPACE_DIR}" \
    CODEX_HOME="${CODEX_HOME}" \
    DEV_PATH="${DEV_PATH}" \
    GIT_REPO_URL="${GIT_REPO_URL}" \
    GIT_REF="${GIT_REF}" \
    BOOTSTRAP_GIT_SYNC_MODE="${BOOTSTRAP_GIT_SYNC_MODE:-resume}" \
    GITHUB_APP_ID="${GITHUB_APP_ID:-}" \
    GITHUB_APP_INSTALLATION_ID="${GITHUB_APP_INSTALLATION_ID:-}" \
    GH_APP_PRIVATE_KEY_PATH="${GH_APP_PRIVATE_KEY_PATH}" \
    GITHUB_API_URL="${GITHUB_API_URL:-https://api.github.com}" \
    /opt/bootstrap/bootstrap_repo.sh; then
    echo "[entrypoint] repo bootstrap failed for ${GIT_REPO_URL}@${GIT_REF}; starting SSH anyway so the box remains recoverable" >&2
  fi
fi

/usr/sbin/sshd -D -e
