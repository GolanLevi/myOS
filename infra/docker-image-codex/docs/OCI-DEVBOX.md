# OCI Codex Dev Box Guide

This guide deploys the same Codex dev-box pattern used locally under `infra/docker-image-codex` onto an OCI VM.

The goal is parity:
- same repo-managed Docker build context
- same `.env` keys
- same GitHub App auth path
- same Codex startup behavior
- same `AGENTS.md` loading model

## What this guide is for
- a cloud-hosted Codex development box
- remote SSH access to the box
- the same container behavior as the local Docker setup

## What this guide is not for
- production deployment of the myOS application runtime
- provider-specific secret manager automation
- replacing the existing runtime GitOps flow under `infra/terraform`

The current `infra/terraform` directory is for the application/runtime side. Use this guide for the Codex development box itself.

## Required inputs
Prepare these values locally and keep them out of Git:
- `SSH_PUBLIC_KEY`
- `GITHUB_APP_ID`
- `GITHUB_APP_INSTALLATION_ID`
- `GH_APP_PRIVATE_KEY_FILE`
- `GIT_REPO_URL`
- `GIT_REF`
- optional `MYOS_OPERATOR_INSTRUCTIONS`

## VM requirements
Any cloud provider is acceptable if it gives you:
- Ubuntu or another modern Linux VM
- Docker Engine plus Docker Compose plugin
- SSH access
- a persistent disk for `/home/dev` and `/workspace`
- a secure way to place the GitHub App PEM on the VM without committing it

OCI-specific recommendation:
- Ubuntu 24.04
- public IP with TCP 22 open only to your trusted source ranges
- attached block volume or sufficiently sized boot volume for Docker image layers and workspace persistence

## OCI flow
1. Provision an Ubuntu VM.
2. Install Docker Engine and Docker Compose plugin.
3. Clone your repo onto the VM.
4. Copy `infra/docker-image-codex/.env.example` to a local `.env` on the VM:
   - `infra/docker-image-codex/.env`
5. Fill in the `.env` values exactly as you would locally.
6. Place the GitHub App private key PEM on the VM outside the repo, for example:
   - `/root/secrets/myos-github-app.private-key.pem`
7. Point `GH_APP_PRIVATE_KEY_FILE` at that VM-local path.
8. Start the dev box from `infra/docker-image-codex`:
```bash
docker compose up -d --build
```
9. SSH into the container through the published SSH port and verify:
```bash
echo "$GITHUB_APP_ID"
echo "$GITHUB_APP_INSTALLATION_ID"
test -f /run/secrets/github_app_private_key.pem && echo key-ok
```

## Persistent state model
Keep the same state split as local:
- Docker volume for `/home/dev`
- Docker volume for `/workspace`
- Git as the durable source of truth for code and non-secret config
- local VM file for the GitHub App PEM

If you later automate this on OCI:
- keep the PEM outside Git
- inject it at provision time or through a secret delivery step
- keep `.env` local to the VM and ignored by Git

## Recommended `.env` values
For full in-container Codex autonomy:
```text
CODEX_SANDBOX_MODE=danger-full-access
CODEX_APPROVAL_POLICY=never
```

For user-specific guidance:
```text
MYOS_OPERATOR_INSTRUCTIONS=amit
```

This loads `docs/instructions/users/amit.md` when present.

## Behavior parity checklist
After startup, confirm:
- non-interactive SSH works: `ssh -T ... sh -lc "echo ok"`
- interactive SSH starts or resumes Codex in tmux
- `/home/dev/AGENTS.md` exists
- `/home/dev/.codex/config.toml` contains trusted entries for `/home/dev` and `/workspace`
- `git fetch` and `git push` work through the GitHub App helper

## Mapping to other cloud providers
The provider-specific pieces are only:
- VM creation
- firewall rules
- persistent disk choices
- secure placement of the PEM file

The rest stays the same:
- same repo
- same image
- same `.env`
- same container startup command
- same Codex behavior
