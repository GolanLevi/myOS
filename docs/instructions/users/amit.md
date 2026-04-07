# Amit operator instructions

## Role
- primary developer/operator for Codex environment setup and workflow quality
- often works through a personal fork when upstream app permissions are restricted

## Main focus areas
- Codex autonomy inside the container
- local and cloud environment parity
- clear bootstrap and deployment documentation
- safe GitOps handling for non-secret configuration

## Working style
- prefer direct, pragmatic updates
- prefer the smallest reversible change that fixes the real blocker
- avoid unnecessary churn in upstream-owned files when a narrower dev-box change is enough

## Escalate quickly
- upstream repository permission problems
- GitHub App installation or permission mismatches
- anything that would break local/cloud parity for the Codex environment
