# Scout Backend Roadmap

Last reconciled: 2026-04-12 against commit `9481f8f` on `main`.

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
Status: **VERIFIED** (updated 2026-04-13; see `AI_ROADMAP.md` for depth)

Scope at the backend layer:
- Anthropic provider abstraction
- Role-aware context loader
- 29 tool registry wrapping existing services (was previously mis-stated as 17)
- Role × surface permission enforcement
- Confirmation-gated shared writes (10 tools in `CONFIRMATION_REQUIRED`)
- Bounded 5-round tool-execution loop
- Full audit logging per tool call
- **(Sprint 1 closeout, 2026-04-13)** Structural surfacing of
  `pending_confirmation` and `handoff` in `ChatResponse`, plus a new
  `confirm_tool` direct-execution path in `ChatRequest` that bypasses
  the LLM round. This backs the ScoutPanel confirm-card affordance.

Evidence:
- `backend/app/ai/provider.py`, `context.py`, `tools.py` (994 lines),
  `orchestrator.py` (extended with `_detect_handoff`, `_build_chat_result`,
  and a `confirm_tool` direct path)
- `backend/app/routes/ai.py` — 7 endpoints including chat, daily brief, weekly plan
- `backend/app/schemas/ai.py` — `ConfirmToolPayload`, `HandoffPayload`,
  `PendingConfirmation`, extended `ChatRequest`/`ChatResponse`
- Migration: `010_ai_orchestration.sql`
- Tests: `test_ai_context.py` (10), `test_ai_routes.py` (now 8 including
  `TestPendingConfirmationPlumbing` — scripted-provider pending test and
  zero-provider-call confirm_tool test), `test_ai_tools.py` (14)

Gaps:
- Provider is **request/response only** — no streaming. Captured in AI Roadmap.
- `send_notification_or_create_action` tool logs but does not deliver.
- No background job, no autonomous loop.

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
- 20 backend test files, ~320 tests passing (per `docs/release_candidate_report.md`)
- `backend/tests/` uses pytest + Postgres 16 + fresh schema per run
- `.github/workflows/ci.yml` jobs: `backend-tests`, `frontend-types`, `smoke-web`
- 12 Playwright smoke tests in `smoke-tests/` (auth + core surfaces + AI panel)
- `scripts/release_check.py` — pytest + tsc + migrate + seed + smoke
- `scripts/wait_for_url.py` — readiness wait for deploy verification

Gaps:
- No load testing. Acceptable at private launch scale.
- No backend chaos / fault injection suite.
- Smoke coverage for AI is thin — see AI Roadmap §9.

## 11. Deployment
Status: **VERIFIED** (in production for private launch as of 2026-04-12)

Artifacts:
- `backend/Dockerfile` (Python 3.12 slim + `start.sh`)
- `scout-ui/Dockerfile`, `docker-compose.yml`
- `backend/railway.json`, `scout-ui/vercel.json`, `scout-ui/railway.json`
- `backend/seed.py` run post-migration for family bootstrap
- Production env: `SCOUT_ENVIRONMENT=production`, `SCOUT_AUTH_REQUIRED=true`,
  `SCOUT_ENABLE_BOOTSTRAP=false`, `SCOUT_ANTHROPIC_API_KEY` set

Verification:
- Backend: `https://scout-backend-production-9991.up.railway.app` (healthy)
- Frontend: `https://scout-ui-gamma.vercel.app`
- 9/9 deployed smoke tests passed (commit `c29a5d0`)

Gaps:
- Rate limiter and bootstrap state are process-local. See Deferred Ledger
  for multi-instance hardening.
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
| Streaming AI responses | Request/response works; streaming is UX debt | Perceived latency on long replies | See AI Roadmap |
| Notification delivery for AI `send_notification_or_create_action` | Currently logged only; no delivery channel chosen | None — Action Inbox covers the need | Later |
| `dietary_preferences` → AI meal generation wiring | Table exists but generator ignores it | Low — AI still produces usable plans | Next sprint |
| Dedicated `parent_action_items` route module | Dashboard aggregation covers current UX | None | When action inbox needs filtering |
