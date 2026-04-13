# Scout Backend Roadmap

Last reconciled: 2026-04-13 against commit `4e8d2e9` on `main`.

This roadmap is organized by backend capability area. It is the planning layer for
the backend — not a changelog dump. Each section lists current status, evidence,
gaps, and next work. See `docs/ROADMAP_RECONCILIATION.md` for the cross-surface
summary that answers "what is actually done?"

## Status Legend

- **VERIFIED** — present in code AND exercised by passing tests, smoke coverage,
  or deployed verification.
- **IMPLEMENTED** — present in code but not strongly verified end-to-end.
- **PARTIAL** — only part of the intended surface exists.
- **DEFERRED** — intentionally postponed; reason captured below.
- **UNKNOWN** — not enough evidence in the repo to judge either way.

## 0. Foundation / Family Model
Status: **VERIFIED**

Scope:
- `families`, `family_members`, `user_accounts`, `sessions`
- `role_tiers`, `role_tier_overrides`
- `connector_configs`, `connector_mappings`

Evidence:
- `backend/app/models/foundation.py`
- `backend/app/services/family_service.py`
- `backend/app/routes/families.py`
- `database/foundation.sql`, migration `001_foundation_connectors.sql`
- `backend/tests/test_tenant_isolation.py` enforces family scoping
- No hardcoded `FAMILY_ID` anywhere in routes/services; `/api/auth/me` returns family context
- Bootstrap is disabled when any account exists (fail-closed in production)

Gaps:
- None known. Connector infrastructure is scaffolded but external sync is tracked
  under §9 Integrations.

## 1. Auth / Sessions / Accounts
Status: **VERIFIED**

Scope:
- Email/password login, bearer-token sessions, rate limiting
- Bootstrap (first-run only, disabled after accounts exist)
- Password change, admin-initiated password reset
- Session listing/revocation, per-member account lifecycle

Evidence:
- `backend/app/routes/auth.py`, `backend/app/services/auth_service.py`
- Endpoints: `POST /api/auth/login` (10/5min rate limit), `logout`, `me`,
  `bootstrap`, `password/change`, `password/reset`, `sessions`, `accounts`
- `backend/tests/test_auth.py` (40 tests covering login, logout, sessions,
  bootstrap, password, role enforcement)
- `SCOUT_AUTH_REQUIRED=true` enforced at startup in production
- Verified in deployed private-launch smoke (see `docs/private_launch.md`)

Gaps:
- Rate limiter is in-memory. Acceptable for single-instance backend; see
  Deferred Ledger for multi-instance risk.
- No OAuth / SSO. Not in scope for private family launch.

## 2. Household Ops — Routines, Chores, Allowance, Daily Wins
Status: **VERIFIED**

Scope:
- `routines`, `routine_steps`, `chore_templates`
- `task_instances`, `task_instance_step_completions`
- `daily_wins`, `allowance_ledger`
- Step-completion rollup, weekly payout calculation

Evidence:
- `backend/app/models/life_management.py`
- Services: `routine_service.py`, `chore_service.py`, `daily_win_service.py`,
  `payout_service.py`
- Routes: `routines.py`, `chores.py`, `task_instances.py`, `daily_wins.py`,
  `allowance.py`
- Tests: `test_daily_wins.py` (11), `test_payout.py` (13), `test_task_generation.py`
- Used on parent + child dashboards in production smoke.

Gaps:
- Bonus / penalty mechanics (parent-applied adjustments) not backed by a
  dedicated endpoint. UI currently stubs these. See Deferred Ledger.

## 3. Calendar / Scheduling
Status: **VERIFIED**

Scope:
- `events`, `event_attendees`
- RRULE-based recurrence (application-side expansion)
- Edited-instance overrides, source tracking (`scout | google_cal | ical`)
- `is_hearth_visible` flag, optional `task_instance_id` linkage

Evidence:
- `backend/app/models/calendar.py`, `services/calendar_service.py`,
  `routes/calendar.py`
- Migrations: `003_calendar.sql`, `004_connector_ical_support.sql`
- Tests: `test_calendar.py`, `test_connector_ical.py`
- Calendar data rendered on parent + personal + child dashboards in smoke runs.

Gaps:
- Recurrence expansion is deliberately app-side, not DB-side. No DB view or
  materialized table of concrete instances. This is intentional; listed for
  clarity.

## 4. Tasks / Notes / Finance / Health
Status: **VERIFIED**

### Personal Tasks
- Model + service + routes; top-N, due-today, complete transition
- `backend/tests/test_personal_tasks.py` (11 tests)

### Notes (Second Brain)
- Model + service + routes with ILIKE search, archive/unarchive
- `backend/tests/test_notes.py`
- No full-text index, no vector store, no tags. Intentionally minimal.

### Finance (Bills)
- Model + service + routes: upcoming / overdue / unpaid, pay / unpay
- `source` CHECK includes `ynab` for future connector
- `backend/tests/test_finance.py`

### Health / Fitness
- `health_summaries`, `activity_records` with source tracking
- `backend/tests/test_health_fitness.py`
- No ingestion engines yet — see §9 Integrations.

Gaps:
- No rollups / aggregated family views for health. Intentional for v1.

## 5. Meals
Status: **VERIFIED**

Scope:
- `meal_plans`, `meals`, `dietary_preferences`
- One-meal-per-type-per-day uniqueness
- Weekly plan with Monday `week_start` CHECK
- **AI-driven weekly plan generation** (see AI Roadmap §5 for the workflow)
- Staple meal suggestions

Evidence:
- `backend/app/models/meals.py`
- Services: `meals_service.py` (221 lines), `weekly_meal_plan_service.py` (790 lines)
- `backend/app/routes/meals.py` (25 route functions)
- Migrations: `005_meals.sql`, `013_meals_weekly_plans.sql`
- Tests: `test_meals.py` (15), `test_meals_routes.py` (39), `test_weekly_meal_plans.py` (39)

Gaps:
- No recipe library, no nutrition tracking — intentional.
- `dietary_preferences` exists but is not wired into AI meal generation yet.
  See Deferred Ledger.

## 6. Grocery / Purchase Requests / Parent Action Items
Status: **VERIFIED** (new since prior roadmap)

Scope:
- `grocery_items` with parent review/approve/reject flow
- `purchase_requests` with approve/reject/convert-to-grocery
- `parent_action_items` surfaced via dashboard

Evidence:
- `backend/app/models/grocery.py`, `models/action_items.py`
- `backend/app/services/grocery_service.py` (396 lines)
- `backend/app/routes/grocery.py` (11 route functions)
- Migrations: `011_grocery_purchase_requests.sql`, `012_parent_action_items.sql`
- Tests: `test_grocery.py` (26 tests)
- Action inbox rendered on parent dashboard; bidirectional child → parent flow
  verified in deployed smoke.

Gaps:
- `parent_action_items` has models but no dedicated route module; surfaced only
  through the dashboard aggregation service. Fine for current UX; worth a
  dedicated route module if Action Inbox gains filtering/pagination.

## 7. AI Orchestration
Status: **VERIFIED** (updated 2026-04-13 after Sprint 2 feature work; see
`AI_ROADMAP.md` for depth)

Scope at the backend layer:
- Anthropic provider abstraction with **both `chat()` (sync) and
  `chat_stream()` (SSE)** surfaces (`provider.py`, 177 lines)
- Role-aware context loader with family-level `allow_general_chat` and
  `allow_homework_help` flags (`context.py`, 310 lines)
- **30-tool** registry wrapping existing services, including the new
  universal `get_weather` tool (`tools.py`, 1149 lines)
- Role × surface permission enforcement
- Confirmation-gated shared writes (10 tools in `CONFIRMATION_REQUIRED`)
- Bounded 5-round tool-execution loop + SSE streaming generator
- Structural surfacing of `pending_confirmation` and `handoff` in
  `ChatResponse`; `confirm_tool` direct-execution path that bypasses the
  LLM round (Sprint 1 closeout, `5f11821`)
- **Moderation layer** (`moderation.py`, 227 lines) — classifier-backed
  safety pass that blocks before any Claude tokens are spent, writes an
  audit row with `status='moderation_blocked'`, creates a
  `parent_action_items` alert, and tags `conversation_kind='moderation'`
  (Sprint 2, `8647e00` + `4e8d2e9`)
- **`conversation_kind` tagging** (`chat | tool | mixed | moderation`)
  per turn via `_tag_conversation_kind()` (migration 015)
- Full audit logging per tool call, including moderation blocks and
  direct-confirm paths

Evidence:
- `backend/app/ai/provider.py`, `context.py`, `orchestrator.py` (877 lines),
  `tools.py`, `moderation.py`
- `backend/app/routes/ai.py` (231 lines) — 8 endpoints:
  `/chat`, **`/chat/stream`**, `/brief/daily`, `/plans/weekly`,
  `/meals/staples`, `/conversations`, `/conversations/{id}/messages`,
  `/audit`
- `backend/app/routes/families.py` — new
  `GET`/`PATCH /api/families/{id}/ai-settings` for the chat flags
- `backend/app/schemas/ai.py` (131 lines) — `ConfirmToolPayload`,
  `HandoffPayload`, `PendingConfirmation`, extended `ChatRequest`/`ChatResponse`,
  SSE event types
- Migrations: `010_ai_orchestration.sql`, `015_ai_conversation_kind.sql`
- Tests: `test_ai_context.py` (**26**), `test_ai_routes.py` (**15**,
  including `TestPendingConfirmationPlumbing` + moderation +
  `conversation_kind`), `test_ai_tools.py` (**17**, including weather).
  Total: **58 AI backend tests**.
- **Production backend verified end-to-end on 2026-04-13** via
  `smoke@scout.app` HTTPS round-trip + real user request captured in
  Railway logs. See `docs/AI_OPERATOR_VERIFICATION.md` and
  `docs/release_candidate_report.md`.

Gaps:
- No provider retry / fallback on upstream 5xx.
- `send_notification_or_create_action` tool logs but does not deliver
  via any transport.
- No background scheduler; daily brief / weekly plan are on-demand only.
- No prompt caching for the static system-prompt prefix.
- No cost or token-budget observability at the app layer.
- Moderation false-positive rate is not telemetered.

## 8. Dashboard Aggregation
Status: **VERIFIED**

- Cross-domain read service assembling personal, parent, and child views.
- `backend/tests/test_dashboard.py` (11 tests)
- Powers action inbox, kids-today status, weekly progress on parent surface.

## 9. Integrations / Connectors
Status: **PARTIAL**

Scope in place:
- Shared upsert helper `services/integrations/base.py` using `connector_mappings`
- Google Calendar v1 ingestion (payload schema + batch + source-of-truth conflict)
- YNAB v1 ingestion (preserves Scout-side paid state on re-ingestion)
- Apple Health / Nike Run Club stub endpoints (501)
- Internal ingestion POST routes for dev-mode triggers

Evidence:
- `backend/tests/test_integrations.py` covers create/update/source-conflict/dedup
- Dev-mode ingestion buttons wired into the personal dashboard for smoke runs.

Deliberately not built (see Deferred Ledger):
- Real OAuth flows for any connector
- Real API clients (Google API, YNAB API, Apple Health, Nike)
- Webhook receivers
- Background sync schedulers / queues
- Delta sync
- iCal feed parsing
- Hearth bridge
- Ingestion audit log
- Rate limiting / retry / credential rotation for external APIs

## 10. Testing / CI / Release Automation
Status: **VERIFIED**

Current surface:
- 20 backend test files, **349 tests passing** (local pytest run 2026-04-13
  on commit `4e8d2e9`; 58 of those are AI-layer tests)
- `backend/tests/` uses pytest + Postgres 16 + fresh schema per run
- `.github/workflows/ci.yml` jobs: `backend-tests`, `frontend-types`,
  `smoke-web` (full local Playwright)
- **28 Playwright tests** across 8 files: auth (5), surfaces (7),
  ai-panel (3), ai-roundtrip (2, conditional), write-paths (6),
  meals-subpages (3), dev-mode (1), error-boundary (1, gated on
  `EXPO_PUBLIC_SCOUT_E2E`)
- `scripts/release_check.py` — pytest + tsc + migrate + seed + smoke
- `scripts/wait_for_url.py` — readiness wait for deploy verification
- Persistent smoke credentials provisioned on Railway
  (`SCOUT_SMOKE_ADULT_EMAIL` / `SCOUT_SMOKE_ADULT_PASSWORD`) for operator
  and future CI smoke runs against the deployed URLs.

Gaps:
- No CI job runs Playwright against the deployed Vercel URL — operator
  checklist only. Tracked as Sprint 2 backlog item "deployed browser
  smoke in CI".
- No load testing. Acceptable at private launch scale.
- No backend chaos / fault injection suite.

## 11. Deployment
Status: **VERIFIED** (in production for private launch since 2026-04-12;
AI path verified end-to-end 2026-04-13)

Artifacts:
- `backend/Dockerfile` (Python 3.12 slim + `start.sh`) — context-relative
  `COPY requirements.txt` / `COPY . .` so Railway's `rootDirectory: backend`
  build works cleanly.
- `scout-ui/Dockerfile`, `docker-compose.yml`
- `backend/railway.json`, `scout-ui/vercel.json`, `scout-ui/railway.json`.
  Single `scout-backend` Railway service (the stale duplicate `Scout`
  service was removed 2026-04-13).
- `backend/seed.py` + `backend/seed_smoke.py` run post-migration.
  `seed_smoke.py` deterministically seeds a draft weekly meal plan,
  pending purchase request, chore template, and a `TaskInstance` for
  the current day so write-path smoke tests always find the right state.
- Production env: `SCOUT_ENVIRONMENT=production`, `SCOUT_AUTH_REQUIRED=true`,
  `SCOUT_ENABLE_BOOTSTRAP=false`, `SCOUT_ANTHROPIC_API_KEY` set,
  `SCOUT_SMOKE_ADULT_EMAIL` + `SCOUT_SMOKE_ADULT_PASSWORD` set.

Verification:
- Backend: `https://scout-backend-production-9991.up.railway.app` (healthy)
- Frontend: `https://scout-ui-gamma.vercel.app`
- 9/9 auth + surface deployed smoke tests passed (`c29a5d0`).
- **Production AI round-trip VERIFIED** on 2026-04-13 (`782c3ef`) using
  the new persistent `smoke@scout.app` account: login → chat → 200 with
  real conversation id, tool call, tokens, and matching production DB
  row deltas. Railway logs confirm `ai_chat_start` / `ai_chat_success`
  pairs with trace ids (including one pair from a real adult user).
- Family renamed Whitfield → Roberts in repo + prod Postgres in lockstep
  (`782c3ef`).

Gaps:
- Deployed browser smoke (Playwright against Vercel URL) is not wired
  into CI yet — backlog Sprint 2 item.
- Rate limiter and bootstrap state are process-local. See Deferred
  Ledger for multi-instance hardening.
- No blue/green or rolling-release strategy beyond Railway's default.

## Deferred Backend Debt Ledger

| Item | Why deferred | Launch impact | Next window |
|---|---|---|---|
| Real OAuth for Google Calendar / YNAB / Apple Health / Nike | No external customer demand at private launch; dev-mode ingestion is enough | None for single family | Later |
| Webhook receivers + background sync schedulers | Same as above; no live external data to react to | None | Later |
| iCal feed parsing | Connector CHECK supports `ical` but parsing not written | None | Later |
| Ingestion audit log | Basic service-level logging is sufficient for v1 | None | Next sprint if integrations ship |
| Multi-instance safe rate limiter | Single-instance backend on Railway | None today; risk if we horizontally scale | Before any horizontal scale-out |
| Bonus / penalty allowance adjustments | UI stubs exist; model change + endpoint needed | None — payout path works without it | Next sprint |
| Provider retry / fallback on Anthropic 5xx | Anthropic reliability acceptable today | User-visible error on single upstream hiccup | Sprint 2 |
| AI cost / latency dashboards + per-family token budget | Log-grep works at family scale | None today; rises with usage | Sprint 2 tail |
| Notification delivery for AI `send_notification_or_create_action` | Currently logged only; no delivery channel chosen | None — Action Inbox covers the need | Later |
| `dietary_preferences` → AI meal generation wiring | Table exists but generator ignores it | Low — AI still produces usable plans | Sprint 2 |
| Prompt caching for static system prompt | Per-turn rebuild fine at current volume | None | Sprint 2 tail |
| Scheduled daily brief / weekly plan delivery | On-demand works | Lower engagement | Sprint 2 |
| Dedicated `parent_action_items` route module | Dashboard aggregation covers current UX | None | When action inbox needs filtering |
| Moderation false-positive feedback loop | Classifier tuned conservatively | Low | Later |
