Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (!(Test-Path .\.env)) {
  throw "Missing .env. Copy .env.example to .env and edit it first."
}

$sshPort = "2222"
$sshPortLine = Get-Content .\.env | Where-Object { $_ -match '^SSH_PORT=' } | Select-Object -First 1
if ($sshPortLine) {
  $sshPort = ($sshPortLine -split '=', 2)[1].Trim()
}

docker compose up -d --build

$containerName = "codex-box"
$deadline = (Get-Date).AddSeconds(20)
do {
  Start-Sleep -Seconds 1
  $status = docker inspect -f '{{.State.Status}}' $containerName 2>$null
} while (($status -eq "created" -or $status -eq "restarting") -and (Get-Date) -lt $deadline)

if ($status -ne "running") {
  Write-Host "Container failed to stay up. Recent logs:"
  docker logs --tail 80 $containerName
  throw "codex-box status: $status"
}

docker exec $containerName sh -lc "test -f /run/secrets/github_app_private_key.pem && test -f /home/dev/.bashrc && test -f /home/dev/.codex/config.toml && echo container-ok" | Out-Null

$ssh = Get-Command ssh -ErrorAction SilentlyContinue
if ($null -eq $ssh) {
  Write-Host "Container started, but ssh.exe was not found on this host for the final probe."
  Write-Host "Test manually with: ssh -T -p $sshPort dev@127.0.0.1 sh -lc `"echo ok`""
  exit 0
}

$sshOutput = & ssh `
  -o StrictHostKeyChecking=no `
  -o UserKnownHostsFile=NUL `
  -o BatchMode=yes `
  -T `
  -p $sshPort `
  dev@127.0.0.1 `
  sh -lc "echo ok" 2>&1

if ($LASTEXITCODE -ne 0 -or ($sshOutput | Out-String) -notmatch 'ok') {
  Write-Host "SSH probe failed. Recent container logs:"
  docker logs --tail 80 $containerName
  throw "codex-box is running, but SSH validation failed"
}

Write-Host "Container started and passed SSH validation on port $sshPort."
