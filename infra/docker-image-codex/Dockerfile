FROM node:22-bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/opt/pyenv/bin:${PATH}"

ARG DEV_USERNAME=dev
ARG DEV_UID=1001
ARG DEV_GID=1001

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    sudo \
    git \
    tmux \
    python3 \
    python3-venv \
    python3-pip \
    ca-certificates \
    curl \
    jq \
    less \
    procps \
    nano \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/pyenv \
 && /opt/pyenv/bin/pip install --no-cache-dir --upgrade pip \
 && /opt/pyenv/bin/pip install --no-cache-dir requests pyjwt cryptography \
 && npm install -g @openai/codex

RUN mkdir -p /var/run/sshd /opt/bootstrap /workspace /run/secrets /var/log/mybox \
 && chmod 0755 /workspace

# Create default dev user and home at build time so files can be placed safely.
RUN groupadd -g ${DEV_GID} ${DEV_USERNAME} \
 && useradd -m -u ${DEV_UID} -g ${DEV_GID} -s /bin/bash ${DEV_USERNAME} \
 && usermod -aG sudo ${DEV_USERNAME} \
 && echo "${DEV_USERNAME} ALL=(ALL) NOPASSWD:ALL" >/etc/sudoers.d/${DEV_USERNAME} \
 && chmod 0440 /etc/sudoers.d/${DEV_USERNAME} \
 && mkdir -p /home/${DEV_USERNAME}/.ssh \
 && chown -R ${DEV_USERNAME}:${DEV_USERNAME} /home/${DEV_USERNAME} /workspace

# SSH server config
RUN sed -i 's/#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config \
 && sed -i 's/#\?PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config \
 && sed -i 's/#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config \
 && printf '\nAllowTcpForwarding yes\nGatewayPorts no\nX11Forwarding no\nClientAliveInterval 60\nClientAliveCountMax 10\n' >> /etc/ssh/sshd_config

COPY scripts/entrypoint.sh /opt/bootstrap/entrypoint.sh
COPY scripts/bootstrap_repo.sh /opt/bootstrap/bootstrap_repo.sh
COPY scripts/git-credential-ghapp.sh /opt/bootstrap/git-credential-ghapp.sh
COPY scripts/github_app_token.py /opt/bootstrap/github_app_token.py
COPY scripts/on-login.sh /opt/bootstrap/on-login.sh

RUN chmod +x /opt/bootstrap/*.sh

# Keep a template copy and also install it for the default dev user.
RUN cat > /opt/bootstrap/dev.bashrc <<'EOF'
# Do nothing special for non-interactive shells.
# Required for VS Code Remote-SSH and ssh -T commands.
case $- in
  *i*) ;;
  *) return ;;
esac

# codex dev-box login behavior
if [[ -n "${SSH_CONNECTION:-}" ]] && [[ -t 0 ]] && [[ -t 1 ]] && [[ -z "${VSCODE_IPC_HOOK_CLI:-}" ]]; then
  tmux attach -t codex || tmux new -s codex "cd /workspace && codex"
fi
EOF

RUN cp /opt/bootstrap/dev.bashrc /home/${DEV_USERNAME}/.bashrc \
 && chown ${DEV_USERNAME}:${DEV_USERNAME} /home/${DEV_USERNAME}/.bashrc \
 && chmod 0644 /home/${DEV_USERNAME}/.bashrc

EXPOSE 22

ENTRYPOINT ["/opt/bootstrap/entrypoint.sh"]