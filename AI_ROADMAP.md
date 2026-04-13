# Scout AI Roadmap

Last reconciled: 2026-04-13 against commit `c527fdf` on `main`.

Purpose of this pass: separate what the AI platform **actually is in code**,
what is **covered by tests**, what is **verified through the real browser UI**,
what is **running in production**, and what is **intentionally deferred debt**.
No new AI features are introduced in this pass — this is reconciliation only.

## Status Legend

- **VERIFIED** — code exists, tests exist, AND the behavior is exercised
  end-to-end (prod deploy OR deployed browser smoke, not just backend tests).
- **IMPLEMENTED** — code exists and unit/integration tests pass, but the real
  shipped behavior has not been re-exercised through the deployed UI.
- **PARTIAL** — only a subset of the intended surface exists, or only the
  happy path is covered.
- **DEFERRED** — intentionally postponed; captured in the ledger below.
- **UNKNOWN** — not enough evidence to classify.

"Works in backend tests" ≠ "works through the real UI" ≠ "works in production"
— each section calls these apart explicitly.

---

## 1. AI Provider / Orchestrator Layer
**Status: IMPLEMENTED**

**What exists**
- `backend/app/ai/provider.py` (99 lines) — Anthropic-only `AnthropicProvider`
  with a clean `chat()` surface, `AIResponse` / `ToolCall` / `ToolDefinition`
  dataclasses. Config read from `settings.anthropic_api_key`,
  `ai_chat_model`, `ai_max_tokens`, `ai_temperature`, `ai_request_timeout`.
  Raises `RuntimeError` if the API key is missing.
- `backend/app/ai/orchestrator.py` (361 lines) — `chat()` runs a bounded
  tool-use loop (`MAX_TOOL_ROUNDS = 5`, one tool per round), plus the
  synchronous `generate_daily_brief`, `generate_weekly_plan`, and
  `suggest_staple_meals` helpers.
- Models are hardcoded through config defaults: `SCOUT_AI_CHAT_MODEL`,
  `SCOUT_AI_CLASSIFIER_MODEL`, `SCOUT_AI_MAX_TOKENS=2048`,
  `SCOUT_AI_TEMPERATURE=0.3`, `SCOUT_AI_REQUEST_TIMEOUT=60`.
- `/ready` exposes `ai_available` based on whether the API key is set.
- `AsyncIterator` is imported in `provider.py` but there is **no streaming
  implementation yet** — the import is aspirational.

**Evidence**
- `provider.py:37-95` (full Anthropic call).
- `orchestrator.py:124-246` (chat loop).
- `release_candidate_report.md` — `/ready` returns `ai_available: true` on
  Railway (commit `5c7d849`).

**Verification strength**
- Backend unit + integration tests exist (below).
- **Request/response only — no streaming.** Frontend awaits a full JSON body
  before rendering.
- No provider retry, no fallback, no prompt caching.

**Gaps**
- Single provider / single point of failure.
- No cost or token-budget ceiling at the app layer.
- No telemetry other than `logger.info` lines.

**Next work**
- Bring up a thin SSE streaming path (server → client incremental render).
- Add retry-with-backoff on upstream 5xx.
- Split `orchestrator.chat()` tool loop out of the request thread so long
  generations don't hold the HTTP connection open for 60s.

---

## 2. Role-Aware Context Loading
**Status: IMPLEMENTED**

**What exists**
- `backend/app/ai/context.py` (196 lines).
- `load_member_context()` loads `Family`, `FamilyMember`, `RoleTier` override,
  permissions, behavior config, and (for adults) the list of active children.
- `build_system_prompt()` produces three documented variants:
  `adult-personal`, `adult-parent`, `child`. Data from notes / events /
  connectors is wrapped as DATA blocks, not instructions (prompt-injection
  resistance).
- `get_allowed_tools_for_surface(role, surface)` returns the per-request tool
  allowlist:
  - **10 read tools** (all roles)
  - **+3 child-write tools** (`add_grocery_item`, `create_purchase_request`,
    `add_meal_review`)
  - **+13 adult-write tools** (tasks, events, notes, meal plans, grocery,
    purchase requests)
  - **+6 parent tools** (notifications, purchase approval, meal-plan
    approval, day regeneration)

**Evidence**
- `context.py:19-100` (context loading), `context.py:142-196` (allowlist).
- `backend/tests/test_ai_context.py` — 10 tests: adult/parent/child prompts,
  child-role restriction, cross-family rejection, prompt-injection resistance.

**Verification strength**
- Backend tests only. Context loading is never directly exercised in a
  browser test; it is implicitly exercised whenever `/api/ai/chat` runs.

**Gaps**
- Role restrictions are not assertively verified through the UI (the ai-panel
  smoke test only covers the happy-path adult-personal case).

**Next work**
- Add a child-login AI panel smoke that asserts a write tool is not offered /
  is denied.

---

## 3. Tool Registry / Confirmation / Audit
**Status: IMPLEMENTED**

**What exists**
- `backend/app/ai/tools.py` (994 lines).
- **29 tool definitions** in `TOOL_DEFINITIONS` (previously mis-stated as 17
  in an earlier roadmap pass). Grouped by read / write / parent as above.
- `CONFIRMATION_REQUIRED` set (10 tools): `create_event`, `update_event`,
  `create_or_update_meal_plan`, `mark_chore_or_routine_complete`,
  `send_notification_or_create_action`, `approve_purchase_request`,
  `reject_purchase_request`, `convert_purchase_request_to_grocery_item`,
  `approve_weekly_meal_plan`, `regenerate_meal_day`.
- First call returns `{confirmation_required: true, ...}`; a second call with
  `confirmed=true` executes.
- `AIToolAudit` table + `GET /api/ai/audit` expose every invocation with
  `status ∈ {success, denied, confirmation_required, error}`, `duration_ms`,
  `result_summary` (truncated), and serialized arguments.
- Tools wrap existing service modules — no duplicated domain logic.

**Evidence**
- `tools.py:35-47` (`CONFIRMATION_REQUIRED`), `tools.py:643-1000+`
  (tool definitions).
- `backend/tests/test_ai_tools.py` — 14 tests: read-only allowlist for
  children, child-denied tool returns error + creates audit row,
  confirmation gating, family isolation, successful execution audited.
- `backend/tests/test_ai_routes.py` — 5 tests: conversation create/retrieve,
  cross-family isolation, confirmation list exposure.

**Verification strength**
- Backend test suite is solid for the tool layer itself.
- No browser test exercises a confirmation round-trip.
- No browser test exercises an audit row being read back.

**Gaps**
- Audit table has no retention / pruning strategy.
- Confirmation-required tools cannot be completed through the current
  ScoutPanel because the panel never surfaces the confirmation prompt.

---

## 4. Conversation Persistence
**Status: IMPLEMENTED**

**What exists**
- `AIConversation` and `AIMessage` tables (see `app/models/ai.py`).
- `get_or_create_conversation()` enforces family + member scoping.
- `_persist_message()` records user / assistant / tool messages, including
  tool calls, tool results, model name, and token usage.
- `_load_conversation_messages()` replays the last 40 messages into
  Anthropic API format on each turn.
- `GET /api/ai/conversations` + `GET /api/ai/conversations/{id}/messages`
  return family-scoped history.

**Evidence**
- `orchestrator.py:32-121`.
- `test_ai_routes.py` — conversation create/retrieve and cross-family tests.

**Verification strength**
- Tests prove the server persists and scopes correctly.
- **No UI path restores a prior conversation on panel reopen** — history is
  reloaded from scratch every session.

**Gaps**
- No conversation "resume" affordance.
- No per-member / per-surface history browser.
- No archive / cleanup strategy.

---

## 5. ScoutPanel Chat UX (Frontend)
**Status: PARTIAL**

**What exists**
- `scout-ui/components/ScoutLauncher.tsx` (272 lines) — `ScoutPanel` slide-up
  modal with message history, 6 quick-action chips, text input, and handoff
  buttons driven by `result.handoff`.
- Quick actions (verbatim): "What does today look like?", "What's off
  track?", "Add a task", "Add to grocery list", "Plan meals for next week",
  "What do the kids still need to finish?".
- `scout-ui/lib/api.ts:340-364` — `sendChatMessage()` POSTs to
  `/api/ai/chat` with a client-generated `X-Scout-Trace-Id`
  (`scout-${Date.now()}-${random}`) and logs failures with the trace id.
- Handoff button deep-links via `router.push(route_hint)` on tap.
- Loading state: `ActivityIndicator` + "Thinking..." text while awaiting.

**Evidence**
- `ScoutLauncher.tsx:27-34` (quick actions), `ScoutLauncher.tsx:50-75`
  (send loop), `ScoutLauncher.tsx:107-127` (handoff rendering).
- `api.ts:340-364` (trace-id generation + error logging).

**Verification strength**
- One thin Playwright test covers the happy path only (see §10).
- **No UI handling for `confirmation_required`** — a tool requiring
  confirmation will silently not execute and the user gets free-form text.
- **No streaming / no typing indicator** beyond a single spinner.
- **No conversation resume** — reopening the panel always starts fresh.
- **No error surface** beyond a single "Something went wrong" bubble on
  fetch failure.

**Gaps**
- Disabled-state handling: the panel does not check `/ready.ai_available`
  before opening; if the key is missing the user fires a request that 500s.
- No child-facing ScoutPanel variant or affordance.

---

## 6. Handoff to Saved Objects
**Status: IMPLEMENTED**

**What exists**
- Every write-tool handler returns `_handoff(entity_type, entity_id,
  route_hint, summary)`.
- Covered entity types: `personal_task`, `event`, `meal_plan`, `grocery_item`,
  `purchase_request`, `note`, `chore_instance`.
- Frontend renders handoffs as tappable cards that deep-link into the
  relevant screen on press.

**Evidence**
- `tools.py:50-57` (`_handoff` helper).
- `ScoutLauncher.tsx:112-125` (handoff rendering + `router.push`).

**Verification strength**
- No browser test taps a handoff card and asserts the deep link works.

**Gaps**
- `send_notification_or_create_action` is logged but not delivered (no
  notification transport).
- `dietary_preferences` is not consumed by the meal-plan generator path.

---

## 7. Meal Generation Workflow
**Status: PARTIAL**

**What exists** — two distinct paths, kept deliberately separate:
1. **`orchestrator.suggest_staple_meals()`** → returns 5–7 staple meal ideas
   as free-form text. Used for ideation. No DB write. Surface via
   `POST /api/ai/meals/staples`. **Currently unused by the UI.**
2. **`weekly_meal_plan_service.py`** (790 lines) — the real AI-driven weekly
   plan loop (questions → answers → regenerate → approve). Wired into
   `scout-ui/app/meals/this-week.tsx` and is the path users actually take.

**Evidence**
- `orchestrator.py` (staples method), `services/weekly_meal_plan_service.py`
  (the real loop).
- Release report: "weekly meals (39)" tests passing locally.

**Verification strength**
- 39 backend tests in the weekly-meals bucket (per
  `release_candidate_report.md`).
- **No deployed smoke test exercises the weekly-plan generation loop.**

**Gaps**
- Dietary preferences table is not read by the generator.
- Staple-meals endpoint has no UI consumer.
- No UI indicator if generation times out or falls back.

---

## 8. Daily Brief / Summaries
**Status: IMPLEMENTED**

**What exists**
- `generate_daily_brief(db, family_id, member_id)` — ~200-word summary of
  today's tasks, events, meals, unpaid bills. Uses a fixed read-tool
  allowlist (`get_today_context`, `list_events`, `list_tasks`,
  `get_rewards_or_allowance_status`).
- `generate_weekly_plan(db, family_id, member_id)` — ~300-word Mon–Sun plan
  highlighting commitments and deadlines.
- Routes: `POST /api/ai/brief/daily`, `POST /api/ai/plans/weekly`,
  `POST /api/ai/meals/staples`.
- **On-demand only**. Blocking. No scheduler, no cache, no email / push.

**Evidence**
- `orchestrator.py:249+`, `routes/ai.py:61-94`.

**Verification strength**
- Backend tests cover wiring.
- No browser smoke hits these endpoints.

**Gaps**
- No scheduled runs → no morning brief without the user tapping a button.
- Up to a 60s hold on the HTTP connection for a long generation.

---

## 9. Correlation Logging / Observability
**Status: IMPLEMENTED**

**What exists**
- `routes/ai.py:40-58` reads `X-Scout-Trace-Id` from the incoming request and
  emits `ai_chat_start`, `ai_chat_success`, and `ai_chat_fail` structured
  log lines. This was added in commit `9481f8f`.
- `scout-ui/lib/api.ts:345-363` generates the trace id and forwards it, and
  also console-logs AI errors with the trace id for browser-side correlation.
- Output is stdout → Railway logs. No external telemetry, no dashboards.

**Evidence**
- `routes/ai.py:40-58`, `api.ts:345-363`.

**Verification strength**
- Log lines confirmed present in source.
- **Not exercised in any smoke test.** Trace-id round-tripping is unverified
  in the deployed environment.

**Gaps**
- No dashboards for AI latency, error rate, or tool-call distribution.
- No per-family or per-conversation cost tracking.
- `AIToolAudit` is per-tool, not per-turn — there is no structured event
  store for "conversation turn X took N ms and consumed Y tokens."

---

## 10. Browser-Based AI Verification
**Status: PARTIAL**

**What exists**
- `smoke-tests/tests/ai-panel.spec.ts` (94 lines) — a **single** test:
  1. Probe `/ready` for `ai_available: true`; `test.skip()` if false.
  2. Adult login → click "Scout AI" in the NavBar → assert the "What can I
     help with?" header.
  3. Click the "What does today look like?" quick action, await the
     `/api/ai/chat` response.
  4. Assert status < 500 and that "Something went wrong" is **not** visible.

**What it does NOT cover**
- Actual tool execution (the test never asserts a tool was called).
- Confirmation round-trip.
- Role restrictions (no child or parent surface variant).
- Handoff button deep-links.
- Conversation resume / history reload.
- Streaming (because streaming does not exist).
- Disabled-state UI when `ai_available: false`.

**Assertion strength**
- **Weak.** The test passes even if the assistant bubble is empty or the
  response is a stock "I can't help right now." The only hard assertion is
  "no 5xx and no error banner." This is a launch-sufficiency gate, not a
  behavior gate.

**Next work**
- Assert the assistant bubble renders non-empty text.
- Add a second test that creates a task through the AI and then asserts
  the task appears on the Personal screen.
- Add a child-login test that tries a write and expects a denial.

---

## 11. Production AI Deployment State
**Status: PARTIAL**

**What exists**
- `SCOUT_ANTHROPIC_API_KEY` is set on Railway (commit `c29a5d0`).
- `/ready` returns `ai_available: true` in production
  (`release_candidate_report.md` line 126).
- Feature-flag gating is fail-closed: missing key → AI disabled, not
  crashed.

**What is NOT verified**
- The deployed 9/9 Playwright smoke pass in `release_candidate_report.md`
  covers **auth (4) + adult surfaces (5)** only. **The `ai-panel.spec.ts`
  suite was not part of that 9/9 run**, so there is no record of the
  ScoutPanel actually getting a 200 from the Railway backend through the
  Vercel frontend.
- No confirmation that `X-Scout-Trace-Id` log lines appear in Railway logs
  from a real production request.
- No confirmation that a tool call successfully executes against the
  production Postgres.

**Caveats**
- Models pinned by string — requires a code change to upgrade.
- No cost ceiling or rate ceiling at the application layer; relies on the
  Anthropic account.
- Drift risk: the local smoke includes the AI panel, the deployed smoke
  does not. A break between local and deployed would not be caught.

**Next work**
- Run `ai-panel.spec.ts` against the production URL and record the
  result in `release_candidate_report.md`.
- Spot-check Railway logs for an `ai_chat_success` line with a real trace
  id.

---

## 12. Deferred AI Debt

See the full ledger at the end of this document.

---

## Required Answers (explicit)

**Is the AI platform implemented?**
Yes. Provider, orchestrator, context loader, 29 tools, confirmation flow,
audit table, conversation persistence, handoff cards, daily brief, and
weekly plan all exist in code with backend tests.

**Is the AI panel verified through the real browser UI?**
Partially. There is one thin Playwright test (`ai-panel.spec.ts`) that runs
**locally** and passes the happy path. It was **not** part of the 9/9 deployed
smoke run recorded in `release_candidate_report.md`. Deployed-browser
verification is UNKNOWN.

**Is the AI request/response or streaming?**
Request/response only. `AnthropicProvider.chat()` returns a single
`AIResponse`. `sendChatMessage()` awaits a single JSON body. The
`AsyncIterator` import in `provider.py` is aspirational — no SSE, no chunks,
no typing indicator.

**Which AI behavior is launch-sufficient but not strategically complete?**
- Single thin AI-panel smoke (good enough for launch, weak for regressions).
- Request/response (usable, feels slow on long replies).
- On-demand daily brief / weekly plan (works, but nobody sees them without
  tapping a button).
- Logging to stdout (works, no dashboards).
- Confirmation flow at the API (works, but the UI never triggers it).
- `send_notification_or_create_action` audits but does not deliver.

**Which AI regressions are now protected by tests, and which are still
weakly protected?**

Well protected:
- Tool permission / allowlist per role and surface
  (`test_ai_context.py`, `test_ai_tools.py`).
- Confirmation gating on shared-write tools (`test_ai_tools.py`).
- Cross-family isolation for tools and conversations (`test_ai_routes.py`,
  `test_ai_tools.py`).
- Audit row creation on success, denial, and confirmation-required paths
  (`test_ai_tools.py`).

Weakly protected:
- ScoutPanel UX (one happy-path test, no assertions on content).
- Handoff deep-links (not exercised by any test).
- Streaming (no implementation to test).
- Role restrictions through the real UI (no child smoke).
- `confirmation_required` round-trip through the UI.
- Weekly meal plan generation loop through the UI.
- Daily brief / weekly plan endpoints through the UI.
- Deployed browser behavior for any AI path.

---

## AI Panel Hardening Still Needed

Only items that are **still true** after reading the current repo:

- **Assertion strength in `ai-panel.spec.ts`.** The test currently only
  checks "no 5xx and no error banner." It should assert the assistant
  bubble contains non-empty text and, ideally, perform a full tool round
  trip (create a task → verify the task exists).
- **Deploy drift between main and Railway/Vercel.** The deployed 9/9 smoke
  run did not include `ai-panel.spec.ts`. Run it against the deployed URLs
  and record the result.
- **Observability gaps.** `ai_chat_start` / `ai_chat_success` /
  `ai_chat_fail` logs exist but no dashboard, no alert, and no automated
  confirmation that they surface in Railway logs with a real trace id.
- **Disabled-state handling in the UI.** `ScoutPanel` does not probe
  `/ready.ai_available` before opening; if the key is ever absent the user
  hits a live request that fails. The smoke test gracefully skips in this
  state, but the app itself does not.
- **No confirmation-flow UI.** Backend returns `confirmation_required`; the
  panel has no affordance for it, so any shared-write tool essentially
  dead-ends.
- **No child/parent surface coverage.** The one smoke test only logs in
  as an adult on the personal surface. Parent and child surfaces are
  completely untested through the browser.
- **No handoff deep-link test.** The handoff cards are wired to
  `router.push`, but no test asserts the target screen loads.

---

## File Summary

| Area | File | Lines | Purpose |
|---|---|---|---|
| Provider | `backend/app/ai/provider.py` | 99 | Anthropic wrapper, dataclasses |
| Context | `backend/app/ai/context.py` | 196 | Role-aware prompt + allowlist |
| Orchestrator | `backend/app/ai/orchestrator.py` | 361 | Chat loop, brief, plan, staples |
| Tools | `backend/app/ai/tools.py` | 994 | 29 tool definitions + executor |
| Routes | `backend/app/routes/ai.py` | ~180 | Chat, conversations, audit, brief |
| Schemas | `backend/app/schemas/ai.py` | 96 | Pydantic request/response models |
| Frontend panel | `scout-ui/components/ScoutLauncher.tsx` | 272 | Slide-up chat panel |
| Frontend API | `scout-ui/lib/api.ts` (AI block) | ~25 | `sendChatMessage` + trace id |
| Backend tests | `backend/tests/test_ai_context.py` | 101 | 10 tests |
| Backend tests | `backend/tests/test_ai_routes.py` | 77 | 5 tests |
| Backend tests | `backend/tests/test_ai_tools.py` | 205 | 14 tests |
| Smoke test | `smoke-tests/tests/ai-panel.spec.ts` | 94 | 1 thin happy-path test |

Total AI backend tests: **29** (matches the "AI (29)" bucket in
`release_candidate_report.md`).

---

## Top 10 AI Deferred Items

1. **Streaming responses.** `AsyncIterator` is imported but no SSE endpoint
   exists. Biggest perceived-latency cost.
2. **Deployed AI-panel smoke.** `ai-panel.spec.ts` has never been recorded
   as run against the Railway + Vercel deployment.
3. **Confirmation-flow UI.** Backend returns `confirmation_required`; no UI
   affordance renders the prompt.
4. **Assertion depth in the AI smoke test.** Currently only checks for
   absence of error, not presence of a real response.
5. **Child / parent surface smoke coverage.** No browser test exercises
   role restrictions, parent surface, or child surface.
6. **`send_notification_or_create_action` delivery channel.** Tool audits
   and logs but does not actually notify anyone.
7. **Dietary preferences → weekly-plan generator wiring.** Generator runs
   without reading the preferences table.
8. **Scheduled daily brief / weekly plan.** On-demand only; no cron, no
   push, no Action Inbox entry, no email.
9. **Conversation resume across sessions.** Conversations persist
   server-side; the panel always opens empty.
10. **Cost / latency observability.** Only stdout log lines. No dashboard,
    no alert, no per-family cost tracking, no token budgeting.

---

## 5 Strongest AI Capabilities

1. **Role-aware tool allowlist with confirmation gating.** 29 tools, three
   role tiers, 10 confirmation-required writes, backed by 14
   `test_ai_tools.py` tests.
2. **Audit trail on every tool invocation.** `AIToolAudit` captures
   success / denied / confirmation_required / error with duration, summary,
   and full arguments.
3. **Family-scoped conversation persistence.** `AIConversation` +
   `AIMessage` with cross-family rejection verified in
   `test_ai_routes.py`.
4. **Clean provider abstraction.** `AnthropicProvider` + `ToolDefinition`
   dataclasses isolate the Anthropic SDK behind a narrow interface; a
   second provider could slot in behind it.
5. **Correlation logging with trace-id propagation.** Frontend generates
   the trace id, backend logs `ai_chat_start` / `ai_chat_success` /
   `ai_chat_fail` with it. Ready for a future dashboard.

---

## 5 Weakest / Least-Verified AI Areas

1. **ScoutPanel UX depth.** One thin smoke test, no content assertions, no
   handoff verification, no confirmation handling, no resume.
2. **Deployed browser verification.** The 9/9 deployed Playwright smoke
   did not include `ai-panel.spec.ts`. Prod-through-UI is UNKNOWN.
3. **Streaming.** Does not exist. Long replies block the full HTTP request.
4. **Scheduled generation.** Daily brief and weekly plan are on-demand only.
5. **Cost / latency observability.** Log lines exist, dashboards and alerts
   do not.

---

## "AI VERIFIED Today" — end-to-end exercised

Strictly: code + backend tests + evidence beyond the unit test harness.

- **AI platform boots in production.** `/ready` returns
  `ai_available: true` on Railway (`release_candidate_report.md:126`).
- **Backend AI test bucket passes at 29/29.** (per
  `release_candidate_report.md` coverage line.)
- **Role-aware tool allowlist.** Enforced in code and covered by 14
  `test_ai_tools.py` tests + 10 `test_ai_context.py` tests.
- **Confirmation gating on shared-write tools.** Enforced and tested.
- **Cross-family isolation of tools and conversations.** Enforced and
  tested.
- **Audit row on every tool invocation.** Written and tested.
- **`X-Scout-Trace-Id` propagation in source.** Present in both frontend
  and backend — but never asserted in a smoke test.

---

## "AI Implemented but Not Strongly Verified"

- **ScoutPanel chat loop.** One happy-path smoke test, no content
  assertions.
- **Handoff cards.** Rendered in code; no test taps one.
- **Conversation persistence replay.** Server persists; no UI test verifies
  a reload.
- **Daily brief / weekly plan / staple meals endpoints.** No smoke test
  calls them.
- **Trace-id propagation end-to-end.** Wired on both sides; no test
  asserts the id reaches the log.
- **Weekly meal plan generation loop.** 39 backend tests; no deployed
  smoke of the real UI flow.
- **`ai-panel.spec.ts` against production.** Exists locally; never
  recorded against Railway + Vercel.

---

## AI Deferred Ledger

| # | Item | Why deferred | Launch impact | Next window |
|---|---|---|---|---|
| 1 | Streaming responses | Request/response works; streaming is UX debt | Perceived latency on long replies | Phase A |
| 2 | Deployed browser verification of AI panel | 9/9 smoke covered auth + surfaces; AI panel ran locally only | Drift between local and deployed can land unseen | Phase A (immediate) |
| 3 | AI panel smoke depth (tools, confirmation, history, handoff) | Happy-path smoke was sufficient for launch gate | Medium — regressions in tool flow would not be caught | Phase A |
| 4 | Confirmation-flow UI in ScoutPanel | Backend returns `confirmation_required`; UI does not render it | Shared-write tools currently dead-end in the panel | Phase B |
| 5 | Provider fallback / retry on 5xx | Anthropic reliability has been acceptable | User sees error on upstream hiccup | Phase A |
| 6 | Dietary preferences → generator wiring | Generator still produces usable plans | Low | Phase A |
| 7 | Scheduled daily brief / weekly plan | On-demand works | Lower engagement | Phase B |
| 8 | `send_notification_or_create_action` delivery | Action Inbox covers the need today | None for launch | Phase B |
| 9 | Cost / latency dashboards | Log-grepping works at single-family scale | None for launch | Phase A tail |
| 10 | Conversation resume in UI | Conversations persist server-side but not restored | Low | Phase C |
| 11 | Disabled-state handling in ScoutPanel | Prod currently has `ai_available: true` | User-visible break if the key is ever removed | Phase A |
| 12 | Prompt caching | Per-turn rebuild is fine at current volume | None | Phase C |
| 13 | Second provider | Single-provider risk is acceptable for private use | Single point of failure | Later |
| 14 | Autonomous multi-step planning | Out of scope for private launch | None | Not planned |
| 15 | Photo / doc / voice pipelines | Out of scope | None | Not planned |

---

## AI Unknowns

These are things the current repo cannot tell us without going out and
probing:

- Whether `ai-panel.spec.ts` would pass against the live Vercel + Railway
  URLs today.
- Whether Railway logs actually show `ai_chat_start` / `ai_chat_success`
  lines from real production traffic (nothing has verified this since
  `9481f8f` landed).
- Whether the weekly meal plan generation loop completes end-to-end against
  production Postgres within the 60s request timeout.
- Whether production Anthropic usage is currently within the account's
  rate/cost ceilings (no app-layer telemetry).
- Whether any tool has been invoked in production since deploy (audit
  table has not been inspected).

---

## Recommended Sequence

**Phase A — Coverage + Quality of Life (before any new AI capability)**
1. Run `ai-panel.spec.ts` against the deployed URLs; log the result.
2. Strengthen the AI smoke test: assert non-empty assistant bubble,
   perform one full tool round trip (create task → verify on Personal).
3. Add a child-login smoke that expects a write denial.
4. Streaming response pipeline (server SSE → client incremental render).
5. Retry-with-backoff on upstream 5xx.
6. Dietary preferences → weekly-plan generator wiring.
7. Disabled-state handling: ScoutPanel probes `ai_available` before opening.

**Phase B — Copilot depth**
1. Scheduled morning brief delivery (email or Action Inbox entry).
2. "What's off track?" as a real rule-engine-backed explanation.
3. Confirmation UI flow inside ScoutPanel.
4. Notification delivery channel for `send_notification_or_create_action`.

**Phase C — Ambient / optimization**
1. Conversation resume + per-member history browser.
2. Prompt caching for the static parts of the system prompt.
3. Budget ceilings per family.
4. Optional: second provider for redundancy.

---

## Out of Scope For Now

- Photo / doc / voice intelligence pipelines
- Autonomous multi-turn planning loops
- Cross-family or anonymized intelligence
- Custom fine-tuned models
