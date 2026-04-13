# Scout AI Roadmap

Last reconciled: 2026-04-12 against commit `9481f8f` on `main`.

This is the first AI roadmap for Scout. It captures the real state of the
orchestration layer, the shipped tool surface, known AI debt, and the
sequence of work that would actually move Scout's AI forward.

## Status Legend

- **VERIFIED** — code + tests + exercised in deployed smoke.
- **IMPLEMENTED** — code present but not strongly verified end-to-end.
- **PARTIAL** — only part of the intended surface exists.
- **DEFERRED** — intentionally postponed.
- **UNKNOWN** — not enough evidence.

## 1. AI Provider / Orchestration Layer
Status: **VERIFIED**

- Anthropic-first provider (`backend/app/ai/provider.py`). Hardcoded models:
  `claude-sonnet-4-20250514` (chat / summary), `claude-haiku-4-20250414`
  (classification).
- Config: `SCOUT_ANTHROPIC_API_KEY`, `SCOUT_AI_*_MODEL`, `SCOUT_AI_MAX_TOKENS=2048`,
  `SCOUT_AI_TEMPERATURE=0.3`, `SCOUT_AI_REQUEST_TIMEOUT=60`, `SCOUT_ENABLE_AI`.
- Graceful disable: `ai_available` on `/ready` reflects whether a key is set.
- Orchestration loop in `backend/app/ai/orchestrator.py`: load context → build
  system prompt → AI call → one tool per round, max 5 rounds.

**Known debt (intentional today):**
- **Request/response only — no streaming.** Frontend waits for the full JSON
  response before showing text. This is the single largest perceived-latency
  issue in the product.
- No provider fallback / retry. A 5xx from Anthropic surfaces as a user-visible
  error.
- No prompt caching. Every turn rebuilds the full system prompt.

## 2. Role-Aware Context Loading
Status: **VERIFIED**

- `backend/app/ai/context.py` loads role tier, permissions, behavior config,
  and (for adults) the list of active children.
- System prompt is assembled per (role, surface) with three documented
  variants: adult-personal, adult-parent, child.
- Tool allowlist is computed per request in `get_allowed_tools_for_surface()`.
- Adults get 13 write tools, parents get 6 additional, children get 3 (grocery
  add, purchase request, meal review).
- Prompt injection resistance: content from notes / events / connectors is
  tagged as DATA, not instructions.
- Tests: `backend/tests/test_ai_context.py` (13 tests).

## 3. Tool Registry, Confirmation, Audit
Status: **VERIFIED**

- `backend/app/ai/tools.py` (994 lines) — 17 tools wrapping existing services
  (no domain logic duplication).
- `CONFIRMATION_REQUIRED` set covers shared-write tools (create/update event,
  approve/reject purchase request, mark chore complete, approve meal plan,
  send notification, etc.).
- Confirmation flow: tool returns `{confirmation_required: true, ...}` on the
  first call; UI must re-invoke with `confirmed=true`.
- `AIToolAudit` table captures every tool invocation with
  `status in (success | denied | confirmation_required | error)`,
  `duration_ms`, `result_summary` (500 char max), and full arguments.
- `GET /api/ai/audit` returns audit history.
- Tests: `test_ai_tools.py` (18 tests), `test_ai_routes.py` (8 tests).

## 4. ScoutPanel Chat UX (Frontend)
Status: **IMPLEMENTED** (thinly smoked)

- `scout-ui/components/ScoutLauncher.tsx` — slide-up modal, quick-action chips,
  message history.
- 6 quick actions: "What does today look like?", "What's off track?",
  "Add a task", "Add to grocery list", "Plan meals for next week",
  "What do the kids still need to finish?".
- Client generates `X-Scout-Trace-Id` for correlation with backend logs.
- Handoff buttons render from `result.handoff` — tap deep-links into the
  created entity (task, event, meal plan, grocery item, etc.).
- **Not streaming** — `sendChatMessage()` awaits a single JSON response.

Gaps:
- No in-panel affordance for the confirmation flow today. The backend returns
  `confirmation_required`; the panel would need a UI round to surface it.
- No conversation resume across sessions (conversations persist server-side
  but the panel does not restore on reopen).
- No typing indicator (because no streaming).

## 5. AI Handoff Into Saved Objects
Status: **VERIFIED**

- All write-tool handlers return `_handoff(entity_type, entity_id, route_hint,
  summary)`.
- Entity types covered: personal_task, event, meal_plan, grocery_item,
  purchase_request, note, chore_instance.
- Every shared-data write is confirmation-gated.
- Services hit are the same ones the UI uses directly — no duplicate paths.

Gaps:
- `send_notification_or_create_action` is logged but not delivered.
- `dietary_preferences` is not read by the meal-plan generation path.

## 6. Meal Generation Workflow
Status: **PARTIAL**

Two distinct paths exist and should not be confused:

1. **`suggest_staple_meals()`** in `orchestrator.py` — AI returns 5–7 staple
   meal suggestions as free text. No DB write. Used for ideation.
2. **`weekly_meal_plan_service`** (790 lines) — the real AI-driven weekly plan
   flow, with a multi-step questions → answers → regenerate → approve loop.
   This is wired into `scout-ui/app/meals/this-week.tsx` and is the path users
   actually take.

Gaps:
- Dietary preferences table is not consumed by the generator.
- No smoke test for the generation loop (see §9).
- Staple-suggestions endpoint is separate from the weekly-plan path; no UI
  currently consumes it.

## 7. Daily Brief / Summaries
Status: **IMPLEMENTED**

- `generate_daily_brief(db, family_id, member_id)` — ~200 word summary of
  today's tasks, events, meals, unpaid bills.
- `generate_weekly_plan(db, family_id, member_id)` — ~300 word Mon–Sun plan
  highlighting commitments and deadlines.
- Routes: `POST /api/ai/brief/daily`, `POST /api/ai/plans/weekly`.
- **On-demand only**. No scheduled generation, no cache, no email / push.

Gaps:
- No scheduled runs → no morning brief without user tapping a button.
- Response is blocking — long generations hold the request open up to 60s.

## 8. Correlation Logging / Observability
Status: **VERIFIED** (new as of commit `9481f8f`)

- `backend/app/routes/ai.py` reads `X-Scout-Trace-Id` from incoming requests.
- Structured logs: `ai_chat_start trace=… member=… surface=…`,
  `ai_chat_success trace=… conversation=…`, `ai_chat_fail trace=… error=…`.
- Frontend generates `scout-${Date.now()}-${random}` trace and forwards it.
- Output is stdout → Docker / Railway logs. No external telemetry yet.

Gaps:
- No dashboards or alerts on AI latency / error rate.
- No cost tracking per conversation / family.
- No structured event store (audit table is per-tool, not per-turn).

## 9. Playwright AI-Panel Coverage
Status: **PARTIAL** (explicitly thin)

- `smoke-tests/tests/ai-panel.spec.ts` — one test:
  1. Check `/ready` for `ai_available: true`; skip gracefully otherwise.
  2. Adult login → open Scout AI → fire a quick action.
  3. Assert 200 response and absence of "Something went wrong".
- ~94 lines total.

**Does NOT test:**
- Actual tool execution
- Confirmation flow
- Role restrictions
- Conversation history / resume
- Different surfaces (personal vs parent)
- Handoff button taps

This is the single biggest AI coverage gap. Captured in the deferred ledger.

## 10. Production AI Deployment State
Status: **VERIFIED**

- `SCOUT_ANTHROPIC_API_KEY` set in production (`c29a5d0`).
- `/ready` returns `ai_available: true`.
- Deployed AI panel smoke passes in `docs/release_candidate_report.md`.
- Feature-flag gating is fail-closed: missing key → AI disabled, not crashed.
- Default timeout: 60s. Default temperature: 0.3.

**Caveats:**
- Models are pinned by version string — safe, but requires a code change to
  upgrade.
- No cost ceiling or rate ceiling at the application layer; relies on
  Anthropic account limits.

## AI Capabilities Explicitly NOT Yet Built

- Streaming responses
- Background / scheduled generation (morning brief, weekly plan)
- Cost tracking + budgets
- Conversation resume across sessions
- Multi-turn confirmation inside the panel
- Prompt caching
- LLM-driven photo / document / voice pipelines
- Any autonomous loop (agent-style planning across turns)
- Provider fallback (single-provider risk)

## Recommended Sequence

**Phase A — Coverage + Quality of Life (before any new AI capability)**
1. AI smoke depth: tool execution, confirmation flow, conversation resume.
2. Streaming response pipeline (server SSE → client incremental render).
3. Provider fallback or at minimum retry-with-backoff on 5xx.
4. Dietary preferences → weekly-plan generator wiring.
5. Basic cost + latency dashboards (stdout logs → lightweight aggregation).

**Phase B — Predictive / Copilot depth (after Phase A)**
1. Scheduled morning brief delivery (email or Action Inbox entry).
2. "What's off track?" as a real rule-engine-backed explanation, not just a
   chat prompt.
3. Confirmation UI flow inside the ScoutPanel (multi-turn confirm).
4. Notification delivery channel for `send_notification_or_create_action`.

**Phase C — Ambient / optimization (only after Phases A and B land)**
1. Conversation resume + per-member history.
2. Prompt caching for the static parts of the system prompt.
3. Budget ceilings per family.
4. Optional: second provider for model diversity or redundancy.

## Out of Scope For Now

- Photo / doc / voice intelligence pipelines
- Autonomous multi-turn planning loops
- Cross-family or anonymized intelligence
- Custom fine-tuned models

## Deferred AI Debt Ledger

| Item | Why deferred | Launch impact | Next window |
|---|---|---|---|
| Streaming responses | Request/response works; streaming is UX debt | Perceived latency on long replies | Phase A |
| AI panel smoke depth (tools, confirmation, history) | Happy-path smoke sufficient for launch gate | Medium — regressions in tool flow wouldn't be caught | Phase A |
| Provider fallback / retry on 5xx | Anthropic reliability has been acceptable | User sees error on upstream hiccup | Phase A |
| `send_notification_or_create_action` delivery | Action Inbox covers the need | None | Phase B |
| Dietary preferences → generator wiring | Generator still produces usable plans | Low | Phase A |
| Scheduled daily brief generation | On-demand works | Lower engagement | Phase B |
| Cost / latency dashboards | Log-grepping works at single-family scale | None for launch | Phase A tail |
| Conversation resume in UI | Conversations persist server-side but not restored | Low | Phase C |
| Prompt caching | Per-turn rebuild is fine at current volume | None | Phase C |
| Second provider | Single-provider risk is acceptable for private use | Single point of failure | Later |
| Confirmation flow UI in ScoutPanel | Backend returns `confirmation_required`; UI does not render it yet | Write tools requiring confirmation currently awkward | Phase B |
