# Code Intelligence Logs

## 2026-04-11

### Topic: Web UI migration pitfalls around HITL decision surfaces
- If `ui_client` proxies `/real-api` to Docker service names like `server`, verify DNS resolution inside the Vite container. In this repo it was flaky and produced empty dashboard states; `host.docker.internal` was stable on the current Windows setup.
- Keep approval payloads presentation-ready. The UI became much simpler once approvals exposed `headline`, `summaryLine`, `senderLine`, `nextStepLine`, `outcomeLine`, and structured `previewSections`.
- Legacy or generic subjects like `פגישה` are not acceptable as card headlines. Always fall back to `event_title`, `draft_subject`, or the first meaningful preview line.
- Mixed RTL/LTR content must be handled per field, not per card. Sender/email, summary, and draft blocks each need their own direction detection.
- Vite dev servers can serve stale behavior after large component rewrites. When a live browser result contradicts the code on disk, restart `myos_ui_client` before chasing phantom logic bugs.
- For safe HITL smoke tests, prefer clicking `manual guidance` and asserting the composer opens rather than executing real approvals on live items.

## 2026-04-11 - UI chrome language vs. payload language
- Keep the application shell in one language, but do not translate backend payload fields like agent summaries, HITL action labels, or Hebrew context lines.
- Mixed RTL/LTR layouts break when direction is applied at the card level. Apply `dir` and text alignment per field or per message bubble.
- Browser smoke tests for the dashboard should avoid asserting on backend Hebrew labels when the product requirement is English chrome plus Hebrew payload.

## 2026-04-12 - Docker engine startup before compose on Windows
- If `docker compose` fails on `//./pipe/dockerDesktopLinuxEngine`, Docker Desktop is not up yet. Start Docker Desktop first, then wait for `docker info` to succeed before running compose.
- For this repo, `docker compose up --build -d` succeeded once the engine was ready, and the server healthcheck was the reliable signal that FastAPI was actually usable.

## 2026-04-12 - Structured decision payloads for dashboard cards
- Approval cards became easier to evolve once the backend exposed a single structured `decisionData` object instead of forcing each UI surface to reverse-engineer sender, time, summary, draft, and action buttons from mixed preview text.
- Keep both a compact preview field and a fuller draft field when extracting email tool payloads. The list view can stay lightweight while deeper surfaces still have access to the actual draft text.

## 2026-04-12 - Calm Today surfaces need labeled confidence, not naked percentages
- A raw `80%` badge reads like a hidden internal score. Label it explicitly as agent confidence and explain once near the top of the page what the range means.
- If only the urgent bucket should feel critical, tone down all other urgency treatments to neutral surfaces so the page reads as ordered rather than alarm-heavy.

## 2026-04-12 - Shared decision summary cards keep Today and Approvals aligned
- When `Today` and `Approvals` both show the same approval queue, they need the same pre-preview card contract. Otherwise each page drifts into its own summary logic and the UI feels inconsistent.
- The stable list-card contract here is: subject summary, sender name, importance, arrival time, confidence, and a single `Open decision` CTA. Draft text, raw source lines, and action buttons belong in the drawer, not in the queue.
- Restarting `myos_ui_client` remains the reliable fix when Vite serves stale queue-card behavior after a large component rewrite.

## 2026-04-13 - Calm dashboard cleanup needs both typography discipline and backend parity
- Removing explanatory helper copy from `Today` and `Approvals` immediately reduced visual noise; those surfaces work better as operational dashboards than as self-explaining marketing panels.
- The live approvals UI can silently break actions if the frontend points `GET` and `PATCH` to the real backend but leaves `DELETE` on the demo server. Keep route parity across methods whenever a surface mixes real data with write actions.
- A calmer dashboard does not require giant typography. It needs one consistent scale: compact metadata, restrained stat cards, and smaller but sharper list-card headlines.

## 2026-04-13 - Knowledge Agent chat should parse actions, not dump them into prose
- If the backend already returns `[[BUTTONS: ...]]`, the frontend should treat those as structured affordances. Leaving them inside the message body makes the chat look broken and wastes the agent's intent.
- Suggested actions work best as compact chips under the latest assistant turn, with light semantic iconography rather than loud badges.
- Creating a new conversation with `firstMessage` and then immediately posting the same content again can duplicate the first user turn. In this UI flow, create the conversation first, then send the message once.

## 2026-04-13 - Conversation lists should show purpose, not transcript
- A chat thread title should summarize why the conversation exists, not mirror the first full sentence. Showing near-verbatim prompts makes the side panel feel noisy and uncurated.
- For dashboard-style assistant panels, lightweight topic icons on stat cards and thread rows help scanning only when they stay small, consistent, and secondary to the text.
- Personal greeting copy belongs in the page header when it is short and stable. It should not compete with the main operational metrics.

## 2026-04-13 - Raw assistant prose is not a scalable UI contract
- When an assistant returns mixed markdown, emoji labels, confirmations, and suggested actions in one text block, the UI starts looking amateur even if the model output is correct.
- The quickest stabilizers are: dedupe action chips, render markdown-lite properly, force visible composer text styles, and derive thread purpose titles on the server instead of the client only.
- The long-term fix is a structured assistant response model with separate fields for summary, facts, suggested actions, and terminal outcomes.

## 2026-04-13 - Multi-user retrofit is feasible, but the repo still has single-user choke points
- The current state layer already understands `user_id`, so the project is not starting from zero. The real blockers are the hardcoded `"admin"` defaults spread across dashboard endpoints, graph entry points, and the chat bridge into `/ask`.
- Shared local OAuth files like `token.json` and `credentials.json` are incompatible with a serious multi-user product. Connector credentials must move to encrypted per-user records with reconnect and revocation paths.
- A single Chroma collection and single checkpoint namespace are acceptable for V1, but they are the wrong default for private multi-tenant memory. Tenant isolation needs to be explicit in both long-term memory and graph execution state before adding banks, social accounts, or other high-sensitivity connectors.

## 2026-04-14 - Phase 2 should add a credential store before rebuilding all connector UX
- The clean migration path is not to rewrite every Gmail and Calendar tool signature at once. Add a user-aware execution context, then let connector lookups resolve the active user from that context.
- Shared local `token.json` can remain as a temporary admin fallback during migration, but only if the encrypted per-user store becomes the default path for every new user.
- A small operational script for interactive Google connection is worthwhile before full UI onboarding exists. It lets the backend move to the new credential model immediately without blocking on a complete connector settings experience.

## 2026-04-14 - Email Inbox needs one source of truth for dismiss actions
- If a live list is fetched from the FastAPI dashboard but its trash action still points at the local demo Mongo route, the delete button will look broken even when both code paths work independently. Read and write routes must hit the same backend.
- Inbox cards should not nest a trash `<button>` inside the main card `<button>`. That markup is invalid and creates flaky click behavior.
- Suppression rules for ignored and low-priority email items should live in the backend first, with a small frontend guard so stale or mixed payloads still stay out of the inbox.
