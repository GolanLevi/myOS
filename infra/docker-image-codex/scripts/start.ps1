Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (!(Test-Path .\.env)) {
  throw "Missing .env. Copy .env.example to .env and edit it first."
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

Write-Host "Container started. Test with: ssh -p 2222 dev@127.0.0.1"
