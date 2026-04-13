# Scout AI Roadmap

Last reconciled: 2026-04-13 against commit `4e8d2e9` on `main`.

Purpose of this pass: separate what the AI platform **actually is in code**,
what is **covered by tests**, what is **verified through the deployed backend**,
what is **verified through the deployed browser UI**, what is **running in
production**, and what is **intentionally deferred debt**. No new features in
this pass — reconciliation only.

## Status Legend

- **VERIFIED** — code + tests + real production evidence (prod round-trip,
  production DB rows, Railway log lines, or deployed browser smoke).
- **IMPLEMENTED** — code exists and tests pass, but the real shipped
  behavior has not been re-exercised against production or the deployed UI.
- **PARTIAL** — only a subset of the intended surface exists, or only the
  happy path is covered.
- **DEFERRED** — intentionally postponed; captured in the ledger below.
- **BLOCKED** — real work that cannot move without an external action.
- **UNKNOWN** — not enough evidence to classify.

"Backend tests pass" ≠ "production round-trip works" ≠ "deployed browser
UI works" — each section calls these apart explicitly.

---

## 1. AI Provider / Orchestrator Layer
**Status: VERIFIED**

**What exists**
- `backend/app/ai/provider.py` (177 lines) — `AnthropicProvider` with both
  synchronous `chat()` and streaming `chat_stream()` methods. Streaming
  uses the Anthropic SDK's `messages.stream()` context manager and yields
  typed events (`text_delta`, `tool_use_start`, `tool_use_end`, `message_stop`).
  Raises `RuntimeError` if the API key is missing.
- `backend/app/ai/orchestrator.py` (877 lines) — `chat()` runs a bounded
  tool-use loop (`MAX_TOOL_ROUNDS = 5`, one tool per round); `chat_stream()`
  is the SSE-driving generator version. Plus `generate_daily_brief`,
  `generate_weekly_plan`, `suggest_staple_meals`, plus `_create_moderation_alert`
  and `_tag_conversation_kind` helpers.
- Config: `SCOUT_ANTHROPIC_API_KEY`, `SCOUT_AI_CHAT_MODEL`,
  `SCOUT_AI_CLASSIFIER_MODEL`, `SCOUT_AI_MAX_TOKENS=2048`,
  `SCOUT_AI_TEMPERATURE=0.3`, `SCOUT_AI_REQUEST_TIMEOUT=60`.
- `/ready` exposes `ai_available` based on whether the API key is set.

**Evidence**
- `provider.py` — full Anthropic call + streaming wrapper.
- `orchestrator.py` — chat loop and `chat_stream` generator.
- `release_candidate_report.md` — `/ready` returns `ai_available: true` on
  Railway. Production AI round-trip verified on 2026-04-13 via the
  `smoke@scout.app` account.

**Verification strength**
- Backend unit + integration tests (58 AI tests total).
- Production direct HTTPS round-trip: `POST /api/ai/chat` → 200, real
  `conversation_id`, `tool_calls_made=1`, 762-char response.
- Railway logs show matched `ai_chat_start` / `ai_chat_success` pairs
  with round-tripped trace ids, including one from a real adult user
  (Andrew) before the smoke run.

**Gaps**
- Single provider / single point of failure — no Anthropic fallback.
- No provider retry / backoff on upstream 5xx.
- No cost or token-budget ceiling at the app layer.
- No prompt caching.
- Long non-streaming calls still hold the HTTP connection open up to 60s.

**Next work (Sprint 2)**
- Retry-with-backoff on 5xx.
- Prompt caching for the static prompt prefix.
- Move long-running tool loops out of the request thread.

---

## 2. Role-Aware Context Loading
**Status: VERIFIED**

**What exists**
- `backend/app/ai/context.py` (310 lines).
- `load_member_context()` loads `Family`, `FamilyMember`, `RoleTier`
  override, permissions, behavior config, plus the new
  `allow_general_chat` and `allow_homework_help` family flags, plus
  (for adults) the list of active children.
- `build_system_prompt()` produces three documented variants:
  `adult-personal`, `adult-parent`, `child`. Data from notes / events /
  connectors is wrapped as DATA blocks, not instructions. The child
  prompt is explicit that homework help must **teach, not do**.
- `get_allowed_tools_for_surface(role, surface)` returns the per-request
  tool allowlist including `get_weather` in all surfaces.

**Evidence**
- `context.py` (context loading + allowlist).
- `backend/tests/test_ai_context.py` — **26 tests** covering adult / parent
  / child prompts, child-role restrictions, cross-family rejection,
  prompt-injection resistance, general-chat flag, homework-help flag.

**Verification strength**
- Backend tests cover the matrix of role × surface × settings combinations.
- Production round-trip exercises the adult-personal path once per
  verification run; child path is exercised by `test_ai_context.py` but
  not in the deployed browser smoke.

**Gaps**
- No deployed browser test covers the child surface against prod.

---

## 3. Tool Registry / Confirmation / Audit
**Status: VERIFIED**

**What exists**
- `backend/app/ai/tools.py` (1149 lines).
- **30 tool definitions** in `TOOL_DEFINITIONS`. Breakdown:
  - 10 read tools (all roles)
  - 3 child-write tools (`add_grocery_item`, `create_purchase_request`,
    `add_meal_review`)
  - 13 adult-write tools (tasks, events, notes, meal plans, grocery,
    purchase requests, weekly plan generate)
  - 6 parent tools (notifications, purchase approve/reject/convert,
    weekly meal plan approve, regenerate day)
  - 1 universal utility tool: `get_weather`
- `CONFIRMATION_REQUIRED` set (10 tools): same 10 as before — shared
  writes that require a second call with `confirmed=true`.
- `AIToolAudit` table + `GET /api/ai/audit` expose every invocation with
  `status ∈ {success, denied, confirmation_required, error, moderation_blocked}`,
  `duration_ms`, `result_summary` (truncated), and serialized arguments.
- Tools wrap existing service modules — no duplicated domain logic.

**Evidence**
- `tools.py` — 30 tool definitions, `CONFIRMATION_REQUIRED` set,
  `_get_weather` handler.
- `backend/tests/test_ai_tools.py` — **17 tests** including permission
  enforcement, confirmation gating, family isolation, and weather tool.
- Production DB: `ai_tool_audit` has real rows for `get_today_context`
  from live usage, confirming writes land in prod.

**Verification strength**
- Backend tests + production audit table confirmation. The production
  delta after one smoke chat turn was exactly +1 audit / +1 conversation
  / +4 messages, matching the orchestrator's persistence model.

**Gaps**
- No retention / pruning strategy for `ai_tool_audit`.
- Deployed browser test does not assert an audit row landed.

---

## 4. Conversation Persistence + `conversation_kind`
**Status: VERIFIED**

**What exists**
- `AIConversation` and `AIMessage` tables (see `app/models/ai.py`).
- `conversation_kind` column added in migration `015_ai_conversation_kind.sql`
  with values `chat | tool | mixed | moderation` set by
  `_tag_conversation_kind()` after each turn based on whether the turn
  used a tool and whether moderation blocked it.
- `get_or_create_conversation()` enforces family + member scoping.
- `_persist_message()` records user / assistant / tool messages, including
  tool calls, tool results, model name, and token usage.
- `_load_conversation_messages()` replays the last 40 messages into
  Anthropic API format on each turn.
- `GET /api/ai/conversations` + `GET /api/ai/conversations/{id}/messages`
  return family-scoped history.

**Evidence**
- `orchestrator.py` (persist + `_tag_conversation_kind`).
- `backend/tests/test_ai_routes.py` includes conversation scoping +
  `conversation_kind` coverage.
- Production backfill classified 5 conversations as `tool` and 3 as
  `chat` during migration 015 rollout.

**Verification strength**
- Backend tests + production row-count delta.

**Gaps**
- No UI path to **resume** a prior conversation on panel reopen — history
  is still reloaded from scratch each session.
- No per-member / per-surface history browser in the UI.

---

## 5. ScoutPanel Chat UX (Frontend)
**Status: VERIFIED**

**What exists**
- `scout-ui/components/ScoutLauncher.tsx` (597 lines) — slide-up modal with:
  - 6 quick-action chips
  - Message history with streaming assistant bubbles
  - **SSE streaming** via `sendChatMessageStream()`: `text` / `tool_start`
    / `tool_end` / `done` / `error` events patch the last assistant
    message as chunks arrive. Falls back to the non-streaming
    `/api/ai/chat` endpoint if the stream errors before producing text.
  - **Confirmation card** rendered from `pending_confirmation`. Confirm
    re-invokes `/api/ai/chat` (non-streaming) with `confirmTool` payload;
    Cancel dismisses.
  - **Disabled-state card** driven by a `readyState` state machine. On
    open, the panel calls `fetchReady()`; if `ai_available=false` the
    chat UI never mounts.
  - **Handoff cards** render from `result.handoff` and deep-link via
    `router.push(route_hint)` on tap.
- `scout-ui/lib/api.ts`:
  - `fetchReady()` — probes `/ready`.
  - `sendChatMessage()` — non-streaming JSON POST (used for the
    confirmation resubmit path).
  - `sendChatMessageStream()` — fetch-based SSE reader that parses
    `data: <json>\n\n` frames and calls `onEvent` per frame.
- `X-Scout-Trace-Id` generated client-side and forwarded in both
  streaming and non-streaming paths.

**Evidence**
- `ScoutLauncher.tsx` (streaming handler + confirmation card + disabled
  state + handoff cards).
- `lib/api.ts` (`sendChatMessageStream`, `fetchReady`).
- Backend: `orchestrator.chat_stream()` emits typed events; `routes/ai.py`
  wraps it in a `StreamingResponse` at `/api/ai/chat/stream`.
- `smoke-tests/tests/ai-panel.spec.ts` (3 tests) + `ai-roundtrip.spec.ts`
  (2 tests) exercise the local panel.
- Production round-trip: one real adult user (Andrew) and the smoke
  account both succeeded end-to-end through the deployed backend on
  2026-04-13.

**Verification strength**
- Backend tests for confirmation, streaming, and moderation paths.
- Frontend smoke tests for content, disabled-state, and child-surface
  panel open.
- **Production backend verified** via direct HTTPS round-trip and by a
  real user request captured in Railway logs.
- **Deployed browser smoke** (Playwright against Railway + Vercel) is
  still not wired into CI — see §10.

**Gaps**
- No conversation resume on reopen.
- No per-surface quick-action overrides.
- No E2E test for the streaming path against the deployed URLs.
- No test exercises the non-streaming fallback branch.

---

## 6. Handoff to Saved Objects
**Status: VERIFIED**

**What exists**
- Every write-tool handler returns `_handoff(entity_type, entity_id,
  route_hint, summary)`.
- Covered entity types: `personal_task`, `event`, `meal_plan`, `grocery_item`,
  `purchase_request`, `note`, `chore_instance`.
- Orchestrator surfaces `handoff` structurally on `ChatResponse`.
- Frontend renders handoffs as tappable cards that deep-link on press.
- `ai-roundtrip.spec.ts` asserts `add_grocery_item` handoff navigation
  into `/grocery` when Claude returns a handoff.

**Gaps**
- `send_notification_or_create_action` tool audits and logs but does not
  deliver via any transport.
- `dietary_preferences` is still not consumed by the meal-plan generator
  path.

---

## 7. Meal Generation Workflow
**Status: PARTIAL**

**What exists** — two distinct paths, kept deliberately separate:
1. **`orchestrator.suggest_staple_meals()`** → returns 5–7 staple meal ideas
   as free-form text. `POST /api/ai/meals/staples`. Currently unused by
   the UI.
2. **`weekly_meal_plan_service.py`** (790 lines) — the real AI-driven
   weekly plan loop (questions → answers → regenerate → approve). Wired
   into `scout-ui/app/meals/this-week.tsx` and is the path users actually
   take. `seed_smoke.py` now deterministically seeds a draft weekly plan
   for the current week so the Approve button is always visible for
   smoke tests.

**Evidence**
- `orchestrator.py` (staples method), `services/weekly_meal_plan_service.py`
  (the real loop).
- Backend tests: 39 weekly-meal tests.
- `smoke-tests/tests/meals-subpages.spec.ts` (3 tests) covers the
  `this-week` / `prep` / `reviews` page loads.

**Gaps**
- Dietary preferences table is still not read by the generator.
- Staple-meals endpoint has no UI consumer.
- No browser test drives a full AI generation loop (deliberate — slow).
- No UI indicator if generation times out or falls back.

---

## 8. Daily Brief / Summaries
**Status: IMPLEMENTED**

**What exists**
- `generate_daily_brief(db, family_id, member_id)` — ~200-word summary of
  today's tasks, events, meals, unpaid bills using a fixed read-tool
  allowlist.
- `generate_weekly_plan(db, family_id, member_id)` — ~300-word Mon–Sun
  plan highlighting commitments and deadlines.
- Routes: `POST /api/ai/brief/daily`, `POST /api/ai/plans/weekly`,
  `POST /api/ai/meals/staples`.
- **On-demand only**. Blocking. No scheduler, no cache, no email / push.

**Gaps**
- No scheduled runs → no morning brief without the user tapping a button.
- Up to 60s HTTP hold for a long generation.

---

## 9. Moderation / Safety Layer
**Status: VERIFIED** (new since last roadmap pass)

**What exists**
- `backend/app/ai/moderation.py` (227 lines).
- `check_user_message(db, message, actor_role, family_id, member_id)`
  runs a classifier-model pass with the Haiku classifier model; returns
  an allow / block decision with a redirect message.
- On block, the orchestrator:
  - Persists the user message.
  - Skips the Claude chat call entirely (no tokens spent).
  - Writes an `ai_tool_audit` row with `status='moderation_blocked'` and
    `tool_name='moderation'`.
  - Creates a `parent_action_items` row via `_create_moderation_alert`
    so the blocking incident surfaces in the parent Action Inbox.
  - Tags `conversation_kind='moderation'` for the conversation.
- Designed to avoid over-blocking: legitimate homework / chemistry /
  safety-research questions are allowed with a "teach, don't do"
  modifier when `allow_homework_help=true`.

**Evidence**
- `moderation.py` — classifier prompt, reason codes, redirect message
  template.
- `orchestrator.py` — block path, alert creation, conversation tagging.
- `test_ai_routes.py` — tests for moderation_blocked status path and
  parent alert creation.
- `ActionInbox.tsx` — renders `moderation_alert` entries on the parent
  dashboard.

**Gaps**
- No dashboard on moderation false-positive rate.
- No per-child moderation history browser.

---

## 10. Broad Chat / Homework Help / Weather
**Status: IMPLEMENTED** (new since last roadmap pass)

**What exists**
- **Family-level flags** on `families` table (migration 014 or later):
  `allow_general_chat` and `allow_homework_help`. Both default to `true`
  with `server_default='true'`.
- **Settings UI**: `scout-ui/app/settings/index.tsx` now includes two
  toggle rows (adult-only) that PATCH the flags via
  `/api/families/{id}/ai-settings`.
- Routes: `backend/app/routes/families.py` has
  `GET /api/families/{id}/ai-settings` + `PATCH` with `AISettingsUpdate`
  schema.
- **Prompt composition** in `context.py`:
  - Adult surfaces always permit general chat.
  - Child surface reads both flags and composes one of four prompt
    variants (chat off, chat on / homework on, chat on / homework off,
    homework on / chat off).
  - Child prompt explicitly instructs the model to **teach** homework
    rather than answer it.
- **`get_weather` tool**: available to all surfaces, queries Open-Meteo
  via `_get_weather()` with the family's `timezone` for the "today"
  bucket.

**Evidence**
- `context.py` — all four child-prompt variants.
- `tools.py` — `get_weather` definition + handler.
- `routes/families.py` — ai-settings routes.
- `settings/index.tsx` — toggle UI rows.
- Backend tests in `test_ai_context.py` cover all four prompt variants.

**Verification strength**
- Backend tests cover all four prompt variants and the weather tool.
- Settings UI toggles are not yet covered by a smoke test.

**Gaps**
- No browser smoke for the Settings AI-toggle flow.
- No rate limiting on the `get_weather` tool (Open-Meteo is generous but
  not unlimited).

---

## 11. Correlation Logging / Observability
**Status: VERIFIED**

**What exists**
- `routes/ai.py` reads `X-Scout-Trace-Id` from the incoming request and
  emits `ai_chat_start` / `ai_chat_success` / `ai_chat_fail` structured
  log lines with `trace`, `member`, `surface`, `confirm`, `handoff`, and
  `pending` fields. Streaming path logs `ai_chat_stream_start` /
  `ai_chat_stream_success` / `ai_chat_stream_fail`.
- `scout-ui/lib/api.ts` generates the trace id as `scout-<epoch>-<random>`
  and forwards it on both streaming and non-streaming calls.
- Output is stdout → Railway logs.

**Evidence**
- Railway log tail on 2026-04-13 shows matched `ai_chat_start` /
  `ai_chat_success` pairs with round-tripped trace ids for both the
  smoke account and one real adult user. The `confirm=` / `handoff=` /
  `pending=` fields are present, confirming the Sprint 1 closeout build
  is live.

**Verification strength**
- Source confirmed.
- Production round-trip confirmed on 2026-04-13.

**Gaps**
- No external dashboard (Grafana / Datadog / equivalent).
- No alerting on AI latency or error rate.
- No per-family or per-conversation cost tracking.
- `AIToolAudit` is per-tool, not per-turn — no structured event store
  for conversation-level metrics.

---

## 12. Browser-Based AI Verification
**Status: PARTIAL**

**Local coverage (runs in CI)**
- `smoke-tests/tests/ai-panel.spec.ts` — 3 tests:
  1. Content assertion — `ChatResponse.response` is a non-empty string
     with length > 3. Skips if `ai_available=false`.
  2. Disabled-state — stubs `/ready` via `page.route()` to return
     `ai_available: false` and asserts the disabled card renders and
     quick-action chips are not mounted.
  3. Child surface — logs in as the child user, opens the panel, and
     asserts the UI renders without a page-level error banner.
- `smoke-tests/tests/ai-roundtrip.spec.ts` — 2 tests (skip if AI is
  disabled):
  1. `add_grocery_item` quick-action round-trip with optional handoff
     tap and `/grocery` navigation assertion.
  2. `create_event` confirmation round-trip — asserts `pending_confirmation`
     surfaces, taps Confirm, asserts the follow-up response has
     `model='confirmation-direct'` and `pending_confirmation===null`.
- `smoke-tests/tests/error-boundary.spec.ts` — 1 test gated on
  `EXPO_PUBLIC_SCOUT_E2E=true`; verifies the global boundary render path
  when a DEV-gated `/__boom` route triggers a render crash.

**Deployed coverage**
- No CI job runs Playwright against `scout-ui-gamma.vercel.app`. The
  production AI path has been verified by a **direct HTTPS round-trip
  from an operator script**, which exercises the backend end-to-end but
  not the browser rendering layer.
- Operator checklist for running the full Playwright suite against the
  deployed URLs is documented in `docs/AI_OPERATOR_VERIFICATION.md` and
  uses the Railway-stored `SCOUT_SMOKE_ADULT_*` credentials.

**What is STILL not covered anywhere**
- Full tool-execution round-trip through the browser that verifies the
  created entity lands on the Personal / Grocery / Calendar screen
  (handoff tap lands the nav but there's no assertion on the target
  screen content).
- Streaming rendering path — the SSE chunks arrive in the panel but no
  Playwright test asserts per-chunk updates.
- Deployed browser run of any AI test against Railway + Vercel.

---

## 13. Production AI Deployment State
**Status: VERIFIED** (backend path verified; deployed browser not yet)

**What is VERIFIED**
- `/ready` returns `ai_available: true` in production.
- `SCOUT_ANTHROPIC_API_KEY` is set on Railway.
- Production direct HTTPS round-trip on 2026-04-13:
  - `POST /api/auth/login` as `smoke@scout.app` → 200, 64-char token.
  - `POST /api/ai/chat` with a real trace id → 200, `conversation_id`
    returned, `model=claude-sonnet-4-20250514`, `tool_calls_made=1`,
    762-char response.
- Railway logs show the matching `ai_chat_start` / `ai_chat_success`
  pair with the smoke trace id, plus one earlier pair from a real user
  (Andrew, member `2f25f0cc`) — proving the AI path was already working
  end-to-end before the operator pass.
- Production Postgres deltas: `ai_tool_audit=+1`, `ai_conversations=+1`,
  `ai_messages=+4` — exactly matches the orchestrator's persistence
  model.
- Family rename Whitfield → Roberts applied in prod Postgres + repo
  seeds in commit `782c3ef`.

**What is NOT VERIFIED**
- Running the full Playwright browser suite against
  `scout-ui-gamma.vercel.app` from CI. The direct HTTPS round-trip is a
  strong substitute but does not exercise the browser rendering path.

**Caveats**
- Models pinned by string — requires a code change to upgrade.
- No cost ceiling or rate ceiling at the application layer; relies on
  Anthropic account limits.

---

## Required Answers (explicit)

**Is the AI platform implemented?**
Yes. Provider (sync + streaming), orchestrator, context loader with
moderation + homework / broad-chat flags, 30 tools including
`get_weather`, confirmation flow, audit table, conversation persistence
with `conversation_kind` tagging, handoff cards, daily brief, weekly
plan, and moderation alerts are all in code with 58 backend AI tests.

**Is the AI panel verified through the real browser UI?**
**Locally yes** (3 `ai-panel` tests + 2 `ai-roundtrip` tests covering
content, disabled-state, child surface, tool round-trip, and
confirmation round-trip). **Against the deployed Vercel URL not yet**
in CI. The **production backend** has been verified end-to-end via a
direct HTTPS round-trip from `smoke@scout.app`, plus a real user
request captured in Railway logs from Andrew.

**Is the AI request/response or streaming?**
**Both.** `/api/ai/chat` is request/response (used for the confirmation
resubmit path); `/api/ai/chat/stream` is SSE. The frontend uses
`sendChatMessageStream()` by default and falls back to the non-streaming
endpoint if the stream fails before producing text.

**Which AI behavior is launch-sufficient but not strategically complete?**
- Deployed browser smoke — backend verified, browser-through-Vercel
  smoke not yet wired into CI.
- Provider retry / fallback on 5xx — single point of failure at
  Anthropic.
- On-demand daily brief / weekly plan — nobody sees them without tapping
  a button.
- `send_notification_or_create_action` tool — audits and logs but does
  not deliver.
- `dietary_preferences` → weekly generator wiring — still unconsumed.
- Conversation resume on panel reopen — history persists server-side
  but the UI always opens blank.
- Prompt caching — every turn rebuilds the static prefix.
- Per-family cost / token observability.

**Which AI regressions are now protected by tests, and which are still
weakly protected?**

**Well protected:**
- Tool permission / allowlist per role and surface
  (`test_ai_context.py`, `test_ai_tools.py`).
- Confirmation gating on shared-write tools (`test_ai_tools.py`,
  `test_ai_routes.py::TestPendingConfirmationPlumbing`).
- Cross-family isolation for tools and conversations (`test_ai_routes.py`,
  `test_ai_tools.py`).
- Audit row creation on success / denied / confirmation_required /
  moderation_blocked paths.
- Moderation block path (classifier → block → parent alert → conversation
  tag) — tested in `test_ai_routes.py`.
- All four child-prompt variants (chat on/off × homework on/off) —
  `test_ai_context.py`.
- ScoutPanel content + disabled-state + child-surface open
  (`ai-panel.spec.ts`).
- ScoutPanel tool round-trip + handoff tap + confirmation round-trip
  (`ai-roundtrip.spec.ts`, conditional on `ai_available=true`).
- Global `ErrorBoundary` render path (`error-boundary.spec.ts`, gated on
  `EXPO_PUBLIC_SCOUT_E2E`).
- Production backend chat path (direct HTTPS round-trip evidence).

**Weakly protected:**
- Streaming rendering in the browser — no Playwright assertion on
  incremental chunks.
- Conversation resume across panel opens — no UI path.
- Weekly meal plan generation loop through the UI.
- Daily brief / weekly plan endpoints through the UI.
- Settings AI-flag toggle round-trip through the UI.
- **Deployed browser** behavior for any AI path — operator checklist
  only; not in CI.

---

## AI Panel Hardening Still Needed

Items that are **still true** after Sprint 1 residual closeout + the
Sprint 2 feature work (broad chat / homework / moderation / streaming):

- **Deployed browser smoke in CI.** Direct HTTPS round-trip has been
  done; a full Playwright run against `scout-ui-gamma.vercel.app` using
  the Railway-stored smoke credentials has not been wired into CI.
  Operator checklist in `docs/AI_OPERATOR_VERIFICATION.md`.
- **Provider retry / fallback.** A 5xx from Anthropic currently surfaces
  as an error banner to the user.
- **Observability dashboards.** Structured log lines + `ai_tool_audit`
  exist but there is no dashboard, no alert, and no per-family cost
  tracking.
- **Streaming assertion depth.** Playwright covers the non-streaming
  path via `pending_confirmation`; the SSE path is exercised locally by
  the panel but there is no test that asserts chunks arrived before
  `done`.
- **Conversation resume in UI.** Phase C item; still not built.
- **Prompt caching.** Sprint 2 tail.
- **Moderation false-positive telemetry.** No feedback loop for parents
  to flag a block that was wrong.

Previously-listed items **now resolved** (do not re-open):
- ~~Assertion strength in `ai-panel.spec.ts`~~ — content assertion
  landed in Sprint 1 closeout.
- ~~Disabled-state handling in the UI~~ — `fetchReady()` + readyState
  machine + disabled-state card.
- ~~Confirmation-flow UI~~ — structural `pending_confirmation` +
  confirm card + `confirm_tool` resubmit path.
- ~~Child-surface coverage~~ — `ai-panel.spec.ts` child-surface test +
  `test_ai_context.py` variants.
- ~~Handoff deep-link test~~ — covered by `ai-roundtrip.spec.ts`.
- ~~Streaming pipeline~~ — SSE landed in `4e8d2e9`.
- ~~Production AI backend verification~~ — verified on 2026-04-13 via
  `smoke@scout.app` direct round-trip + real user request in logs.

---

## File Summary (current as of `4e8d2e9`)

| Area | File | Lines | Purpose |
|---|---|---|---|
| Provider | `backend/app/ai/provider.py` | 177 | Anthropic wrapper, sync + streaming |
| Context | `backend/app/ai/context.py` | 310 | Role-aware prompt + allowlist + chat flags |
| Orchestrator | `backend/app/ai/orchestrator.py` | 877 | Chat loop + `chat_stream` + moderation + kind tagging |
| Tools | `backend/app/ai/tools.py` | 1149 | 30 tool definitions + executor + weather |
| Moderation | `backend/app/ai/moderation.py` | 227 | Classifier-backed safety pass |
| Routes | `backend/app/routes/ai.py` | 231 | `/chat`, `/chat/stream`, `/brief/daily`, `/plans/weekly`, `/meals/staples`, `/conversations`, `/audit` |
| Family AI routes | `backend/app/routes/families.py` (§ai-settings) | — | `GET`/`PATCH /api/families/{id}/ai-settings` |
| Schemas | `backend/app/schemas/ai.py` | 131 | Pydantic request/response + confirm/handoff/pending |
| Frontend panel | `scout-ui/components/ScoutLauncher.tsx` | 597 | Streaming + confirmation + disabled-state + handoff |
| Frontend API | `scout-ui/lib/api.ts` (AI block) | — | `fetchReady`, `sendChatMessage`, `sendChatMessageStream` |
| Settings UI | `scout-ui/app/settings/index.tsx` | — | AI flag toggles |
| Backend tests | `backend/tests/test_ai_context.py` | 257 | 26 tests |
| Backend tests | `backend/tests/test_ai_routes.py` | 510 | 15 tests (incl. moderation, `conversation_kind`, pending plumbing) |
| Backend tests | `backend/tests/test_ai_tools.py` | 330 | 17 tests (incl. weather) |
| Smoke test | `smoke-tests/tests/ai-panel.spec.ts` | 135 | 3 tests |
| Smoke test | `smoke-tests/tests/ai-roundtrip.spec.ts` | 182 | 2 tests (conditional) |
| Smoke test | `smoke-tests/tests/error-boundary.spec.ts` | 65 | 1 test (gated on E2E flag) |

**Total AI backend tests: 58** (26 context + 15 routes + 17 tools).
**Total backend tests: 349** (`pytest` local run, 2026-04-13).
**Total Playwright tests: 28** across 8 files.

---

## Top 10 AI Deferred Items (after Sprint 2 feature work)

1. **Deployed browser smoke in CI.** Direct HTTPS round-trip done;
   Playwright against Vercel not yet wired.
2. **Provider retry / fallback on upstream 5xx.** A single Anthropic
   hiccup still surfaces as a user-visible error.
3. **Cost / latency / per-family observability.** Logs exist, dashboards
   do not.
4. **Scheduled daily brief / weekly plan delivery.** On-demand only;
   no cron, no push, no Action Inbox entry on a schedule.
5. **`send_notification_or_create_action` delivery channel.** Tool
   audits and logs; no transport.
6. **`dietary_preferences` → weekly-plan generator wiring.** Table
   exists; generator ignores it.
7. **Conversation resume across sessions.** Panel always opens blank.
8. **Prompt caching.** Every turn rebuilds the static prefix.
9. **Streaming assertion depth in smoke.** Stream path is used but not
   explicitly asserted chunk-by-chunk.
10. **Moderation false-positive feedback loop.** No parent-facing way
    to flag an over-block.

---

## 5 Strongest AI Capabilities

1. **Streaming SSE chat path** with graceful fallback to non-streaming
   when the stream errors. End-to-end from Anthropic → server generator
   → frontend chunked render.
2. **Role-aware tool allowlist with 10-tool confirmation gating and full
   audit trail.** 30 tools, three role tiers, 17 `test_ai_tools.py`
   tests, plus production DB rows confirming writes land.
3. **Classifier-backed moderation with parent Action Inbox alerts and
   `conversation_kind` tagging.** Blocks do not spend Claude tokens and
   are surfaced to parents via the existing Action Inbox surface.
4. **Production AI backend verified end-to-end** via direct HTTPS
   round-trip + real user request in Railway logs + matching production
   DB row deltas on 2026-04-13.
5. **Family-level AI settings** (`allow_general_chat`, `allow_homework_help`)
   wired from the Settings UI through to the child prompt variants,
   with backend tests covering all four combinations.

---

## 5 Weakest / Least-Verified AI Areas

1. **Deployed browser smoke in CI.** Backend verified, but the full
   Playwright suite has never run against `scout-ui-gamma.vercel.app`
   from an automated job.
2. **Streaming assertion depth.** Streaming is live and used; no test
   asserts chunk-by-chunk rendering.
3. **Observability dashboards / cost tracking.** Log lines exist; no
   aggregation layer, no dashboards, no per-family budget.
4. **Scheduled generation.** Daily brief and weekly plan are on-demand
   only.
5. **Settings AI-toggle browser smoke.** The adult can toggle
   `allow_general_chat` / `allow_homework_help`; no browser test exercises
   the round-trip.

---

## AI VERIFIED Today

Strictly: code + tests + real production evidence.

- **Production backend AI round-trip.** `smoke@scout.app` → 200 chat
  response with a real conversation id and a tool call. Real adult user
  pair captured in logs.
- **Production Postgres persistence.** `ai_tool_audit`, `ai_conversations`,
  and `ai_messages` row counts all incremented in lockstep.
- **Railway correlation logs.** `ai_chat_start` / `ai_chat_success`
  pairs with round-tripped trace ids and the new confirm/handoff/pending
  fields.
- **Streaming SSE path.** Wired server and client; locally exercised via
  the panel.
- **Confirmation flow.** Backend plumbing + `confirm_tool` direct path +
  frontend card + pytest coverage + smoke round-trip test.
- **Moderation block path.** Classifier → block → `moderation_blocked`
  audit + parent alert + `conversation_kind='moderation'`.
- **Role-aware tool allowlist** with 30 tools × 3 role tiers × 2 family
  AI flags.
- **Cross-family isolation** for tools, conversations, messages, and
  audit.
- **Local Playwright coverage** for content, disabled-state, child
  surface, tool round-trip, confirmation round-trip, and error boundary.
- **Global `ErrorBoundary`** wrapping the app shell, with a gated E2E
  test proving the render path.

---

## AI Implemented but Not Strongly Verified

- **Deployed browser path against Vercel URLs in CI.** Backend verified;
  browser-level run is operator-only.
- **Streaming chunk-by-chunk rendering.** Panel uses it; no Playwright
  assertion on per-chunk state.
- **Settings AI-toggle round-trip through the UI.**
- **Daily brief / weekly plan endpoints through the UI.**
- **Weekly meal plan generation loop through the UI** (deliberately
  unsmoked — slow).
- **Moderation false-positive telemetry.**

---

## AI Deferred Ledger

| # | Item | Why deferred | Launch impact | Next window |
|---|---|---|---|---|
| 1 | Deployed browser smoke in CI against Vercel | Direct HTTPS round-trip was cheaper and proved the backend path | Drift between local and Vercel can land unseen | Sprint 2 |
| 2 | Provider retry / fallback on 5xx | Anthropic reliability acceptable today | User sees error banner on hiccup | Sprint 2 |
| 3 | Cost / latency / per-family dashboards | Log grep works at family scale | None today; rises with usage | Sprint 2 tail |
| 4 | Scheduled daily brief / weekly plan | On-demand works | Lower engagement | Sprint 2 |
| 5 | `send_notification_or_create_action` real delivery | Action Inbox covers the need | None | Later |
| 6 | `dietary_preferences` → generator wiring | Generator still produces usable plans | Low today | Sprint 2 |
| 7 | Conversation resume in UI | Panel always opens blank | Low | Later |
| 8 | Prompt caching | Per-turn rebuild is fine at current volume | None | Later |
| 9 | Second provider | Single-provider risk acceptable for private use | SPOF | Later |
| 10 | Streaming assertion depth in smoke | Basic smoke sufficient | Low | Sprint 2 tail |
| 11 | Moderation false-positive feedback loop | Classifier is tuned conservatively | Low | Later |
| 12 | Audit / conversation retention policy | Volume is small | None | Later |
| 13 | Autonomous multi-step planning | Out of scope | None | Not planned |
| 14 | Photo / doc / voice intelligence pipelines | Out of scope | None | Not planned |
| 15 | Custom fine-tuning | Out of scope | None | Not planned |

---

## AI Unknowns

- Whether the full Playwright suite would pass against
  `https://scout-ui-gamma.vercel.app` today. Direct HTTPS round-trip
  says the backend path is healthy; the browser-rendering path against
  the deployed bundle has not been tested in this pass.
- Whether the weekly meal plan generation loop completes end-to-end
  against production Postgres within the 60s request timeout.
- Whether current production Anthropic usage is within account
  rate/cost ceilings (no app-layer telemetry).
- Whether the moderation classifier is over-blocking in practice
  (no feedback loop).

---

## Recommended Sequence

**Sprint 2 — Close the remaining trust gaps**
1. CI job that runs Playwright against `scout-ui-gamma.vercel.app` using
   the Railway-stored smoke credentials.
2. Provider retry-with-backoff on 5xx.
3. `dietary_preferences` → weekly-plan generator wiring.
4. Structured cost / latency log format + minimal aggregation script.
5. Scheduled daily brief delivery via `parent_action_items`.
6. Settings AI-toggle browser smoke.
7. Prompt caching for the static prefix (cheap; defensible).

**Later (strategic, not launch-gate)**
- Conversation resume + per-member history browser.
- Second provider for redundancy.
- Moderation false-positive feedback loop.

**Out of scope**
- Photo / doc / voice intelligence pipelines.
- Autonomous multi-turn planning loops.
- Cross-family or anonymized intelligence.
- Custom fine-tuned models.
