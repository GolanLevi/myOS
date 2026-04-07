# Secrets and State Model

## Why secrets are materialized at runtime
Vault is the durable source of truth.
Applications still need plaintext values at runtime to authenticate to external services.
So the correct model is:

Vault -> fetch at deploy/start -> restricted runtime files under `/run/myos-secrets` -> app process reads them

`/run` is runtime-only. It is not the durable store.
That means:
- reboot/reset is fine
- the VM fetches fresh values again
- secrets are not stored in Git
- developer accounts should not have permission to read runtime secrets

## Durable state categories

### 1. Git-managed desired state
Versioned, non-secret:
- `config/desired-state.json`
- `config/app-config.json`
- systemd units
- deployment scripts
- AGENTS/docs

### 2. Local admin config
Not committed:
- `config/deploy.local.psd1`
- `config/operators.local.json`
- local secret source file for seeding Vault

### 3. Vault-managed secrets
Durable secret source for runtime:
- GitHub App private key
- model/API keys
- app tokens

### 4. Runtime-only materialization
Ephemeral on the VM:
- `/run/myos-secrets/*`

## Join/leave/change cases
- adding/removing operators updates operator state only; runtime account remains untouched
- rotating a secret updates Vault and the next deploy/start fetches the new version
- changing non-secret config usually requires only a redeploy/reconcile, not infra reprovision
- changing cloud provider should keep the same Git-managed desired state and local secret source, while only infra/provider layers change
