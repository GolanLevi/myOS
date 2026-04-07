# OCI Codex Dev Box

Use this when you want the same Codex dev-box behavior on an OCI VM that you use locally.

## Goal
Keep local and cloud behavior the same:
- same `infra/docker-image-codex` image
- same `.env` keys
- same GitHub App auth path
- same Codex startup defaults
- same AGENTS loading model

## Minimum requirements
- Ubuntu VM
- Docker Engine + Docker Compose plugin
- SSH access
- a local `.env` file on the VM
- the GitHub App PEM stored on the VM outside the repo

## Setup
1. Clone your fork onto the VM.
2. Go to `infra/docker-image-codex`.
3. Copy `.env.example` to `.env`.
4. Set at least:
```text
SSH_PUBLIC_KEY=...
GITHUB_APP_ID=...
GITHUB_APP_INSTALLATION_ID=...
GH_APP_PRIVATE_KEY_FILE=/root/secrets/myos-github-app.private-key.pem
GIT_REPO_URL=https://github.com/amitkapl/myOS.git
GIT_REF=codex-devbox-autonomy-defaults
```
5. Start:
```bash
docker compose up -d --build
```

## Verify
```bash
ssh -T -p 2222 dev@127.0.0.1 sh -lc "echo ok"
ssh -p 2222 dev@127.0.0.1
```

Inside the container:
```bash
echo "$GITHUB_APP_ID"
echo "$GITHUB_APP_INSTALLATION_ID"
test -f /run/secrets/github_app_private_key.pem && echo key-ok
```

## OCI note
The existing `infra/terraform` area is for the application/runtime side, not this Codex dev box. For the dev box, the important part is simply a VM that can run the same Docker setup with the same `.env` values and mounted PEM file.
