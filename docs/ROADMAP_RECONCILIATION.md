# Scout Roadmap Reconciliation

Last reconciled: 2026-04-12 against commit `9481f8f` on `main`.

This document is the single place that answers the question:
**"what is actually done, and what was just good-enough for private launch?"**

It exists because three roadmap docs (backend, frontend, AI) can each be
internally consistent while still disagreeing about what "done" means. This
doc forces the disagreement into the open.

Scope: Scout repo only. Local `main` was already in sync with `origin/main`
at the time of this pass — no pull was needed.

## How to read this

- **VERIFIED** — present in code AND exercised by passing tests, deployed
  smoke, or documented deploy verification.
- **IMPLEMENTED** — present in code but not strongly verified end-to-end.
- **PARTIAL** — only part of the intended surface exists.
- **DEFERRED** — intentionally postponed; reason captured.
- **UNKNOWN** — not enough proof in this reconciliation pass.

## 1. What is truly VERIFIED today

These capabilities have code **and** evidence (passing tests, smoke runs, or
documented deploy verification):

- **Foundation / family model** — models, migrations, tenant isolation tests,
  no hardcoded `FAMILY_ID`, bootstrap disabled in production.
- **Auth / sessions / accounts** — 40 backend tests in `test_auth.py`, Playwright
  auth smoke (5 tests), fail-closed `SCOUT_AUTH_REQUIRED=true` in production.
- **Household ops** (routines, chores, daily wins, allowance, weekly payout) —
  `test_daily_wins.py` (11), `test_payout.py` (13), surfaced on parent + child
  smoke paths.
- **Calendar + iCal connector support** — `test_calendar.py`,
  `test_connector_ical.py`; rendered in production smoke.
- **Personal tasks, notes, finance, health** — all four have models, services,
  routes, and unit tests.
- **Meals + AI weekly plan service** — 15 + 39 + 39 tests across
  `test_meals.py`, `test_meals_routes.py`, `test_weekly_meal_plans.py`.
- **Grocery, purchase requests, parent action items** — `test_grocery.py` (26)
  plus parent dashboard rendering in smoke.
- **AI orchestration layer** — provider, context, tool registry, confirmation,
  audit; `test_ai_context.py` (13), `test_ai_routes.py` (8), `test_ai_tools.py`
  (18).
- **Dashboard aggregation** — `test_dashboard.py` (11).
- **CI + release check** — `.github/workflows/ci.yml`, `scripts/release_check.py`,
  `scripts/wait_for_url.py`, 320 backend tests + 12 Playwright smoke tests.
- **Deployment** — Railway backend + Vercel frontend, verified 2026-04-12 by
  `docs/release_candidate_report.md` and deployment commit `c29a5d0` (9/9
  deployed smoke pass).

## 2. Implemented but not strongly verified

Code exists but smoke / E2E coverage is thin or absent:

- **Meals UX — `prep.tsx`, `reviews.tsx`** — files exist but were not
  re-audited in this pass. Status: **UNKNOWN** until audited.
- **AI panel depth** — the `ai-panel.spec.ts` smoke test covers entry point +
  happy-path error handling only. It does NOT test tool execution,
  confirmation, conversation history, or per-surface behavior.
- **Write-path E2E on the frontend** — no Playwright coverage for task
  completion, meal plan approval, or grocery approval as full user flows.
  Backend has unit coverage; the UI write path is trusted by extension.
- **Weekly AI meal generation loop (UI)** — the questions → answers → approve
  path in `meals/this-week.tsx` is not smoked.
- **Parent bonus / penalty payout UI** — buttons visible, handlers "not
  implemented yet". Matches the backend gap.
- **`parent_action_items` dedicated routes** — models exist, but the only
  surface is dashboard aggregation. No route module.

## 3. Launch-sufficient but not actually "done"

These items passed the private-launch bar but should not be called "done"
outside of that context:

- **AI streaming** — we shipped request/response. That is launch-sufficient,
  not "AI chat done".
- **AI smoke coverage** — one test file covers AI. Launch-sufficient, not
  "AI verified".
- **AI notification delivery** — the tool logs but does not deliver. The
  Action Inbox covers the product need; the tool itself is a stub.
- **Rate limiting** — in-memory, per-process. Correct for a single Railway
  instance; a multi-instance deployment would need redistribution.
- **Connector framework** — the upsert helper, mapping table, and Google /
  YNAB payload ingestion work, but there is no real OAuth, no live API
  client, no webhook, no scheduler. Dev-mode ingestion is the only trigger.
- **Global frontend error boundary** — does not exist. Component-level
  handling was enough for launch; a worst-case render crash has no fallback.
- **Bundle / Web Vitals / accessibility measurement** — unmeasured.
- **`dietary_preferences`** — table exists but the weekly meal plan generator
  ignores it.
- **RexOS / Exxir placeholder panels** on the personal surface — copy only,
  no wiring. Not exposed as a feature but present in code.
- **Dev-mode ingestion buttons in production builds** — gated by a flag that
  has not been audited for prod behavior.

## 4. Deferred debt that still matters

The consolidated list of deferred work — the same items carried at the
bottom of each roadmap, surfaced once here for auditing.

**Production / ops hardening**
- Multi-instance safe rate limiter (blocker only if we horizontally scale)
- Provider fallback / retry for Anthropic 5xx
- Cost + latency dashboards for AI
- Load / chaos testing

**Frontend UX / polish**
- Write-path E2E smoke (tasks, meals, grocery)
- Global error boundary / fallback screen
- Multi-member session switching
- Task-step completion E2E coverage
- Accessibility audit
- Responsive / mobile-web verification beyond smoke
- Audit + smoke for `meals/prep.tsx` and `meals/reviews.tsx`
- Decide production behavior for dev-mode ingestion buttons
- RexOS / Exxir placeholder panel decision (build / remove / "coming soon")
- Bonus / penalty parent payout UX

**Schedule / document advanced features**
- iCal feed parsing (CHECK constraint already permits `ical`)
- Real OAuth + API clients for Google Calendar / YNAB / Apple Health / Nike
- Webhook receivers + background sync schedulers + delta sync
- Ingestion audit log

**Bonus / performance system**
- Bonus / penalty allowance adjustment endpoints + model
- Parent-applied reward overrides

**AI / intelligence**
- Streaming responses (biggest perceived-latency win)
- AI smoke depth (tools, confirmation, history, surfaces)
- Dietary preferences → weekly plan generator wiring
- Scheduled morning brief delivery
- Confirmation flow UI inside ScoutPanel
- Conversation resume in UI
- Prompt caching for static system prompt sections
- `send_notification_or_create_action` real delivery channel

**Long-range platform**
- Second AI provider
- Cross-family analytics
- Offline / service worker story
- Fine-tuned or cached models

## 5. Stale / contradictory docs found

- `BACKEND_ROADMAP.md` stopped at section 10 (Intelligence Layer) and made no
  mention of migrations `011_grocery_purchase_requests.sql`,
  `012_parent_action_items.sql`, or `013_meals_weekly_plans.sql`. Fixed in this
  pass — new sections added for Grocery / Purchase Requests / Parent Action
  Items, Dashboard Aggregation, Testing / CI, and Deployment.
- `BACKEND_ROADMAP.md` marked "Parent Rewards / Allowance Management" as
  PARTIAL with "backend refinements if needed" as the missing piece. The
  payout path is actually VERIFIED; the gap is specifically bonus/penalty
  adjustments. Refreshed with the precise gap.
- There was no `FRONTEND_ROADMAP.md`. Frontend was never mapped to a roadmap.
  Created in this pass.
- There was no `AI_ROADMAP.md`. AI was tracked only as §10 inside the backend
  roadmap. Created in this pass.
- Old status labels (`DONE`, `NEXT`, `PLANNED`, `BLOCKED`) did not distinguish
  between "we ran the tests" and "we wrote the code". Replaced with
  VERIFIED / IMPLEMENTED / PARTIAL / DEFERRED / UNKNOWN.

## 6. Direct answers

- **Was backend "done" against a roadmap?** Yes, but the roadmap was stale by
  ~3 migrations. Every section in the old doc is still correct where it
  appears; the doc just stopped tracking once grocery / purchase requests /
  weekly meal plans landed. Refreshed.
- **Was frontend ever mapped against a roadmap?** No. The frontend was
  exercised by smoke tests and a deployment checklist, not a planning
  document. `FRONTEND_ROADMAP.md` is the first one.
- **Was AI ever mapped against a roadmap?** Only as a single backend section.
  `AI_ROADMAP.md` is the first one that treats AI as a cross-stack concern
  (provider, orchestration, tools, UX, smoke, deployment, debt).
- **What was "done for private launch" vs "done strategically"?** See
  sections 1 and 3 above. The short version: the product is launch-ready
  end-to-end at family scale, but AI smoke coverage, write-path E2E coverage,
  streaming, bonus/penalty, and multi-instance ops are explicitly
  launch-sufficient, not strategically complete.

## 7. Top 10 deferred items across the product

1. AI streaming responses
2. AI panel smoke depth (tool execution, confirmation, history)
3. Frontend write-path E2E smoke (task / meal / grocery approval flows)
4. Global frontend error boundary
5. Bonus / penalty parent payout endpoint + UI wiring
6. Real OAuth + API clients for Google Calendar, YNAB, Apple Health, Nike
7. `dietary_preferences` → weekly meal plan generator wiring
8. Confirmation flow UI inside ScoutPanel
9. Multi-instance safe rate limiter + distributed bootstrap state
10. Audit + smoke for `meals/prep.tsx` and `meals/reviews.tsx`
     (currently UNKNOWN)

## 8. Five places where we may have over-called something "done"

1. **AI layer** — was listed as a single DONE section in `BACKEND_ROADMAP.md`.
   Reality: the backend orchestration is solid, but the UX, smoke, streaming,
   and delivery channels are all partial.
2. **Meals** — was DONE in the backend roadmap. Reality: AI generation is the
   primary user path and is not smoked; `dietary_preferences` is ignored by
   the generator; two subpages (prep / reviews) are UNKNOWN.
3. **Parent Rewards / Allowance** — was PARTIAL with vague wording. Reality:
   payout works; bonus/penalty is the specific missing piece. The label was
   underselling one axis and overselling another.
4. **Integrations** — was PARTIAL. Reality: Google Calendar and YNAB ingestion
   work only from dev-mode buttons with pre-built payloads. No real external
   integration has ever hit production.
5. **Notification delivery via AI tools** — `send_notification_or_create_action`
   is in the tool registry and passes its audit. Reality: it logs and returns;
   there is no delivery channel. Action Inbox covers the product need but not
   the tool's name.

## 9. Five strongest pieces of evidence Scout is actually ready for private use

1. **320 backend tests passing** on CI plus locally (`docs/release_candidate_report.md`).
2. **9/9 deployed smoke tests passing** post-deploy on commit `c29a5d0`
   against real Railway + Vercel URLs.
3. **Production env locked down**: `SCOUT_ENVIRONMENT=production`,
   `SCOUT_AUTH_REQUIRED=true`, `SCOUT_ENABLE_BOOTSTRAP=false`,
   fail-closed on missing AI key, bootstrap disabled once accounts exist.
4. **No hardcoded `FAMILY_ID`** anywhere; tenant isolation covered by
   `test_tenant_isolation.py`; family context comes from `/api/auth/me`.
5. **End-to-end role gating verified by smoke**: adults see "Accounts &
   Access", children do not; bad-password error rendered; invalid-token
   recovery clears storage and returns to login. Auth + surface smoke is
   genuinely exercising production-mode code paths.

## 10. Sync check

- Local `main` at start of this pass: `9481f8f`
- `origin/main`: `9481f8f`
- Pull result: already up to date; no changes.
- Working tree: clean at start of this pass.
