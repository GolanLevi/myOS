# Organization Instructions for Codex

You run inside a portable GitOps-oriented development box.
Your job is to improve the product through small, reviewable, well-documented changes.

## Where you live
- Local Docker container now
- May move later to OCI or another cloud
- Same image and startup model should continue to work across environments

## Main expectations
- Work only inside `/workspace`
- Treat Git as the source of truth for code, docs, and non-secret configuration
- Keep real secrets outside the repo
- Prefer small commits and clear branch discipline
- Leave the repo more maintainable than you found it

## How to work
1. Read the repo instructions first
2. Understand current branch and current task
3. Propose the smallest safe change
4. Implement
5. Run relevant checks
6. Commit with a clear message
7. Push to your branch
8. Summarize what changed and what still needs review

## Main principles
- no secrets in Git
- no destructive changes without explicit approval
- preserve working paths while improving architecture
- keep setup portable across local Docker and cloud deployment
- document important assumptions in README or docs

## Resources to use
- repo files in `/workspace`
- README
- task files
- AGENTS hierarchy in the repo
- environment variables already injected into the container

## Do not assume
- that hidden host files are available
- that secrets can be read from Git
- that you can touch production state freely

## Goal
Build a high-quality, low-maintenance AI operating environment that can be moved between local Docker and cloud with minimal changes.
