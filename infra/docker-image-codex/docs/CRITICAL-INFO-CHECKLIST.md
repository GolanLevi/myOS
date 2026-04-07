# Critical Information Checklist

This checklist is for the human operator, not for Codex.

## Required to start the container

### SSH public key contents
Get from:
```powershell
Get-Content $HOME\.ssh\id_ed25519.pub
```
Put the entire single line into `.env` -> `SSH_PUBLIC_KEY=`.

### GitHub App ID
Where:
- GitHub -> Settings -> Developer settings -> GitHub Apps -> your app
Field:
- **App ID**

### GitHub App installation ID
Where:
- GitHub App -> Install App / Configure -> select your account / repo
- Use the installation page / URL / API to get the installation ID

### GitHub App private key PEM
Where:
- GitHub App -> Generate private key
Store at a safe local path outside the repo, e.g.:
```text
C:/Users/YOU/secrets/myos-github-app.private-key.pem
```
Then set `.env` -> `GH_APP_PRIVATE_KEY_FILE=` to that path.

### Repo URL
Example:
```text
GIT_REPO_URL=https://github.com/GolanLevi/myOS.git
```

### Working branch
Example:
```text
GIT_REF=chatGPT-amit/myos-infra
```
Use a feature branch while testing.

### Git author identity for the container
Set in `.env`:
```text
GIT_USER_NAME=myOS Agent
GIT_USER_EMAIL=myos-agent@users.noreply.github.com
```

## Optional later
- model/API keys if you want your own app runtime inside the same box
- provider-specific secret mounts
- richer task/config files in the repo
