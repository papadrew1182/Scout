# Scout Roadmap Reconciliation

Last reconciled: 2026-04-13 against commit `4e8d2e9` on `main`.

This document is the single place that answers the question:
**"what is actually done, and what was just good-enough for private launch?"**

It exists because three roadmap docs (backend, frontend, AI) can each be
internally consistent while still disagreeing about what "done" means. This
doc forces the disagreement into the open.

Scope: Scout repo only. `main` at the start of this pass was `4e8d2e9`
(SSE streaming + conversation_kind + moderation alerts), which is ahead
of every milestone the earlier passes reference.

## How to read this

- **VERIFIED** — code + tests + real production evidence (prod
  round-trip, production DB rows, Railway log lines, or deployed
  browser smoke).
- **IMPLEMENTED** — code exists and tests pass, but production / browser
  deploy behavior has not been re-exercised in this pass.
- **PARTIAL** — only a subset of the intended surface exists.
- **DEFERRED** — intentionally postponed; reason captured.
- **BLOCKED** — real work that cannot move without an external action.
- **UNKNOWN** — not enough evidence.

## 1. What is truly VERIFIED today

These capabilities have code **and** evidence (passing tests, smoke,
or documented production verification):

- **Foundation / family model** — models, migrations, tenant isolation
  tests, no hardcoded `FAMILY_ID`, bootstrap disabled in production,
  family renamed Whitfield → Roberts across code + prod DB in `782c3ef`.
- **Auth / sessions / accounts** — 40 backend auth tests + 5 Playwright
  auth smoke + persistent `smoke@scout.app` account for ops verification.
- **Household ops** (routines, chores, daily wins, allowance, weekly
  payout) — backend tests + write-path smoke for the approve / run-payout
  flows.
- **Calendar + iCal connector support** — `test_calendar.py`,
  `test_connector_ical.py`; rendered in production smoke.
- **Personal tasks, notes, finance, health** — all four have models,
  services, routes, and unit tests.
- **Meals + AI weekly plan service** — 39 weekly-meal tests +
  `meals-subpages.spec.ts` (3 Playwright tests) + deterministic draft
  plan from `seed_smoke.py`.
- **Grocery, purchase requests, parent action items** — 26 `test_grocery`
  tests + write-path smoke coverage for approve / convert flows.
- **AI orchestration layer** — provider (sync + streaming), context
  loader with `allow_general_chat` / `allow_homework_help` flags,
  30-tool registry including `get_weather`, confirmation flow with
  structural surfacing, audit table, moderation layer, and
  `conversation_kind` tagging. **58 AI backend tests** (26 context +
  15 routes + 17 tools).
- **Production AI backend path** — direct HTTPS round-trip from
  `smoke@scout.app` returned 200 with a real conversation id, tool
  call, and 762-char response. One real adult-user pair captured in
  Railway logs. Production DB row deltas match the orchestrator's
  persistence model exactly.
- **SSE streaming** — `/api/ai/chat/stream` endpoint, orchestrator
  `chat_stream()` generator, frontend `sendChatMessageStream()`.
  Landed in `4e8d2e9`.
- **Moderation layer** — classifier-backed block path with `ai_tool_audit`
  row, parent `Action Inbox` alert, and `conversation_kind='moderation'`
  tagging.
- **ScoutPanel confirmation flow** — structural `pending_confirmation`
  surfacing + frontend confirm card + `confirm_tool` direct path +
  Playwright round-trip test.
- **ScoutPanel disabled state** — `fetchReady()` + `readyState` machine
  + Playwright stub test.
- **Global `ErrorBoundary`** — wraps `AuthProvider + AppShell` +
  Playwright verification via gated `/__boom` route.
- **Dashboard aggregation** — `test_dashboard.py` (11 tests).
- **CI + release check** — `.github/workflows/ci.yml`,
  `scripts/release_check.py`, `scripts/wait_for_url.py`, **349 backend
  tests + 28 Playwright smoke tests**.
- **Deployment** — Railway backend + Vercel frontend verified 2026-04-12
  for the auth + surfaces path; 2026-04-13 for the AI backend path;
  stale duplicate `Scout` Railway service removed; `backend/Dockerfile`
  paths made context-relative so Railway's `rootDirectory: backend`
  build works cleanly.

## 2. Implemented but not strongly verified

Code exists but end-to-end verification is thin:

- **Deployed browser smoke in CI.** The AI backend path is verified via
  direct HTTPS round-trip, but running the full Playwright suite
  against `scout-ui-gamma.vercel.app` from CI is not wired up. Operator
  checklist in `docs/AI_OPERATOR_VERIFICATION.md`.
- **Streaming rendering in the browser.** The panel uses SSE and the
  chunks flow through, but no Playwright test asserts per-chunk updates.
- **Weekly AI meal generation loop (UI).** Questions → answers →
  approve path is not driven by smoke (deliberate — slow).
- **Daily brief / weekly plan / staple meals endpoints through the UI.**
  Routes exist; no browser test hits them.
- **AI-settings toggle round-trip.** Adults can toggle `allow_general_chat`
  / `allow_homework_help` in Settings; backend prompt variants are
  tested, the UI round-trip is not.
- **Parent bonus / penalty payout UI.** Buttons visible, handlers are
  explicit stubs. Backend endpoint does not exist.

## 3. Launch-sufficient but not actually "done"

Items that passed the private-launch bar but should not be called
"done" outside of that context. Items **resolved** since the earlier
roadmap passes are marked inline with the commit that closed them.

- ~~**AI streaming**~~ — **RESOLVED in `4e8d2e9`.** SSE server + client +
  panel consumption.
- ~~**AI smoke coverage**~~ — **RESOLVED in Sprint 1 closeout / residual
  closeout.** 3 `ai-panel` tests + 2 `ai-roundtrip` tests.
- ~~**Production backend AI path**~~ — **RESOLVED 2026-04-13** via
  persistent `smoke@scout.app` + direct HTTPS round-trip + Railway
  log verification + prod DB row deltas.
- ~~**ScoutPanel confirmation flow UI**~~ — **RESOLVED in `5f11821`.**
- ~~**ScoutPanel disabled-state handling**~~ — **RESOLVED in `5f11821`.**
- ~~**Global frontend error boundary**~~ — **RESOLVED in `5f11821` +
  residual closeout** (Playwright verification via gated `/__boom`).
- ~~**Dev-mode ingestion buttons in prod builds**~~ — **RESOLVED in
  `5f11821`.** `DEV_MODE = !EXPO_PUBLIC_API_URL` is compile-time; any
  prod build hides the panel; `dev-mode.spec.ts` asserts it.
- ~~**Family name Whitfield in prod / seeds**~~ — **RESOLVED in `782c3ef`.**
  Renamed to Roberts across repo + prod Postgres in lockstep.
- **Deployed browser smoke in CI** — still launch-sufficient (direct
  HTTPS round-trip covers the backend path) but not strategically
  complete.
- **Provider fallback / retry on Anthropic 5xx** — single hiccup
  surfaces as a user-visible error banner.
- **Rate limiting** — in-memory, per-process. Correct for a single
  Railway instance; multi-instance would need redistribution.
- **Connector framework** — upsert helper + mapping table + Google /
  YNAB payload ingestion work, but no real OAuth, no live API client,
  no webhook, no scheduler. Dev-mode ingestion is the only trigger.
- **Bundle / Web Vitals / accessibility measurement** — unmeasured.
- **`dietary_preferences`** — table exists; weekly generator ignores it.
- **`send_notification_or_create_action` delivery** — tool logs + audits
  but no transport. Action Inbox covers the product need.
- **Scheduled daily brief / weekly plan** — on-demand only.
- **Prompt caching** — every turn rebuilds the static prefix.
- **Cost / latency / per-family observability** — logs only.
- **RexOS / Exxir placeholder panels** — copy only, product decision
  pending.

## 4. Deferred debt that still matters

The consolidated list of deferred work. Items resolved above are not
repeated here.

**Production / ops hardening**
- Deployed browser smoke in CI using the Railway-stored smoke
  credentials
- Multi-instance safe rate limiter (blocker only on horizontal scale)
- Provider fallback / retry for Anthropic 5xx
- Cost + latency dashboards for AI
- Per-family token / cost budget
- Load / chaos testing

**Frontend UX / polish**
- Streaming assertion depth in Playwright
- AI-settings toggle round-trip smoke
- Production error reporting (Sentry-equivalent) wired into
  `ErrorBoundary.componentDidCatch`
- Account create / password reset E2E through the adult settings screen
- Task-step completion E2E coverage (beyond current write-path tests)
- Accessibility audit
- Responsive / mobile-web verification beyond smoke
- RexOS / Exxir placeholder panel decision (build / remove / "coming soon")
- Bonus / penalty parent payout UX (backend endpoint pending)
- Conversation resume in ScoutPanel

**Schedule / document advanced features**
- iCal feed parsing (CHECK constraint already permits `ical`)
- Real OAuth + API clients for Google Calendar / YNAB / Apple Health /
  Nike
- Webhook receivers + background sync schedulers + delta sync
- Ingestion audit log

**Bonus / performance system**
- Bonus / penalty allowance adjustment endpoints + model
- Parent-applied reward overrides

**AI / intelligence**
- Scheduled morning brief delivery
- `dietary_preferences` → weekly plan generator wiring
- Prompt caching for static system prompt prefix
- `send_notification_or_create_action` real delivery channel
- Moderation false-positive feedback loop

**Long-range platform**
- Second AI provider
- Cross-family analytics
- Offline / service worker story
- Fine-tuned or cached models

## 5. "Done" claims that were previously wrong and are now corrected

- **"AI layer is request/response only — streaming is UX debt."** No
  longer true. SSE streaming shipped in `4e8d2e9`; the panel uses
  `sendChatMessageStream()`. The non-streaming path survives as a
  fallback for the `confirm_tool` resubmit flow.
- **"17 tools in the registry."** Was already corrected to 29; the real
  number as of `4e8d2e9` is **30** (added `get_weather`).
- **"AI panel is verified through tests: 10 context / 5 routes / 14
  tools = 29 AI tests."** Now **26 / 15 / 17 = 58** after Sprint 1
  closeout + Sprint 2 feature work.
- **"Backend test count is 320."** Now **349** local pytest run on
  `4e8d2e9`.
- **"Confirmation flow UI does not exist."** Now exists — backend
  structural surfacing + frontend confirm card + `confirm_tool` direct
  path + Playwright round-trip.
- **"Disabled-state handling does not exist."** Now exists —
  `fetchReady()` + `readyState` machine + Playwright stub test.
- **"Global error boundary does not exist."** Now exists + verified via
  gated `/__boom` Playwright path.
- **"Deployed AI backend verification is BLOCKED on operator access."**
  Now VERIFIED — direct HTTPS round-trip from `smoke@scout.app` +
  Railway log evidence + prod DB row deltas on 2026-04-13.
- **"Whitfield family name hardcoded in seeds."** Renamed to Roberts
  across repo + prod DB in `782c3ef`.
- **"No moderation layer."** Now exists — classifier-backed block path
  with parent Action Inbox alerts and `conversation_kind='moderation'`
  tagging.
- **"Homework help / broad chat are not tracked."** Now tracked via
  family-level `allow_general_chat` + `allow_homework_help` flags with
  adult Settings toggles and all four child-prompt variants tested.

## 6. Direct answers

**Is the AI platform implemented?** Yes — provider (sync + streaming),
orchestrator, context loader, 30 tools, confirmation flow, audit table,
conversation persistence with kind tagging, moderation layer, handoff
cards, daily brief, weekly plan, and family-level AI flags all exist
in code with 58 backend AI tests.

**Is the AI panel verified through the real browser UI?** **Locally
yes** (5 Playwright tests covering content, disabled-state, child
surface, tool round-trip, confirmation round-trip, plus the
ErrorBoundary test gated on the E2E flag). **Deployed-URL CI smoke:
not yet.** **Production backend**: VERIFIED via direct HTTPS
round-trip + real user pair in Railway logs on 2026-04-13.

**Is the AI request/response or streaming?** Both. `/api/ai/chat` is
request/response; `/api/ai/chat/stream` is SSE. The panel uses
streaming by default and falls back to non-streaming if the stream
errors before producing text.

**What was "done for private launch" vs "done strategically"?** The
product is launch-ready end-to-end at family scale *and* the
production AI backend path has been verified end-to-end. The
remaining "launch-sufficient but not strategically complete" work is
captured in §3 above — the biggest single item is running the full
Playwright suite against the deployed URLs from CI.

## 7. Top 10 deferred items across the product

1. Deployed browser smoke in CI (against `scout-ui-gamma.vercel.app`)
2. Provider retry / fallback for Anthropic 5xx
3. Production error reporting wired into `ErrorBoundary`
4. AI cost / latency / per-family observability
5. Scheduled daily brief / weekly plan delivery
6. `dietary_preferences` → weekly meal plan generator wiring
7. Streaming assertion depth in Playwright
8. AI-settings toggle smoke + settings audit log
9. Bonus / penalty parent payout endpoint + UI wiring
10. Real integrations layer (OAuth + API clients + webhooks +
    schedulers for Google Calendar / YNAB / Apple Health / Nike)

## 8. Five places where we may have over-called something "done"

1. **Deployed AI verification.** Was BLOCKED, now VERIFIED at the
   backend path level, but the full Playwright-against-Vercel run is
   still operator-only. "Deployed AI path is verified" is true for the
   backend and not yet for the browser bundle in CI.
2. **Integrations.** Still PARTIAL. Google Calendar / YNAB ingestion
   works only from dev-mode buttons with pre-built payloads. No real
   external integration has ever hit production.
3. **Parent Rewards / Allowance.** Payout works and is VERIFIED;
   bonus/penalty is the specific missing piece. The overall label is
   now more precise.
4. **Daily brief / weekly plan.** Routes exist and backend tests pass,
   but nobody sees the output without tapping a button — calling
   "daily brief" DONE overstates engagement value.
5. **Notification delivery via AI tools.**
   `send_notification_or_create_action` is in the tool registry and
   passes its audit; it logs and returns without delivering.

## 9. Five strongest pieces of evidence Scout is ready for private use

1. **349 backend tests passing** on local pytest against `4e8d2e9`
   (58 of those are AI-layer tests).
2. **Production AI round-trip verified** 2026-04-13 via
   `smoke@scout.app` — login + chat + conversation id + tool call +
   production DB row deltas + Railway log pair (plus one real-user
   pair from Andrew).
3. **Production env locked down**: `SCOUT_ENVIRONMENT=production`,
   `SCOUT_AUTH_REQUIRED=true`, `SCOUT_ENABLE_BOOTSTRAP=false`, stale
   duplicate Railway service removed, `backend/Dockerfile` fixed for
   Railway's `rootDirectory: backend` build context.
4. **No hardcoded `FAMILY_ID`** anywhere; tenant isolation covered by
   `test_tenant_isolation.py`; family context comes from `/api/auth/me`.
5. **End-to-end role gating verified by smoke**: adults see "Accounts &
   Access", children do not; bad-password, invalid-token recovery;
   child denial paths covered by `test_ai_context.py` variants.

## 10. Sync check

- Local `main` at start of this pass: `4e8d2e9`
- `origin/main`: `4e8d2e9`
- Pull result: already up to date.
- Working tree at start of this pass: clean (after Phase A).
- Backend pytest against this commit: **349 passed** in ~53s.

## 11. Operating mode now

Scout is **live for private family use**. The production backend AI
path has been verified end-to-end. All Sprint 1 closeout + Sprint 2
feature work (streaming, moderation, broad chat, homework help,
weather, AI settings) has landed on `main`.

**From this point forward, prompts should be bugfix-only or
tightly-scoped backlog items.** No more broad "build everything"
prompts. The remaining work in `docs/EXECUTION_BACKLOG.md` is
trust / polish / strategic-completion work (deployed browser smoke in
CI, provider retry, observability dashboards, production error
reporting, `dietary_preferences` wiring, scheduled brief delivery,
prompt caching, etc.) — not launch survival.

Concretely, the allowed prompt shapes from now on:
- "Fix bug X in Y" with a specific repro or failing test.
- "Pick off backlog item Z and ship it end-to-end" where Z is named in
  `docs/EXECUTION_BACKLOG.md`.
- "Add a smoke test for W" where W is a named, existing surface.
- Operational and dependency maintenance (upgrades, security patches,
  deploy hygiene).

Prompts that should be pushed back on:
- "Build feature A" where A is not already in the backlog.
- "Refactor module B" without a concrete bug or test to anchor the
  change.
- "Add a new roadmap / planning doc" unless an existing one is wrong.
- Any request to "reconcile" or "resync" roadmaps again without new
  code landing first — the current docs are as fresh as they can be
  given the commit history.

This section supersedes the "Recommended next sequence" tails in the
individual roadmap files if they conflict.
