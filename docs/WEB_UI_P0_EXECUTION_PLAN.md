# Web UI P0 Execution Plan

Last updated: 2026-04-10
Owner: Codex
Scope: rollback-safe migration of myOS from Telegram-first HITL to Web UI-first HITL

## Why This File Exists

The project is already in a transition state:

- the React UI exists and is visually strong
- FastAPI already exposes additive `/dashboard/*` endpoints
- some dashboard actions are live
- but the product still behaves like a preview bridge in a few important places

This file tracks the highest-priority execution work that must happen now, with verification after each step.

## P0 Goals

1. The Web UI must become the trustworthy primary HITL interface.
2. Incoming Gmail items must render correctly in Hebrew and English.
3. The dashboard must report real state instead of mixed preview/demo signals.
4. Every change must be easy to roll back.

## Current P0 Task List

### P0.1 Live Mode Truthfulness
Status: Completed
Owner: `LiveMode Steward` + Codex verification

Problem:
- the UI can have live approval buttons while still showing `Read-only preview`
- different write affordances are inconsistently disabled

Files:
- `ui/client/src/lib/apiClient.js`
- `ui/client/src/pages/TodayPage.jsx`
- `ui/client/src/pages/ApprovalsPage.jsx`

Acceptance:
- if real approvals are enabled, the UI must not claim it is read-only
- Today and Approvals must derive their preview state from one shared rule
- disabled controls must match actual backend capability

Verification:
- run the UI in `real` mode with live approvals enabled
- confirm approval buttons are clickable
- confirm preview badge is absent when writes are enabled

Verified:
- `ui/client` production build passes
- browser validation passes: Today now shows `Live approvals` instead of `Read-only preview`
- approval buttons remain clickable while notification dismiss stays read-only

Rollback:
- revert only UI files above
- env flags remain the source of truth

### P0.2 Gmail Intake Fidelity
Status: Completed
Owner: `Mail Intake Surgeon` + Codex verification

Problem:
- some incoming/self-sent Hebrew emails appear with broken subject/body rendering
- fallback values like `No Subject` leak into UI cards
- `utils/gmail_tools.py` still uses `print()`

Files:
- `utils/gmail_tools.py`

Acceptance:
- decoded subject/from/to values are stable for Hebrew mail
- self-sent test emails do not degrade into generic placeholders unless truly missing
- no `print()` calls remain in this module

Verification:
- send a Hebrew test mail locally through the project Gmail OAuth path
- fetch it back with `fetch_recent_emails()` / `fetch_email_by_id()`
- confirm UI card title/description look sane

Verified:
- `utils/gmail_tools.py` passes `py_compile`
- no `print()` calls remain in `utils/gmail_tools.py`
- Hebrew self-send smoke test succeeds when the subject is supplied as real UTF-8 text to Python
- fetch path now returns the Hebrew subject correctly instead of collapsing to `No Subject`

Rollback:
- revert only `utils/gmail_tools.py`

### P0.3 End-to-End Approval Smoke Path
Status: Completed
Owner: Codex

Problem:
- we need a stable way to prove the UI is not only rendering cards, but can approve/reject without regressions

Files:
- integration only unless fixes are needed

Acceptance:
- create one reversible test approval from a fake or low-risk email
- approve or reject from the UI
- verify resulting state transition in `/dashboard/approvals`, `/dashboard/activity`, and persisted action state

Verification:
- browser check with Playwright
- API check against `/dashboard/approvals` and `/dashboard/activity`
- no unintended external side effects

Rollback:
- use a synthetic or isolated thread where possible
- if a real card is used, prefer reject over approve unless explicitly testing execution

Verified:
- callback-driven approval buttons are now rendered from the Telegram-equivalent backend action set
- browser validation confirms `Today` and `Approvals` show live Hebrew action buttons with inline manual guidance
- synthetic callback test via `TestClient` transitions an isolated action to `approved` without external side effects

### P0.3b Hebrew-Safe Smoke Harness
Status: Completed
Owner: Codex

Problem:
- terminal-encoded ad hoc test sends can create `????` in subject/body and pollute both Gmail and the dashboard
- we need a repeatable smoke path that always sends proper Hebrew through Gmail OAuth

Files:
- `scripts/hebrew_hitl_smoke.py`

Acceptance:
- smoke mail is sent with a real Hebrew subject/body
- the matching pending approval and insight summary appear in `/dashboard/*`
- neither payload includes raw `[[BUTTONS: ...]]` markers
- both surfaces expose Telegram-equivalent actions

Verification:
- run `python scripts/hebrew_hitl_smoke.py`
- confirm non-zero `approval_actions` and `summary_actions`

Rollback:
- additive script only

### P0.3a Legacy Pending Cleanup
Status: Completed
Owner: Codex

Problem:
- the running Docker stack contained hundreds of stale `incoming_email` placeholder actions with empty `params`
- these polluted `Today` / `Approvals` with generic legacy cards

Files:
- `scripts/backfill_legacy_pending_actions.py`

Acceptance:
- identify only stale placeholder pending actions
- preserve rollback metadata on every changed record
- remove the stale records from pending dashboard queues without deleting history

Verification:
- `dry-run` inside the running `myos_server` container reports targeted ids before mutation
- `apply` stores `_legacy_dashboard_cleanup` metadata and flips the records to `expired`
- `/dashboard/approvals?status=pending&user_id=admin` now returns only the real pending approval card

Rollback:
- each cleaned record preserves previous status/params under `params._legacy_dashboard_cleanup`
- records can be restored by replaying that metadata if needed

### P0.4 Real-Time Dashboard Delivery
Status: Pending
Owner: Codex

Problem:
- dashboard views still rely on manual refresh instead of a live stream

Files:
- `manager_api.py`
- `ui/client` subscription layer

Acceptance:
- dashboard receives new events without manual refresh
- approvals/activity update automatically

Verification:
- inject a new pending item and confirm it appears live in the open browser

Rollback:
- additive SSE/WebSocket endpoint only
- polling fallback remains intact

### P0.6 Unified Urgency Model + Today Simplification
Status: Completed
Owner: Codex

Problem:
- `Today` was rendering two separate feeds (`Urgent` + `Top Approvals`) instead of one real priority surface
- pending HITL items could appear in `Today`, `Approvals`, and `Insights` as near-duplicate cards
- urgency was implicit and inconsistent across screens

Files:
- `manager_api.py`
- `ui/client/src/pages/TodayPage.jsx`
- `ui/client/src/pages/ApprovalsPage.jsx`
- `ui/client/src/pages/InboxPage.jsx`
- `ui/client/src/components/layout/Sidebar.jsx`

Acceptance:
- backend exposes one shared urgency model on dashboard items:
  - `urgencyScore`
  - `urgencyLabel`
  - `dueBucket`
  - `isActionable`
- `Today` renders only:
  - `דורש החלטה עכשיו`
  - `להיום`
  - `אפשר לחכות`
- `Approvals` remains the canonical HITL action queue
- `Insights` defaults to summaries/context and no longer acts like a second approvals page

Verification:
- `manager_api.py` passes `py_compile`
- `ui/client` production build passes
- `docker compose up --build -d` succeeds
- API checks confirm urgency metadata is present on `/dashboard/approvals`, `/dashboard/notifications`, and `/dashboard/summaries`
- browser checks confirm:
  - `Today` shows the 3 urgency sections
  - action buttons still work in `Today` and `Approvals`
  - `Insights` shows the approvals handoff banner and no in-card HITL action buttons

Rollback:
- backend urgency logic is additive and limited to dashboard payload builders
- `Today`, `Approvals`, and `Insights` can each be reverted independently if the UX split needs tuning
- no HITL callback path or graph interrupt logic was changed

### P0.5 Knowledge Tool Wiring
Status: Pending
Owner: Codex

Problem:
- `KnowledgeAgent` exists but is not exposed as a graph tool

Files:
- `agents/secretariat_graph.py`
- `agents/information_agent.py`

Acceptance:
- graph can query the knowledge base as a safe tool
- no write/HITL rules are bypassed

Verification:
- run one targeted knowledge lookup through the graph

Rollback:
- additive tool registration only

## P1 After P0

- replace the token estimation heuristic fallback with a Hebrew-safe byte-based estimate
- continue multi-user-safe query design on every new dashboard endpoint
- extract `card_renderer.py` / `hitl_orchestrator.py` from `manager_api.py`

## Debug Discipline

For every task above:

1. inspect before changing
2. patch the smallest viable surface
3. run targeted verification immediately
4. keep logs and screenshots when useful
5. do not batch unrelated fixes together
