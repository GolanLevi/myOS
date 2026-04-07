# Codex GitOps Dev Box

This runs Codex inside a Docker container with:
- SSH access for VS Code Remote-SSH
- persistent home directory (`codex-home` volume)
- persistent workspace (`codex-workspace` volume)
- repo clone/update inside the container (no host repo bind mount)
- GitHub App authentication for clone / fetch / pull / push
- stripped inherited host git/token/SSH-agent credentials at runtime
- tmux auto-resume so reconnecting over SSH returns you to the last Codex session
- a home-level `AGENTS.md` that points Codex at the repo AGENTS hierarchy and optional user-specific instructions

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

## Critical information you need before first start

### 1) SSH public key contents
Used so you can SSH from VS Code / PowerShell into the container.

PowerShell:
```powershell
Get-Content $HOME\.ssh\id_ed25519.pub
```
Paste the **contents** into `.env` as `SSH_PUBLIC_KEY=`.

### 2) GitHub App ID
GitHub -> Settings -> Developer settings -> GitHub Apps -> your app -> **App ID**

### 3) GitHub App installation ID
Install the app on the repo/account, then get the installation ID from the installation URL or API.
A simple route is:
- GitHub App page -> **Install App** / **Configure**
- choose the repo
- copy the installation ID from the URL if shown, or query it with GitHub API / browser dev tools.

### 4) GitHub App private key PEM
Download it from the GitHub App page after generating a private key.
Store it outside the repo, for example:
```text
C:/Users/YOU/secrets/myos-github-app.private-key.pem
```
Then put that path into `.env` as `GH_APP_PRIVATE_KEY_FILE=`.

### 5) Repo URL and branch
For example:
```text
GIT_REPO_URL=https://github.com/GolanLevi/myOS.git
GIT_REF=chatGPT-amit/myos-infra
```
Use a working branch while testing. Switch to `main` only after merge.

### 6) Optional operator-specific instruction file
Create a non-secret file under:
```text
docs/instructions/users/<name>.md
```

Then set in `.env`:
```text
MYOS_OPERATOR_INSTRUCTIONS=<name>
```

On login, the container home `AGENTS.md` tells Codex to load that file when it exists.

### 7) Codex login
First time only, after SSHing in:
```bash
codex --login
```
That login state persists in the `codex-home` volume.

## Quick start

1. Copy `.env.example` to `.env`
2. Edit `.env`
3. Recommended defaults for this dev box:
```text
CODEX_SANDBOX_MODE=danger-full-access
CODEX_APPROVAL_POLICY=never
```
These make Codex run with full in-container permissions and no interactive approval prompts.
4. Start:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
Unblock-File .\scripts\start.ps1
.\scripts\start.ps1
```
5. Test SSH:
```powershell
ssh -p 2222 dev@127.0.0.1
```
6. In VS Code, add to `~/.ssh/config`:
```text
Host codex-local
    HostName 127.0.0.1
    Port 2222
    User dev
    IdentityFile C:\Users\YOU\.ssh\id_ed25519
    StrictHostKeyChecking no
    UserKnownHostsFile NUL
```
7. VS Code -> `Remote-SSH: Connect to Host` -> `codex-local`
8. Open `/workspace`
9. In the terminal:
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

## Codex startup defaults
The container now bootstraps Codex in a repo-controlled way so new and resumed volumes behave consistently:
- `.bashrc` is repaired to short-circuit non-interactive shells, which keeps `ssh -T` and VS Code Remote-SSH working
- `~/.codex/config.toml` is seeded with trusted entries for `/home/dev` and `/workspace`
- interactive SSH logins start Codex through a wrapper script, so sandbox and approval defaults come from `.env`
- login shells also export the GitHub App metadata from `.env`, so interactive `git fetch/pull/push` keeps using the same GitHub App path as bootstrap
- `/home/dev/AGENTS.md` points Codex to the repo AGENTS hierarchy and optional user-specific instructions selected by `.env`

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

Useful examples:
- `CODEX_APPROVAL_POLICY=on-request` if you later want Codex to pause before some commands
- `CODEX_SANDBOX_MODE=workspace-write` if you want a safer default than full in-container access
- `CODEX_ENABLE_WEB_SEARCH=true` if you want live web search available by default

After changing these values, rerun the normal start command so the container restarts with the new behavior.

## Environment parity
Use the same Git-managed files for both local Docker and cloud-hosted dev boxes:
- same `infra/docker-image-codex` image build context
- same `.env` keys and mounted GitHub App PEM
- same named-volume style persistence goals, adapted to the target provider
- same Codex startup wrapper and `AGENTS.md` loading model

For the cloud-hosted version, use the OCI guide in [docs/OCI-DEVBOX.md](/workspace/infra/docker-image-codex/docs/OCI-DEVBOX.md). The same pattern can be applied to any cloud provider that can run Docker on a VM.

## Recommended prompt for Codex after login
"Read `AGENTS.md`, `README.md`, and the repo docs. Explain the current architecture, the current branch, the next safe step, and what you need from me before making changes."
