# Research Scout Learnings

## 2026-04-10

### Topic: Anthropic skills for UI migration, live UI validation, and future multi-user architecture

#### Source: https://github.com/anthropics/skills/tree/main
- Anthropic's `skills` repo is an official public reference for agent skills, with examples spanning design, testing, MCP construction, and documentation.
- The repo is explicitly positioned as a pattern library for specialized, repeatable tasks rather than generic prompts.
- The repo should be treated as inspiration plus reusable operational guidance, but each installed skill still needs validation in the local environment before relying on it for critical flows.

#### Source: https://skills.sh/anthropics/skills/frontend-design
- `frontend-design` is the best direct fit for high-quality React/Vite dashboard work because it targets production-grade frontend interfaces instead of static art assets.
- The skill is optimized for distinctive, polished UI output and is more aligned with real app surfaces than presentation-first skills.
- This should be the default design skill for work inside `ui/` when we are building or refining the actual product interface.

#### Source: https://skills.sh/anthropics/skills/webapp-testing
- `webapp-testing` is highly relevant for this project because it closes the loop between implementation and verification on local dynamic apps.
- Its recommended flow is reconnaissance first, then interaction, with explicit waiting for `networkidle` before DOM inspection on dynamic apps.
- This is especially useful for validating the React/Vite dashboard against live backend behavior and catching regressions while we migrate away from Telegram-first flows.

#### Source: https://skills.sh/anthropics/skills/theme-factory
- `theme-factory` is useful when the UI needs a coherent visual system, reusable palette, and typography direction across multiple artifacts or surfaces.
- It complements `frontend-design` rather than replacing it: one gives visual-system scaffolding, the other drives production-grade UI execution.
- This is a good fit for establishing a repeatable dashboard theme before scaling the UI to more agents and eventual multi-user views.

#### Source: https://skills.sh/openai/skills/figma
- `figma` was not available in `anthropics/skills`, but an actively used alternative exists in `openai/skills`.
- Its workflow is strongly implementation-oriented: fetch structured design context, fetch screenshots, pull assets, then translate into project conventions rather than copying generated UI verbatim.
- This makes it a strong fit for design-to-code work if the myOS dashboard starts using Figma frames as the source of truth.

#### Source: https://skills.sh/anthropics/skills/skill-creator
- `skill-creator` is useful once the project accumulates repeated internal workflows that generic public skills do not capture well.
- It emphasizes evaluation, iteration, and measuring whether a skill actually improves outputs, which matters if we later build a myOS-specific dashboard or multi-tenant architecture skill.
- The right moment to lean on it is after we identify recurring project-specific tasks, not as a substitute for installing the baseline UI/testing skills first.

## 2026-04-11

### Topic: Decision dashboard hierarchy, approval-flow clarity, and RTL/LTR rendering for the Web UI transition

#### Source: https://design.applecart.co/ux/ux-feedback/key-ux-insights-from-our-audience-management-workflow-testing-2025
- Review and approval flows degrade fast when button affordances and navigation are ambiguous; Applecart measured high misclick rates and a 50% drop-off in review/approval tasks.
- The concrete mitigation is better button placement, clearer affordances, and inline guidance instead of pushing users into extra navigation loops.
- For myOS this supports making `Today` cards action-led and keeping the main approval buttons visible without forcing a generic `Review` step first.

#### Source: https://learn.microsoft.com/en-us/windows/uwp/design/globalizing/adjust-layout-and-fonts--and-support-rtl
- RTL support must be applied structurally, not as a cosmetic mirror. Mixed-language content needs control-level directionality rather than one `dir` for the whole surface.
- Layouts and text containers should size to content and be pseudo-localized/tested to catch truncation and direction bugs early.
- For myOS this supports per-field `dir` handling in the drawer and avoiding a single monolithic mixed-direction content block.

#### Source: https://ronasit.com/blog/right-to-left-design-guide/
- RTL interfaces should still keep inherently LTR fragments like emails, URLs, and English copy in LTR, even inside an RTL shell.
- Paragraph direction should follow the language of the paragraph, not the page. Mixed-direction interfaces need scoped alignment and spacing rules.
- For myOS this supports rendering sender/email, English draft text, and Hebrew explanatory text as separate blocks with independent alignment.

#### Source: https://cygnis.co/blog/web-app-ui-ux-best-practices-2025/
- Modular UI and strong visual hierarchy remain the practical way to reduce cognitive load in dense web apps.
- Surfaces should emphasize the next action and compress secondary data instead of presenting every field at equal visual weight.
- For myOS this supports promoting subject, short summary, and primary action above metadata and raw payload.
2026-04-11 | Bilingual dashboard chrome with Hebrew payloads | Local repo task | Keep UI shell language stable, preserve user/system content in the source language, and apply RTL/LTR direction per field instead of per card or page.
2026-04-12 | Docker Compose restart / rebuild | https://docs.docker.com/get-started/docker_cheatsheet.pdf?pubDate=20250606 | Use `docker compose up --build -d` when you need recreated services with rebuilt images; verify readiness with `docker compose ps`, targeted HTTP checks, and health status instead of assuming the stack is ready after the command exits.

## 2026-04-12

### Topic: HITL dashboard UX, dense decision surfaces, and mixed RTL/LTR rendering

#### Source: https://design.applecart.co/ux/ux-feedback/key-ux-insights-from-our-audience-management-workflow-testing-2025
- Approval and review flows break down quickly when affordances are unclear or actions are placed poorly.
- The reported 27% to 45% misclick rates and 50% drop-off in review/approval tasks reinforce that dense decision queues need clearer button hierarchy and fewer navigation loops.
- For myOS this supports making the primary decision obvious at first glance and reducing duplicate surfaces that show the same item in slightly different forms.

#### Source: https://cygnis.co/blog/web-app-ui-ux-best-practices-2025/
- Dense web apps degrade when cards carry too much equally-weighted information.
- Clear visual hierarchy, modular cards, responsive behavior, and limiting each card to essential content remain the practical baseline for complex dashboards.
- For myOS this supports compressing metadata, promoting headline and next action, and keeping summary cards glanceable instead of email-like.

#### Source: https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance.html
- Focus indicators should visibly change by at least 3:1 contrast and be large enough to remain clear across responsive variants.
- A 2px perimeter-equivalent focus treatment is the simplest compliant baseline for interactive controls.
- For myOS this supports stronger keyboard focus and clearer active states on pills, tabs, queue cards, drawer actions, and icon-only controls.

## 2026-04-13

### Topic: Multi-tenant architecture, tenant isolation, and per-user connector credentials

#### Source: https://docs.aws.amazon.com/wellarchitected/latest/saas-lens/preventing-cross-tenant-access.html
- Tenant context must be carried explicitly through every request and write path; relying on application conventions alone is not enough to prevent cross-tenant access.
- Cross-tenant access prevention works best when isolation is enforced at multiple layers rather than only in UI routing or controller code.
- For myOS this supports making `user_id` mandatory end-to-end in API handlers, graph execution, logs, connector calls, and storage lookups.

#### Source: https://developers.google.com/identity/protocols/oauth2/resources/best-practices
- OAuth client secrets and user refresh tokens must be stored securely, encrypted at rest, and revoked or deleted when no longer needed.
- Incremental authorization is the recommended path for multi-connector products: request scopes only when a user enables a feature, not all upfront.
- For myOS this means the shared `token.json` model must be replaced with per-user encrypted credential records and connector-specific consent flows.

#### Source: https://developers.google.com/workspace/gmail/api/auth/web-server
- Server-side applications are expected to retrieve stored refresh tokens from their database and authorize requests for the correct signed-in user.
- Refresh token failure is a normal production path and must trigger a reconnect flow instead of silently failing.
- For myOS this supports moving Gmail and Calendar auth from local filesystem tokens to database-backed per-user connector sessions.

### Topic: Inbox noise suppression and destructive action clarity in dense dashboards

#### Source: https://carbondesignsystem.com/patterns/common-actions/
- Destructive actions should be explicit and predictable, and `remove` should be treated differently from permanent `delete` when the product is only dismissing an item from a queue.
- Error feedback for list actions should stay short and contextual instead of forcing the user into a separate flow.
- For myOS this supports treating inbox trash as a queue dismissal action and wiring it directly to the same source of truth as the live list.

#### Source: https://rocketvalidator.com/accessibility-validation/axe/4.11/nested-interactive
- Interactive controls must not be nested inside other interactive controls because click, focus, and screen-reader behavior become unreliable.
- If a card is clickable and also has its own action buttons, the layout should separate the primary click target from secondary controls rather than literally nesting buttons.
- For myOS this supports restructuring inbox rows so the expand trigger and trash action are siblings, not nested controls.

#### Source: https://arxiv.org/abs/2603.05893
- Calm-notification research continues to reinforce that non-urgent items should stay peripheral rather than competing with urgent actions in the main attention surface.
- Urgency should change visibility and placement, not only color treatment.
- For myOS this supports filtering ignored and low-priority email summaries out of the main inbox surface instead of merely labeling them as less important.

#### Source: https://clerk.com/docs/organizations/overview
- Multi-tenant products need an explicit organization context in each active session, including membership and role data.
- A user can legitimately belong to multiple organizations, so the active tenant must be first-class state rather than inferred from email alone.
- For myOS this supports modeling tenant context separately from person identity, so one user can act in personal, family, and business workspaces safely.

#### Source: https://learn.microsoft.com/en-my/entra/identity-platform/claims-validation
- In multitenant systems, stored data must only be accessed again within the same tenant context that created it.
- Token validation must check tenant claims in addition to subject claims; otherwise data can leak across tenants even when auth technically succeeds.
- For myOS this supports enforcing tenant-aware authorization in the Node UI server and FastAPI backend, not only at the database query layer.

## 2026-04-14

### Topic: Encrypted connector credentials and per-user OAuth session storage

#### Source: https://developers.google.com/identity/protocols/oauth2/resources/best-practices
- OAuth refresh tokens should be stored securely and encrypted at rest. Local shared token files are only acceptable for single-user development, not for a multi-user product.
- Authorization should be requested incrementally as users connect features, not globally at first login.
- For myOS this supports replacing shared `token.json` usage with encrypted per-user connector credential records while keeping explicit per-feature connection steps.

#### Source: https://developers.google.com/workspace/gmail/api/auth/web-server
- Server-side apps should retrieve the correct signed-in user's stored credentials from durable storage before calling Gmail.
- Refresh token rotation and invalidation are normal states and should feed reconnect flows instead of being treated as exceptional edge cases.
- For myOS this supports a connector store in MongoDB plus future reconnect UX in the `Connections` page.

#### Source: https://docs.aws.amazon.com/wellarchitected/latest/saas-lens/preventing-cross-tenant-access.html
- Tenant isolation is strongest when enforced at several layers, including request context, storage lookup, and execution context.
- Background workers and asynchronous execution must preserve tenant context, not just web request handlers.
- For myOS this supports carrying user context into LangGraph tool execution, not only into dashboard route parameters.

#### Source: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- Important controls should meet at least 24 by 24 CSS pixels or provide enough spacing to avoid accidental activation.
- Small adjacent icon actions are a recurring failure mode in dense admin surfaces.
- For myOS this supports enlarging trash, refresh, close, and row-level controls, especially inside approvals and the drawer header.

#### Source: https://firefox-source-docs.mozilla.org/code-quality/coding-style/rtl_guidelines.html
- LTR-only fragments such as URLs, usernames, phone numbers, and similar tokens should explicitly use LTR direction, but can still align visually with the parent layout using `text-align: match-parent`.
- Mixed-direction inputs sometimes need `dir="auto"` rather than a page-wide direction decision.
- For myOS this supports field-level direction handling for sender/email lines, English draft snippets, and chat content instead of card-level RTL assumptions.

### Topic: Calm decision cards, progressive disclosure, and confidence presentation

#### Source: https://www.adminuiux.com/future-of-admin-dashboard-design/
- Recent dashboard guidance is shifting from flashy contrast toward "calm design" with subtle elevation, softer highlights, and less decorative noise.
- In dense operational surfaces, visual ergonomics matter more than ornament. Critical items should gain weight structurally, not through constant alarm-color backgrounds.
- For myOS this supports replacing harsh red card fills with restrained dark surfaces, thin urgency accents, and clearer spacing hierarchy.

#### Source: https://uxuiprinciples.com/en/principles/confidence-indicator-display
- Confidence indicators help users calibrate trust, but raw technical numbers are weaker than human-readable framing and contextual explanation.
- The useful pattern is: show confidence, label what it means, and make it obvious that the signal is guidance rather than certainty.
- For myOS this supports keeping confidence visible on the card while pairing it with a stable label and a single page-level explanation.

#### Source: https://www.iopex.com/blog/ai-adoption-in-ux-design
- Trust breaks when users must open multiple screens just to understand what the AI wants them to approve.
- High-stakes AI UX should expose confidence, recourse, and enough context inline, while pushing deeper explanation into one-click drill-down rather than dumping raw detail into the list.
- For myOS this supports making list cards summary-only: subject, sender, urgency, arrival time, confidence, and one obvious `Open decision` action.

#### Source: https://arxiv.org/abs/2604.07535
- Fresh CHI-adjacent research suggests urgency framing can hurt a human user's self-confidence in human-AI workflows even when it does not increase trust in the AI.
- Overusing urgent visual language can therefore make the interface feel more stressful without improving decision quality.
- For myOS this supports using urgency sparingly, reserving stronger emphasis for true exceptions and keeping the default queue visually calm.

### Topic: Open-decision panel structure for overview-detail approval flows

#### Source: https://design.cms.gov/components/drawer/
- Recent drawer guidance emphasizes using drawers for medium-to-long supplementary content while keeping page context visible.
- On larger screens the drawer should stay fixed to the side; on smaller screens it should overlay the full screen. Close control, heading, focus management, and sticky header/footer all matter.
- For myOS this supports a structured side panel for `Open decision`, but only if the content is clearly chunked and actions stay sticky and obvious.

#### Source: https://carbondesignsystem.com/community/patterns/create-flows/
- Carbon distinguishes between a simple side panel and a wider tearsheet: if there is scrolling, sectional content, or more decision complexity, the wider pattern is a better fit than a narrow panel.
- A side panel is suitable when the user benefits from retaining page context, while a sticky footer and clear title/body/action anatomy help keep execution stable.
- For myOS this supports a wide `Open decision` panel with a stable action rail and sectioned content instead of a narrow text-heavy drawer.

#### Source: https://arxiv.org/abs/2503.07782
- Overview-detail interfaces benefit when users can control which attributes stay in the overview and which move into the detail view.
- The study frames this as variation in content, composition, and layout rather than a single fixed split.
- For myOS this supports a hard rule: queue cards keep only the essential attributes, while `Open decision` shows the richer attributes produced by `decisionData`.

## 2026-04-13

### Topic: Calm dashboard typography, card density, and progressive disclosure for the myOS cockpit

#### Source: https://hexabinar.com/insights/composable-dashboard-cards/
- Dense operational dashboards stay readable when cards use one consistent primitive and then scale density by spacing and typography, not by inventing a new card structure for every section.
- The practical takeaway is that card height, internal padding, and label cadence should be adjustable as a system.
- For myOS this supports shrinking `Today` and `Approvals` into one compact card language instead of mixing oversized hero blocks with dense queue cards.

### Topic: Global RTL/LTR handling for mixed-language dashboards and chats

#### Source: https://www.w3.org/International/questions/qa-html-dir
- User-generated content should not inherit a single page-wide direction blindly. The browser should get direction hints close to the content block itself.
- `dir="auto"` and scoped direction assignment are the safe defaults for mixed-language products.
- For myOS this supports field-level direction on chat bubbles, inbox rows, and approval summaries instead of mirroring entire screens.

#### Source: https://developer.mozilla.org/en-US/docs/Web/HTML/Global_attributes/dir
- The `dir` attribute is the semantic source of truth for text direction and should be set on the element that owns the content, not only via CSS alignment.
- Mixed-content UIs should separate alignment from data order so English emails, URLs, and timestamps can stay `LTR` inside an otherwise Hebrew experience.
- For myOS this supports a shared helper that returns both `dir` and alignment class for every dynamic text block.

#### Source: https://firefox-source-docs.mozilla.org/code-quality/coding-style/rtl_guidelines.html
- Fragments such as emails, usernames, and timestamps should stay `LTR` explicitly even when nearby content is `RTL`.
- Firefox guidance also reinforces that bidi handling should be granular and predictable, not based on a single container assumption.
- For myOS this supports keeping timestamps and technical identifiers pinned to `LTR` while the surrounding message or summary aligns by detected language.

#### Source: https://uxuiprinciples.com/en/principles/progressive-disclosure
- Progressive disclosure works best when the overview keeps only the attributes needed for the next decision and defers everything else until the user explicitly asks for depth.
- Human working memory remains a hard constraint, so overloaded overview screens feel worse even when all the data is technically useful.
- For myOS this supports stripping the top explanatory copy from `Today`, keeping the queue compact, and moving richer context into `Open decision`.

#### Source: https://www.uilayouts.com/top-ui-ux-trends-in-admin-dashboard-design-for-2025/
- Recent dashboard guidance keeps converging on cleaner typography, balanced spacing, and lower visual noise instead of decorative chrome.
- The emphasis is on quick comprehension, with restrained color accents and fewer large competing blocks.
- For myOS this supports a calmer top section, smaller stat cards, and more disciplined type sizing so the page feels organized instead of inflated.

#### Source: https://wpaccessibility.day/2025/wp-content/uploads/sites/7/2025/10/GiuliaLaco_TypographyReadabilityAndDigitalA11y_WPAD2025_slides_graphic_compressed.pdf
- Readability improves when type scales are limited, line lengths stay controlled, and secondary copy does not compete with the primary decision path.
- Overlarge or inconsistent type can reduce scan speed even when contrast is technically sufficient.
- For myOS this supports tightening the headline/body/label scale and reducing oversized summary copy on `Today`.

### Topic: Conversational side panels, suggested action chips, and calmer AI chat UX

#### Source: https://leadadvisorai.com/blog/chatbot-ui-ux-best-practices
- Chat assistants work better when quick replies are short, obviously tappable, and visually separated from the message body instead of buried inside prose.
- The useful pattern is to keep suggested actions close to the latest assistant turn and limit the set to the most relevant next steps.
- For myOS this supports rendering `[[BUTTONS: ...]]` as compact action chips directly under the Knowledge Agent reply.

#### Source: https://www.onething.design/post/chatbot-ui-ux-best-practices-2025
- Recent chat UX guidance favors cleaner panels, reduced helper copy, and stronger visual rhythm between title, message content, metadata, and composer.
- Side panels feel calmer when they avoid instructional filler and let structure do the work.
- For myOS this supports stripping non-essential explanatory text from the Knowledge Agent surface and relying on layout, spacing, and iconography instead.

#### Source: https://www.census.design/blog/designing-generative-ai-experiences-conversational-interfaces
- Generative AI interfaces benefit from progressive disclosure: lightweight responses first, then explicit actions and structured detail only when the user needs them.
- Suggested actions should behave like affordances, not like paragraph content.
- For myOS this supports keeping assistant messages readable while moving action choices into their own dedicated UI layer.

#### Source: https://wayfound.ai/blog/chatbot-ui-ux-design-best-practices
- Conversation lists become easier to scan when each thread carries a subtle semantic cue such as an icon or category tint, but heavy decoration quickly becomes noise.
- The best implementations use small, consistent topic markers rather than full-color illustrations or large badges.
- For myOS this supports adding lightweight dynamic icons to conversation rows, reply types, and suggested buttons without making the panel feel busy.

### Topic: Structured assistant output for operational chat surfaces

#### Source: https://www.useparagon.com/blog/ai-agent-ux-best-practices
- AI assistant surfaces feel unreliable when they mix plain prose, action intents, and confirmation states inside one undifferentiated message blob.
- Better patterns separate summary, structured facts, and next actions, even if the transport layer is still text-based.
- For myOS this supports moving the Knowledge Agent toward a stable response contract instead of relying only on raw `answer` strings.

#### Source: https://uxmag.com/articles/designing-ai-powered-conversational-experiences
- Conversational systems should expose intent and outcome clearly, especially after the user triggers an action.
- The same response model should work across users and contexts rather than being tuned to one personal flow.
- For myOS this supports a generic assistant message schema that can scale to more users, more agents, and more channels.
