#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y \
  ca-certificates curl gnupg lsb-release jq git python3 python3-venv python3-pip \
  openssh-server unzip software-properties-common

# Docker
install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.asc ]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
fi
source /etc/os-release
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# OCI CLI
bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)" -- --accept-all-defaults >/root/oci-cli-install.log
ln -sf /root/bin/oci /usr/local/bin/oci || true

# Base accounts and dirs
groupadd -f myos-runtime
groupadd -f myos-operators
id -u myos-runtime >/dev/null 2>&1 || useradd -m -s /bin/bash -g myos-runtime myos-runtime
usermod -aG docker myos-runtime || true

install -d -m 0755 -o root -g root /srv/myos-app
install -d -m 0755 -o root -g root /srv/myos-config
install -d -m 0750 -o root -g myos-runtime /run/myos-secrets
install -d -m 0755 -o root -g root /srv/myos-state

echo "bootstrap-vm complete"
