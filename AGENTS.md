# myOS - AGENTS.md
## Context for AI Coding Agents Working on `C:\Users\97250\myOS`

> Read this file before changing code.
> It describes the current product, the live architecture, the UI transition status, and the new multi-user direction.

> Current top priorities
> 1. Finish the Web UI migration and keep it as the primary user interface.
> 2. Prepare the backend for real multi-user isolation instead of the current `"admin"` defaults.
> 3. Preserve privacy boundaries while expanding connectors like Gmail, Calendar, banks, finance tools, and social networks.

---

## 0. Session Initialization Rules

Every new task must begin with these checks:

1. Read:
   - `C:\Users\97250\myOS\skills\research-scout\learnings.md`
   - `C:\Users\97250\myOS\skills\code-intelligence\logs.md`
2. Apply recent learnings before making changes.
3. If the task touches architecture, connectors, auth, privacy, or UI behavior, add new learnings back into those files.

Permanent local rules:
- Be concise and direct.
- Do not mix Hebrew and English in the same sentence.
- Do not expose secrets.
- Do not commit `.env`, `token.json`, `credentials.json`, local logs, or generated artifacts.

---

## 1. Product Identity

`myOS` is a personal AI operating system.

It sits between a user and the user's digital life:
- email
- calendar
- tasks
- finance alerts
- knowledge retrieval
- future connectors like banks, WhatsApp, and social networks

The system's job is to:
- reduce administrative overhead
- prepare actions instead of just summarizing information
- keep humans in the loop for anything sensitive or irreversible

The user is technical.
Do not over-explain basics.
Do not suggest framework churn.

---

## 2. Non-Negotiable Principles

### 2.1 Human in the loop
Sensitive actions must require approval.

Examples:
- sending an email
- creating or deleting an event
- trashing an email
- future financial actions

This is enforced at the graph and workflow level, not only in prompts.

### 2.2 Privacy by default
- User data should remain local whenever possible.
- External model calls are the only accepted disclosure boundary.
- Every persistent record must become user-scoped and eventually tenant-scoped.
- Cross-user data leakage is unacceptable.

### 2.3 LangGraph stays
Do not replace LangGraph.
Do not introduce other orchestration frameworks.

### 2.4 Multi-user forward thinking
The product is no longer allowed to evolve as a permanently single-user tool.

Even when a feature still runs with `"admin"` today, new code must be written as if multiple users will use it soon.

---

## 3. What Exists Today

## 3.1 Core Python backend

Primary backend:
- `C:\Users\97250\myOS\manager_api.py`

This file currently does too much:
- FastAPI endpoints
- dashboard APIs
- HITL resolution
- approval actions
- event rendering
- workflow bridging
- chat bridge behavior
- summary extraction

It still needs decomposition.

### 3.2 Active graph

Primary graph:
- `C:\Users\97250\myOS\agents\secretariat_graph.py`

Current responsibilities:
- triage inbound emails
- classify intent
- suggest replies
- prepare calendar actions
- pause before sensitive tools

Fallback chain:
- Gemini
- Anthropic
- Groq

### 3.3 Knowledge and memory

Knowledge agent:
- `C:\Users\97250\myOS\agents\information_agent.py`

Current state:
- manual and partial
- Chroma-backed
- still using one shared collection:
  - `my_knowledge_lc`

This is acceptable for local single-user behavior.
It is not acceptable for real private multi-user memory.

### 3.4 Local persistence

State manager:
- `C:\Users\97250\myOS\core\state_manager.py`

Important current truth:
- action history already understands `user_id`
- contacts already understand `user_id`
- pending actions already understand `user_id`

This is the strongest existing base for the future multi-user migration.

### 3.5 Connectors

Current Gmail and Calendar utilities:
- `C:\Users\97250\myOS\utils\gmail_connector.py`
- `C:\Users\97250\myOS\utils\gmail_tools.py`
- `C:\Users\97250\myOS\utils\gmail_tools_lc.py`
- `C:\Users\97250\myOS\utils\calendar_tools.py`
- `C:\Users\97250\myOS\utils\calendar_tools_lc.py`
- `C:\Users\97250\myOS\utils\credential_store.py`
- `C:\Users\97250\myOS\utils\request_context.py`

Current migration status:
- active execution now has a user-aware request context for graph and connector calls
- encrypted per-user credential storage now exists in MongoDB
- an operational connection script now exists:
  - `C:\Users\97250\myOS\scripts\connect_google_for_user.py`

Remaining limitation:
- connector auth still has a legacy fallback on shared local files for admin:
  - `credentials.json`
  - `token.json`

That fallback is transitional only and must be removed after connector onboarding and migration are complete.

### 3.6 Cost and time logging

New support modules:
- `C:\Users\97250\myOS\utils\cost_logger.py`
- `C:\Users\97250\myOS\utils\time_saved_logger.py`

These are now part of the product baseline and should be used by future agents and tools.

---

## 4. Web UI Status

The Web UI is no longer a future plan.
It is now a real codebase and the main product direction.

### 4.1 UI structure

Main UI folders:
- `C:\Users\97250\myOS\ui\client`
- `C:\Users\97250\myOS\ui\server`

### 4.2 Client

Tech:
- React
- Vite
- Tailwind

Main pages currently present:
- `Today`
- `Approvals`
- `Email Inbox`
- `Tasks`
- `Timeline`
- `Cost & Value`
- `Connections`
- `Admin`
- login flow

Shared UI pieces already exist:
- dashboard chrome primitives
- shared approval summary cards
- calmer visual language for `Today` and `Approvals`
- `Knowledge Agent` side panel

### 4.3 Node UI server

The Node server is now a real middle layer.

It handles:
- auth
- dashboard routes
- conversations
- chat list and chat history
- server-side conversation titles
- activity feeds

Important current limitation:
- the chat route still bridges into FastAPI with `user_id = "admin"` in at least one important path
- this must be removed during the multi-user refactor

### 4.4 Current UI behavior

What is already working:
- login shell
- dashboard navigation
- approvals list
- approval drawer
- today queue
- calmer card system
- dismiss and delete actions
- structured decision data rendering
- `Knowledge Agent` action chips
- dynamic conversation title summarization

What is still incomplete:
- full design consistency across every page
- stronger empty states
- complete responsive polish
- structured agent response contract instead of free-form text blobs
- real multi-user isolation across the full stack

---

## 5. Current Architecture Reality

The stack now has two backends:

1. Python backend
   - LangGraph
   - Gmail and Calendar tools
   - HITL logic
   - dashboard APIs

2. Node UI backend
   - auth
   - UI-specific models
   - chat persistence
   - dashboard-facing APIs

This split is acceptable.

But it means every user-facing action now needs clean identity propagation across both layers.

Current weak points:
- too many Python endpoints default to `"admin"`
- chat to FastAPI is still partly single-user
- Chroma memory is shared
- shared OAuth token files are single-user only
- LangGraph checkpoints are not yet tenant-isolated by design

---

## 6. What Works Well Today

1. Email triage and action preparation exist.
2. The Web UI now has real operational surfaces.
3. Decision cards are moving toward a stable summary contract.
4. The state manager already has useful `user_id` scaffolding.
5. Approval and activity concepts are already expressed in product terms, not only as Telegram actions.

---

## 7. What Is Still Technical Debt

### High priority
- `manager_api.py` is still too large
- shared Gmail and Calendar token model is single-user
- `Knowledge Agent` still depends too much on raw prose output
- multi-user is only partial and inconsistent
- Chroma memory is globally shared
- graph invocation still has single-user defaults

### Medium priority
- dashboard data is still split between Python and Node without a hard contract
- several UI pages still need the same polish level as `Today` and `Approvals`
- some routes still depend on fallback display logic instead of strongly structured payloads

### Low priority
- some helper scripts are local-operational only and do not belong to the main product path
- some legacy Telegram-first assumptions still remain in the codebase

---

## 8. Current Repository Map

### Product code
- `main.py`
- `manager_api.py`
- `agents/`
- `core/`
- `utils/`
- `ui/`
- `bot/`

### Current docs worth keeping
- `README.md`
- `README_HE.md`
- `docs/WEB_UI_P0_EXECUTION_PLAN.md`
- this `AGENTS.md`

### Local-only or generated material
Do not commit:
- `.env`
- `credentials.json`
- `token.json`
- `output/`
- `test-results/`
- local log files
- `node_modules/`
- generated build output

---

## 9. Rules for New Work

### 9.1 For backend changes
- New user-facing flows must carry `user_id`.
- New storage must be designed as user-scoped.
- New write actions must remain HITL-protected.
- Prefer typed data structures over raw prose parsing.

### 9.2 For UI changes
- Keep the calm dashboard style already established in `Today` and `Approvals`.
- Do not add explanatory marketing copy to operational screens.
- Prefer compact, decision-led surfaces.
- Keep typography disciplined and consistent.

### 9.3 For agent output
Long term, every assistant response should move toward a structured contract such as:
- `kind`
- `title`
- `summary`
- `facts`
- `suggested_actions`
- `result`

Do not keep growing the UI around unpredictable raw strings.

---

## 10. Multi-User Expansion Plan

This section replaces the old vague V2 idea.

The product now needs a real staged path.

## Phase 1 - Identity and user propagation

Goal:
Stop pretending the product is single-user.

Required work:
1. Remove `"admin"` defaults from dashboard and action endpoints.
2. Make `user_id` mandatory in the Python workflow entry paths.
3. Pass the authenticated UI user through the Node server into FastAPI.
4. Ensure approvals, history, summaries, notifications, and chat all resolve only inside the signed-in user context.

Output:
- user-scoped actions
- user-scoped approvals
- no shared dashboard views by accident

## Phase 2 - Connector credential isolation

Goal:
Make Gmail and Calendar safe for more than one person.

Required work:
1. Replace shared filesystem tokens with encrypted per-user connector records.
2. Add reconnect and revoke flows.
3. Support incremental scope grants.
4. Model connector status per user in the UI.

Output:
- each user connects their own Google account
- no token collisions
- no single shared mailbox model

## Phase 3 - Memory and execution isolation

Goal:
Prevent cross-user leakage in long-running AI state.

Required work:
1. Partition Chroma memory per user or per tenant.
2. Partition or namespace LangGraph checkpoints by user or tenant.
3. Ensure state restoration always resolves within the same owner context.
4. Make background jobs user-aware.

Output:
- private memory
- private workflow state
- no shared long-term context

## Phase 4 - Product-level multi-tenant model

Goal:
Support personal, family, and business workspaces cleanly.

Required work:
1. Introduce explicit tenant or workspace identity.
2. Separate person identity from workspace membership.
3. Add role and permission checks.
4. Make each connector belong to a user and optionally to a workspace.

Output:
- one person can operate in more than one workspace
- family or business models become possible

## Phase 5 - New connectors

Goal:
Expand the operating system safely.

Candidate connectors:
- banks
- finance systems
- WhatsApp
- social networks
- research and web search

Required work:
1. connector registry
2. normalized connector status model
3. per-connector consent flow
4. per-connector privacy classification
5. audit logging

Output:
- scalable connector architecture instead of one-off integrations

## Phase 6 - Cross-product hardening

Goal:
Make the system production-grade for real multi-user growth.

Required work:
1. structured audit logs
2. encrypted secret storage
3. reconnect and token expiry handling
4. tenant-aware monitoring
5. rate limits
6. background worker isolation
7. stronger test coverage around authorization boundaries

---

## 11. Recommended Immediate Next Steps

The next correct order is:

1. finish Google connector onboarding around the new encrypted credential store
2. migrate existing admin credentials into the new store and remove direct operational dependence on `token.json`
3. partition memory and graph state
4. only then add more users in production
5. only after that add banks and social connectors

Do not add more sensitive connectors before Phase 2 and Phase 3 are done.

---

## 12. Rules for Git and Commits

- Commit product code only.
- Do not commit generated local output.
- Do not commit secrets.
- Keep commits clean and explainable.
- If a branch is used for major UI or architecture work, keep the branch focused.

---

## 13. Hard Do Nots

- Do not remove HITL from sensitive actions.
- Do not replace LangGraph.
- Do not keep adding features on top of `"admin"` shortcuts.
- Do not store multiple users' connector tokens in shared local files.
- Do not use one global memory collection for private multi-user rollout.
- Do not build new UI screens with noisy helper text or bulky layout blocks.

---

## 14. Summary

The project is no longer just:
- Gmail webhook
- Telegram approval

It is now:
- a real Web UI product
- a split Python and Node architecture
- an approval and operations dashboard
- an early platform for multi-user orchestration

The next major engineering challenge is not visual polish.

It is identity, tenant isolation, connector storage, and privacy-safe scaling.

Last updated: 2026-04-13
