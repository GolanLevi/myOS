Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (!(Test-Path .\.env)) {
  throw "Missing .env. Copy .env.example to .env and edit it first."
}

docker compose up -d --build
Write-Host "Container started. Test with: ssh -p 2222 dev@127.0.0.1"
