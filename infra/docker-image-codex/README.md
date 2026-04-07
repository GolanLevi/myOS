# Codex GitOps Dev Box

Use this when you want Codex to work inside an isolated container with:
- SSH access for VS Code Remote-SSH
- persistent `/home/dev` and `/workspace` Docker volumes
- GitHub App auth for clone / fetch / pull / push
- full in-container Codex autonomy by default
- the repo AGENTS hierarchy plus optional operator-specific instructions

## How it works

### Persistent state
This setup uses **named Docker volumes** instead of bind mounting your repo:
- `codex-home` -> `/home/dev` (Codex login state, shell history, tmux state)
- `codex-workspace` -> `/workspace` (the cloned git repo and in-progress work)

Because the repo lives inside a Docker volume, the container is not coupled to your host files.

### GitOps source of truth
The long-term source of truth is:
1. Git for code, docs, AGENTS files, examples, and non-secret config
2. External secret handling for real credentials (not committed)
3. Docker named volumes for local continuity between restarts

For migration to cloud later:
- use the same image
- pass the same env vars
- mount the same secret file / secret source
- let the container clone the repo again
- optionally restore volumes if you want live tmux / Codex home continuity

## Files that SHOULD be in Git
- `Dockerfile`
- `docker-compose.yml`
- `scripts/*.sh`, `scripts/*.ps1`
- `AGENTS.md`
- `README.md`
- `.env.example`
- secret examples / templates only

## Files that SHOULD NOT be in Git
- GitHub App private key PEM
- real API keys / tokens
- real Codex auth material
- any private local-only overrides
- local `.env` files for operator-specific bootstrapping

## Auth model
This dev box is designed to authenticate GitHub operations through the mounted GitHub App private key and the values you set in `.env`.

It now actively clears inherited host-side credential paths such as:
- `GIT_ASKPASS`
- `SSH_AUTH_SOCK`
- `GH_TOKEN`
- `GITHUB_TOKEN`

That means the container should only know what you explicitly provide through:
- `.env`
- the mounted PEM file from `GH_APP_PRIVATE_KEY_FILE`
- persisted login state inside the container volumes

## Required before first start
- `SSH_PUBLIC_KEY`
- `GITHUB_APP_ID`
- `GITHUB_APP_INSTALLATION_ID`
- `GH_APP_PRIVATE_KEY_FILE`
- `GIT_REPO_URL`
- `GIT_REF`

Use your fork for day-to-day work. The repo URL and branch must match each other.

Example:
```text
GIT_REPO_URL=https://github.com/amitkapl/myOS.git
GIT_REF=codex-devbox-autonomy-defaults
```

## Optional operator-specific instruction file
Create a non-secret file under:
```text
docs/instructions/users/<name>.md
```

Then set in `.env`:
```text
MYOS_OPERATOR_INSTRUCTIONS=<name>
```

On login, the container home `AGENTS.md` tells Codex to load that file when it exists.

## Quick start

1. Copy `.env.example` to `.env`
2. Edit `.env`
3. Start:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
Unblock-File .\scripts\start.ps1
.\scripts\start.ps1
```
The script now waits for the container to stay running and performs an SSH probe automatically.

4. If the script succeeds, SSH should already be validated. Manual check:
```powershell
ssh -p 2222 dev@127.0.0.1
```
5. In VS Code, add to `~/.ssh/config`:
```text
Host codex-local
    HostName 127.0.0.1
    Port 2222
    User dev
    IdentityFile C:\Users\YOU\.ssh\id_ed25519
    StrictHostKeyChecking no
    UserKnownHostsFile NUL
```
6. VS Code -> `Remote-SSH: Connect to Host` -> `codex-local`
7. Open `/workspace`
8. First time only:
```bash
codex --login
```

If you changed auth/bootstrap behavior or the Dockerfile, rerun the same start command so Docker rebuilds the image.

## Runtime behavior

### First startup
- container creates the `dev` user
- SSH server starts
- repo is cloned into `/workspace`
- future git operations use the GitHub App via an on-demand installation token

### Later restarts
- repo volume remains
- home volume remains
- SSH login attaches you to the last tmux session
- if the workspace already exists, the default mode is `resume` (leave local work untouched)

Set in `.env` if you want different behavior:
- `BOOTSTRAP_GIT_SYNC_MODE=resume` -> do not touch existing repo
- `BOOTSTRAP_GIT_SYNC_MODE=fetch` -> fast-forward branch on startup
- `BOOTSTRAP_GIT_SYNC_MODE=reset` -> hard reset to remote branch on startup

## How to work safely
- let Codex work inside `/workspace`
- commit/push frequently so the branch is the portable state, not only the volume
- keep secrets out of the repo
- keep real secret files outside the repo and outside Codex-visible folders
- use the GitHub App path for git operations; do not rely on forwarded host credentials

## Tooling inside the box
The image includes a fuller local toolbox so Codex can operate with less manual setup:
- `gh`
- `ripgrep`
- `fd`
- build tools
- archive/network utilities

## Behavior
The container bootstraps Codex in a repo-controlled way:
- `.bashrc` is repaired to short-circuit non-interactive shells, which keeps `ssh -T` and VS Code Remote-SSH working
- `~/.codex/config.toml` is seeded with trusted entries for `/home/dev` and `/workspace`
- interactive SSH logins start Codex through a wrapper script, so sandbox and approval defaults come from `.env`
- login shells also export the GitHub App metadata from `.env`, so interactive `git fetch/pull/push` keeps using the same GitHub App path as bootstrap
- `/home/dev/AGENTS.md` points Codex to the repo AGENTS hierarchy and optional user-specific instructions selected by `.env`
- if repo bootstrap fails, the container still starts SSH so the box is recoverable instead of entering a restart loop

The default Codex CLI startup flags are:
```text
--sandbox danger-full-access
--ask-for-approval never
```

You can tune them in `.env`:
```text
CODEX_SANDBOX_MODE=danger-full-access
CODEX_APPROVAL_POLICY=never
CODEX_ENABLE_WEB_SEARCH=false
MYOS_OPERATOR_INSTRUCTIONS=amit
```

## Environment parity
Use the same Git-managed files for both local Docker and cloud-hosted dev boxes:
- same `infra/docker-image-codex` image build context
- same `.env` keys and mounted GitHub App PEM
- same named-volume style persistence goals, adapted to the target provider
- same Codex startup wrapper and `AGENTS.md` loading model

For the cloud-hosted version, use the OCI guide in [docs/OCI-DEVBOX.md](/workspace/infra/docker-image-codex/docs/OCI-DEVBOX.md). The same pattern can be applied to any cloud provider that can run Docker on a VM.
