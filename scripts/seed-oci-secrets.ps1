param(
  [string]$LocalConfigPath = ".\config\deploy.local.psd1",
  [string]$VaultSeedJsonPath = ".\config\vault-secrets.local.json"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $LocalConfigPath)) { throw "Missing $LocalConfigPath" }
if (-not (Test-Path $VaultSeedJsonPath)) { throw "Missing $VaultSeedJsonPath" }

$config = Import-PowerShellDataFile -Path $LocalConfigPath
$seed = Get-Content $VaultSeedJsonPath -Raw | ConvertFrom-Json

if (-not (Get-Command oci -ErrorAction SilentlyContinue)) {
  throw "Missing OCI CLI on this local machine."
}

Write-Host "This script seeds/updates OCI Vault secrets."
Write-Host "You must already have a vault and key created, and set the vault OCID in repo-overlay/config/secret-manifest.json or /srv/myos-config/secret-manifest.json."
Write-Host ""

# This script is intentionally conservative.
# It assumes you will use OCI CLI on your local machine with your API key auth already configured.
# For each secret in the local JSON, it base64-encodes the content and prints the create/update command to run.

$manifestPath = ".\repo-overlay\config\secret-manifest.json"
if (-not (Test-Path $manifestPath)) { throw "Missing $manifestPath" }
$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
$vaultId = $manifest.vault_id
if (-not $vaultId -or $vaultId -eq "REPLACE_WITH_VAULT_OCID_AFTER_FIRST_APPLY") {
  throw "Set vault_id in repo-overlay/config/secret-manifest.json before seeding."
}

foreach ($p in $seed.secrets.PSObject.Properties) {
  $name = $p.Name
  $value = [string]$p.Value
  $tmp = New-TemporaryFile
  [System.IO.File]::WriteAllText($tmp.FullName, $value, [System.Text.UTF8Encoding]::new($false))
  $b64 = [Convert]::ToBase64String([System.IO.File]::ReadAllBytes($tmp.FullName))
  Remove-Item $tmp.FullName -Force

  Write-Host "Seed/update secret: $name"
  Write-Host "Use OCI Console or OCI CLI to create/import the CURRENT version for this secret in vault $vaultId."
  Write-Host "Base64 content preview length: $($b64.Length)"
  Write-Host ""
}
