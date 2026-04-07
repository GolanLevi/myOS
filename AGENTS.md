# AGENTS.md - Organization layer

This repository is part of the myOS organization.

## Who uses this environment
- Human builders, operators, and reviewers
- Coding assistants such as Codex or other development agents
- Runtime automation that deploys or operates the product

## Main expectation
Preserve working behavior, increase control and clarity, and move the system toward a safe, maintainable, approval-first AI operating layer.

## Loading order
Read and follow instructions in this order:
1. this file (organization layer)
2. `docs/instructions/10-project.md` (project/repo layer)
3. relevant file under `docs/instructions/users/` if one exists for the active human/operator
4. `docs/tasks/current-sprint.md` (current task/sprint layer)

A lower layer may add detail but may not break a higher-layer rule.

## Core principles
- preserve the working secretary core unless a change is explicitly approved
- prefer small, reversible changes
- never commit secrets
- keep runtime secrets out of developer-accessible paths
- prefer adapters and extraction over rewrites
- prefer one clean control surface over many disconnected tools
- keep the system observable, debuggable, and approval-first
- optimize for quality, safety, and speed of iteration

## What good work looks like
- bounded scope
- tests or checks where practical
- clear diff
- doc update when behavior changes
- explicit risk/rollback note for risky changes

## Resources to use
- `docs/instructions/10-project.md`
- `docs/tasks/current-sprint.md`
- config files under `config/`
- scripts under `scripts/`
- ops docs under `docs/ops/`

## If something is unclear
Stop, state the uncertainty, and choose the safer/smaller path.
