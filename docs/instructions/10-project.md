# Project / Repo Instructions

## Current product truth
This repo already contains a working smart-secretary style core around email, calendar, approvals, and orchestration.
Do not treat the project as a blank slate.

## Current target direction
Evolve the current system into a cleaner, web-based command center with:
- one main web UI
- approvals in the web UI
- execution visibility
- cost/value visibility
- safer service boundaries
- GitOps-style desired state for non-secret configuration

## Architecture expectations
- runtime account is `myos-runtime`
- runtime deploys pull approved `main`
- secrets come from OCI Vault
- runtime materialization is allowed only under `/run/myos-secrets`
- operator accounts must not read runtime secrets
- adding/removing operators must not restart production

## Out of scope by default
- major rewrites
- unnecessary framework changes
- broad new agents
- production secret sprawl
- direct pushes to protected `main`

## Working style
- one PR-sized change at a time
- explicit acceptance criteria
- preserve behavior unless changing it intentionally
- note risks and rollback when touching deployment or auth
