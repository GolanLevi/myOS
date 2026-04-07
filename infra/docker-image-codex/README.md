# Codex GitOps Dev Box

This runs Codex inside a Docker container with:
- SSH access for VS Code Remote-SSH
- persistent home directory (`codex-home` volume)
- persistent workspace (`codex-workspace` volume)
- repo clone/update inside the container (no host repo bind mount)
- GitHub App authentication for clone / fetch / pull / push
- tmux auto-resume so reconnecting over SSH returns you to the last Codex session

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

### 6) Codex login
First time only, after SSHing in:
```bash
codex --login
```
That login state persists in the `codex-home` volume.

## Quick start

1. Copy `.env.example` to `.env`
2. Edit `.env`
3. Start:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
Unblock-File .\scripts\start.ps1
.\scripts\start.ps1
```
4. Test SSH:
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
8. In the terminal:
```bash
codex --login
```

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

## Recommended prompt for Codex after login
"Read `AGENTS.md`, `README.md`, and the repo docs. Explain the current architecture, the current branch, the next safe step, and what you need from me before making changes."
