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

# Helpful shell setup.
if ! grep -q 'source /opt/bootstrap/on-login.sh' "${CODEX_HOME}/.bashrc" 2>/dev/null; then
  cat >>"${CODEX_HOME}/.bashrc" <<'RC'

# codex dev-box login behavior
source /opt/bootstrap/on-login.sh
RC
fi
chown "${DEV_USERNAME}:${DEV_GID}" "${CODEX_HOME}/.bashrc"

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
  DEV_USERNAME="${DEV_USERNAME}" \
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
  /opt/bootstrap/bootstrap_repo.sh
fi

/usr/sbin/sshd -D -e
