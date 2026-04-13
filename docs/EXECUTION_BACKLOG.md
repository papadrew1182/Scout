# Scout Execution Backlog

Last reconciled: 2026-04-13 against commit `4e8d2e9` on `main`, after
Sprint 2 feature work (broad chat + homework + moderation + weather +
AI settings + SSE streaming + `conversation_kind`).

**Sprint 1 + Sprint 2 feature work is complete.** Scout is live for
private family use; the production AI backend path has been verified
end-to-end. Backlog below is now the **strategic completion + polish
list** for bugfix-only / tightly-scoped execution mode. See
`docs/ROADMAP_RECONCILIATION.md` §11 ("Operating mode now") for the
new execution constraints.

**Closed-in-this-pass items** (do not re-open unless a regression is
discovered):

- ~~1.1 Deployed AI-panel smoke (first-ever)~~ — **VERIFIED** at the
  backend path level via `smoke@scout.app` HTTPS round-trip + Railway
  log evidence + prod DB row deltas on 2026-04-13 (`782c3ef`).
  Residual: deployed **browser** run in CI against Vercel — see new
  item `Sprint 2 — deployed browser smoke in CI` below.
- ~~1.2 ScoutPanel disabled-state handling~~ — VERIFIED in Sprint 1
  closeout `5f11821`.
- ~~1.3 Dev-mode ingestion button prod audit~~ — VERIFIED in Sprint 1
  closeout `5f11821`.
- ~~2.1 Write-path E2E smoke suite~~ — VERIFIED in Sprint 1 residual
  closeout (6 tests, no annotated skips).
- ~~2.2 AI panel verification depth~~ — **VERIFIED locally** (3
  `ai-panel` tests + 2 `ai-roundtrip` tests); the deployed-URL CI run
  is the residual, tracked as a new Sprint 2 item.
- ~~2.3 Confirmation-flow UI inside ScoutPanel~~ — VERIFIED (backend
  structural surfacing + frontend card + `confirm_tool` direct path +
  pytest + Playwright round-trip test).
- ~~2.4 Global frontend error boundary~~ — VERIFIED (gated `/__boom`
  route + `error-boundary.spec.ts`).
- ~~2.5 Meals subpages smoke~~ — VERIFIED (3 tests).
- ~~3.1 AI streaming response pipeline~~ — VERIFIED. SSE shipped in
  `4e8d2e9`; orchestrator has `chat_stream()`, routes expose
  `/api/ai/chat/stream`, frontend uses `sendChatMessageStream()`.
- ~~17/18/19 Investigation items~~ — VERIFIED. Direct HTTPS round-trip
  + Railway log tail + prod Postgres row-count query all completed on
  2026-04-13.

This is a cross-product execution backlog. It is **not** a changelog and
it is **not** a wish list. Every item here is already captured as a
deferred / partial / unknown entry in one of the roadmaps; this document
merges duplicates, ranks, and sizes them.

**Status labels are preserved verbatim** from the source roadmaps:
VERIFIED / IMPLEMENTED / PARTIAL / DEFERRED / UNKNOWN.

## How to read this

Each item has:
- **Area**: backend / frontend / ai / ops
- **Current status** (from source roadmap, unchanged)
- **Why it matters**
- **Launch impact**: high / medium / low
- **Verification gap**: what a passing acceptance test would prove
- **Scope**: S (< 1 day) / M (1–3 days) / L (4+ days)
- **Owner type**: backend / frontend / full-stack / ops

## Deduplication notes

Items that appeared in multiple roadmaps have been merged here. Wherever
a single problem (e.g. "the AI panel is under-verified") was restated
with different wording (thin smoke / no tool round-trip / no deployed
run / no handoff test), it is **one backlog item** with multiple
acceptance criteria.

Merged item groups:
- **AI panel verification depth** — merges: thin smoke assertions, no
  tool round-trip, no deployed run against Railway+Vercel, no handoff
  deep-link test, no child/parent surface coverage.
- **Write-path E2E smoke** — merges: task complete, grocery approve,
  weekly payout, meal-plan approve, meal review submit, purchase-request
  convert.
- **Confirmation flow UX** — single item (panel affordance + surfaced on
  the shared-write tools that already return `confirmation_required`).
- **AI streaming pipeline** — single item including SSE server + client
  incremental render + typing indicator.
- **Meals subpages smoke** — merges: `prep.tsx` + `reviews.tsx` + weekly
  generation loop smoke.
- **Integrations realism** — merges: real OAuth, real API clients,
  webhook receivers, delta sync, ingestion audit log.
- **Production error reporting** — merges: frontend error boundary +
  Sentry-equivalent provider + cost/latency dashboards.

---

## Bucket 1 — Must-fix for private-launch stability

**Bucket 1 is empty.** All launch-stability items have landed. Scout is
in operating mode now — see `docs/ROADMAP_RECONCILIATION.md` §11.

Archived item (retained for historical context only):

### 1.1 — ~~Deployed AI-panel smoke (first-ever against Railway + Vercel)~~
**VERIFIED 2026-04-13 (`782c3ef`).** Direct HTTPS round-trip from
`smoke@scout.app` returned 200 with a real conversation id, tool call,
and 762-char response. Railway logs show matched `ai_chat_start` /
`ai_chat_success` pairs (one of them from a real adult user, Andrew,
before the smoke run). Production DB row deltas: `ai_tool_audit=+1`,
`ai_conversations=+1`, `ai_messages=+4`, matching the orchestrator's
persistence model exactly. See `docs/AI_OPERATOR_VERIFICATION.md`
"Initial verification result (2026-04-13)". The residual CI wiring for
running the full Playwright suite against Vercel has moved to the new
Sprint 2 item **"Deployed browser smoke in CI"** below.

- **Area:** ai / ops
- **Status:** VERIFIED (2026-04-13)
- **Resolution:** see note above.

### 1.2 — ScoutPanel disabled-state handling
**Sprint 1 status: IMPLEMENTED.** `scout-ui/lib/api.ts :: fetchReady()` +
`scout-ui/components/ScoutLauncher.tsx` probe `/ready` on open and render
a "Scout AI is unavailable right now" card when `ai_available=false`.
Covered by new Playwright test in `ai-panel.spec.ts` that stubs `/ready`
via `page.route()`.

- **Area:** frontend
- **Status:** PARTIAL (AI Roadmap §5, item 11 of ledger)
- **Why it matters:** `ScoutPanel` does not probe `/ready.ai_available`
  before opening. If the Anthropic key is ever removed, users will hit a
  live 5xx on their first quick-action click.
- **Launch impact:** medium (production currently has the key; one
  config mistake away from a user-visible break)
- **Verification gap:** no test forces `ai_available: false` at UI level.
- **Scope:** S
- **Owner:** frontend
- **Acceptance:**
  1. `ScoutPanel.open()` reads `/ready` and renders a "Scout AI is
     currently unavailable" state instead of mounting the chat UI when
     `ai_available === false`.
  2. Playwright test stubs `/ready` to return `ai_available: false` and
     asserts the disabled state.

### 1.3 — Decide production behavior for dev-mode ingestion buttons
**Sprint 1 status: VERIFIED.** Audited `scout-ui/lib/config.ts`:
`DEV_MODE = !process.env.EXPO_PUBLIC_API_URL`, evaluated at compile time
via Metro inlining. Any CI or Vercel build sets `EXPO_PUBLIC_API_URL`,
so `DEV_MODE=false`, so `{DEV_MODE && <DevToolsPanel />}` on the personal
surface short-circuits and the ingestion buttons are not rendered. New
`smoke-tests/tests/dev-mode.spec.ts` asserts the buttons are absent on
the personal dashboard.

- **Area:** frontend
- **Status:** IMPLEMENTED — gate not audited (Frontend Roadmap §3)
- **Why it matters:** personal dashboard renders Google Calendar + YNAB
  ingestion buttons behind a `DEV_MODE` flag that has never been
  validated against the production Vercel build.
- **Launch impact:** low — only visible if the flag leaks; but users
  clicking one would fire a real ingestion request with demo payloads.
- **Verification gap:** no test asserts the buttons are hidden in prod.
- **Scope:** S
- **Owner:** frontend
- **Acceptance:**
  1. Confirm current production behavior (visible or hidden).
  2. If visible, hide by default in prod builds.
  3. Playwright smoke asserts the buttons are not rendered when
     `process.env.EXPO_PUBLIC_DEV_MODE !== "true"`.

---

## Bucket 2 — Next sprint (highest-value verification + UX dead-ends)

Should follow a launch-stabilization sprint (Bucket 1) immediately.

### 2.1 — Write-path E2E smoke suite
**Sprint 1 residual closeout status: VERIFIED.** `write-paths.spec.ts`
ships 6 write-path tests: approve pending grocery, approve draft meal
plan, run weekly payout, convert purchase request, child task
completion, child meal-review submit. The residual closeout removed
the last annotated skip — `seed_smoke.py` now seeds the current-week
plan in `status='draft'` and normalizes any previously-approved row
back to draft on re-run, so the Approve button is deterministically
visible.

- **Area:** frontend / full-stack
- **Status:** PARTIAL (Frontend Roadmap §12; Reconciliation §2)
- **Why it matters:** every main surface is read-path only in smoke.
  Task completion, weekly payout, grocery approve, purchase-request
  convert, meal-plan approve, and meal-review submit are all blind
  spots. Backend tests cover the service layer but UI wiring is
  untested.
- **Launch impact:** medium (backend is covered; UI wiring regressions
  would escape CI)
- **Verification gap:** at least one E2E per write path.
- **Scope:** M
- **Owner:** full-stack
- **Acceptance:** six new Playwright tests, all runnable via
  `npm --prefix smoke-tests run test`:
  1. Child completes a task with step-tracking.
  2. Parent approves a pending grocery item.
  3. Parent runs weekly payout and sees an earned-amount update.
  4. Parent approves a weekly meal plan.
  5. Child submits a meal review (rating + repeat/tweak/retire).
  6. Parent converts a purchase request into a grocery item.

### 2.2 — AI panel verification depth
**Sprint 1 residual closeout status: IMPLEMENTED.** Content assertion +
disabled-state + child-surface test landed in Sprint 1 closeout.
Residual closeout adds `ai-roundtrip.spec.ts` with (a) an
`add_grocery_item` quick-action round-trip that taps the handoff card
and asserts navigation into `/grocery` when Claude returns a handoff,
and (b) a `create_event` confirmation round-trip that asserts the
confirm card renders when `pending_confirmation` is set, taps Confirm,
and asserts the follow-up response has `model === 'confirmation-direct'`.
Both tests skip cleanly when `ai_available=false`. Remaining gap:
deployed-URL run against Railway + Vercel — BLOCKED on operator
access, see `docs/AI_OPERATOR_VERIFICATION.md`.

- **Area:** ai / frontend
- **Status:** PARTIAL (AI Roadmap §10; Frontend Roadmap §10)
- **Why it matters:** the single AI-panel smoke test asserts only
  "no 5xx and no error banner." It never verifies a tool was called,
  a handoff card rendered, or a confirmation prompt surfaced.
- **Launch impact:** medium
- **Verification gap:** content assertions + tool round-trip + role
  variant + handoff deep-link + confirmation.
- **Scope:** M
- **Owner:** full-stack
- **Acceptance:**
  1. Strengthen existing test: assert the assistant bubble contains
     non-empty text.
  2. New test: "Ask Scout to add a task" → verify `personal_task`
     handoff card renders → tap → assert the new task appears on
     `/personal`.
  3. New test: child login → attempt a write quick-action →
     assert a denial response (not a crash).
  4. New test: parent-surface login → open ScoutPanel → assert quick
     actions render (parent variant is otherwise untested).
  5. New test: trigger a confirmation-required tool → assert the panel
     surfaces a confirm affordance (depends on 2.3 landing).

### 2.3 — Confirmation-flow UI inside ScoutPanel
**Sprint 1 status: IMPLEMENTED.** Backend: `orchestrator.chat()` now
detects `confirmation_required` in a tool result, breaks the loop, and
returns a structured `pending_confirmation={tool_name, arguments, message}`
in `ChatResponse`. Schema gained `ConfirmToolPayload`, `PendingConfirmation`.
New `confirm_tool` direct path on `ChatRequest` bypasses the LLM and
re-executes the tool with `confirmed=true`. Frontend: `ScoutLauncher.tsx`
renders a confirm/cancel card when `result.pending_confirmation` is set;
tapping Confirm calls `sendChatMessage("", {confirmTool})`. Covered by
two new pytest classes in `test_ai_routes.py`. **Remaining:** browser
Playwright round-trip of the confirm tap (open bug: still in backlog).

- **Area:** frontend
- **Status:** PARTIAL (AI Roadmap §5 and §3; Frontend Roadmap §10)
- **Why it matters:** the backend confirmation gate on the 10
  shared-write tools cannot currently be completed through the
  ScoutPanel. Users hit the `confirmation_required: true` response,
  which the panel does not render, and have to re-ask in plain English.
  Shared-write tools are effectively dead-ended.
- **Launch impact:** medium
- **Verification gap:** no UI affordance; no test exercises it.
- **Scope:** M
- **Owner:** frontend
- **Acceptance:**
  1. ScoutPanel recognizes `result.confirmation_required` and renders a
     confirm + cancel affordance with the tool name + summary.
  2. Tapping confirm re-invokes `/api/ai/chat` with `confirmed: true`.
  3. Covered by item 2.2.5.

### 2.4 — Global frontend error boundary
**Sprint 1 residual closeout status: IMPLEMENTED (with E2E test).**
`scout-ui/components/ErrorBoundary.tsx` wraps `AuthProvider + AppShell`
in `scout-ui/app/_layout.tsx`. Residual closeout adds a DEV-gated
`/__boom` route (`scout-ui/app/__boom.tsx`) that renders a trigger
button — clicking it flips a state flag and the next render throws,
which the boundary catches. `smoke-tests/tests/error-boundary.spec.ts`
exercises this path end-to-end when `EXPO_PUBLIC_SCOUT_E2E=true` is
set in the expo export environment. The route renders an inert "Not
available" stub in production builds (flag unset).

- **Area:** frontend
- **Status:** IMPLEMENTED — per-component only (Frontend Roadmap §11)
- **Why it matters:** a render crash anywhere in the Expo Router tree
  produces a blank screen with no recovery path.
- **Launch impact:** medium
- **Verification gap:** no top-level boundary component.
- **Scope:** S
- **Owner:** frontend
- **Acceptance:**
  1. New `components/ErrorBoundary.tsx` wrapped around `_layout.tsx`.
  2. Renders "Something went wrong — reload?" fallback with a button.
  3. Playwright test forces a thrown error inside a surface and asserts
     the boundary fallback renders.

### 2.5 — Meals subpages smoke
**Sprint 1 status: IMPLEMENTED.** New
`smoke-tests/tests/meals-subpages.spec.ts` covers `/meals/this-week`,
`/meals/prep`, and `/meals/reviews`. Both subpages previously had zero
coverage.

- **Area:** frontend
- **Status:** IMPLEMENTED (Frontend Roadmap §6; Reconciliation §2)
- **Why it matters:** 539 total lines of real UI (`prep.tsx` +
  `reviews.tsx` + weekly generation loop in `this-week.tsx`) have zero
  smoke coverage.
- **Launch impact:** low
- **Verification gap:** no page-load test on either subpage; no test
  for the weekly plan generation loop.
- **Scope:** S
- **Owner:** frontend
- **Acceptance:**
  1. Playwright load test for `/meals/prep` asserts the "Sunday Prep"
     header renders or the no-plan empty state renders.
  2. Playwright load test for `/meals/reviews` asserts the rating UI
     renders or the empty state renders.
  3. Playwright test loads `/meals/this-week` after a plan exists and
     asserts generation buttons render. (Does **not** drive a real AI
     generation — too slow.)

### 2.6 — Production error reporting
- **Area:** ops / frontend
- **Status:** DEFERRED (Frontend Roadmap §13)
- **Why it matters:** production JS errors are invisible. A broken build
  on the Vercel side would be found only when a user reports it.
- **Launch impact:** medium
- **Verification gap:** no provider wired.
- **Scope:** M
- **Owner:** frontend
- **Acceptance:**
  1. Error provider (Sentry-equivalent) configured in `scout-ui` with
     `dsn` via env var.
  2. Errors from the global error boundary (item 2.4) report upstream.
  3. `scout-ui/app/_layout.tsx` initialization documented in
     `docs/private_launch.md`.

### 2.7 — Bonus / penalty parent payout endpoint + UI wiring
- **Area:** full-stack
- **Status:** PARTIAL (Backend Roadmap §2; Frontend Roadmap §4)
- **Why it matters:** parent payout card already renders bonus/penalty
  buttons, but the handlers are explicitly "not implemented yet". Two
  visible buttons that do nothing is user-perceptible debt.
- **Launch impact:** low (payout itself works)
- **Verification gap:** no endpoint, no handler, no test.
- **Scope:** M
- **Owner:** full-stack
- **Acceptance:**
  1. Backend: `POST /families/{id}/allowance/adjustments` with
     `{member_id, cents, reason, kind ∈ {bonus, penalty}}`.
  2. Writes an `allowance_ledger` row (new `adjustment_kind` column
     required; migration `014_allowance_adjustments.sql`).
  3. Backend test covers create + appears-in-payout path.
  4. Parent payout card wires the buttons; Playwright test covers one
     bonus + one penalty adjustment.

### 2.8 — `dietary_preferences` → weekly meal plan generator wiring
- **Area:** backend / ai
- **Status:** PARTIAL (Backend Roadmap §5; AI Roadmap §6 and §7)
- **Why it matters:** the `dietary_preferences` table exists but the
  weekly-plan generator (790 lines in `weekly_meal_plan_service.py`)
  ignores it. Families with dietary restrictions get generic plans.
- **Launch impact:** low for single family today, high if we ever
  onboard a family with real restrictions.
- **Verification gap:** no wiring + no test.
- **Scope:** S
- **Owner:** backend
- **Acceptance:**
  1. `weekly_meal_plan_service.build_context()` reads
     `dietary_preferences` for the target family.
  2. Prompt includes a "constraints" block with allergies / dislikes /
     diet labels.
  3. New test asserts a plan generated for a family with
     `nut_allergy=true` does not include nut-based staples.

---

## Bucket 3 — Next 30 days

Items that materially improve the product after launch stabilization +
sprint 1 land.

### 3.1 — AI streaming response pipeline
- **Area:** ai / full-stack
- **Status:** DEFERRED (AI Roadmap §1 and §12 ledger #1)
- **Why it matters:** request/response makes every long reply feel slow.
  The `AsyncIterator` import in `provider.py` is aspirational — no SSE
  endpoint exists. Biggest perceived-latency cost in the product.
- **Launch impact:** low for launch gate; high for daily UX quality.
- **Verification gap:** no SSE path, no client incremental render.
- **Scope:** L
- **Owner:** full-stack
- **Acceptance:**
  1. Server adds `/api/ai/chat/stream` SSE endpoint using the Anthropic
     streaming API.
  2. Client `sendChatMessage()` optionally switches to the streaming
     endpoint behind a feature flag.
  3. Typing indicator in ScoutPanel.
  4. Playwright test opens the stream and asserts multiple chunks
     arrive before `response.end`.

### 3.2 — Provider retry / fallback on upstream 5xx
- **Area:** ai / backend
- **Status:** DEFERRED (AI Roadmap §1)
- **Why it matters:** a single 5xx from Anthropic surfaces to the user
  as an error banner. No retry, no backoff, no fallback provider.
- **Launch impact:** low today; medium if Anthropic has a bad hour.
- **Verification gap:** no test forces a 5xx.
- **Scope:** S
- **Owner:** backend
- **Acceptance:**
  1. `AnthropicProvider.chat()` retries once on `5xx` with
     exponential-backoff.
  2. Test with a mocked 5xx asserts the retry path and the final error
     message matches the expected "temporarily unavailable" copy.

### 3.3 — Scheduled daily brief delivery
- **Area:** ai / backend
- **Status:** DEFERRED (AI Roadmap §8 and ledger #7)
- **Why it matters:** daily brief and weekly plan exist but are
  on-demand only. Nobody sees them without tapping a button, which
  kills the "morning brief" use case.
- **Launch impact:** low for launch; high for engagement.
- **Verification gap:** no scheduler, no delivery channel.
- **Scope:** M
- **Owner:** backend
- **Acceptance:**
  1. Daily cron job (Railway scheduled service or APScheduler) runs
     `generate_daily_brief` for each active adult at 06:00 local.
  2. Brief is written as a `parent_action_item` (so it surfaces in the
     existing Action Inbox).
  3. Backend test covers the cron entry point + action-item creation.

### 3.4 — Cost / latency observability for AI
- **Area:** ops / ai
- **Status:** DEFERRED (AI Roadmap §9 and ledger #10)
- **Why it matters:** currently the only observability is stdout log
  lines. No dashboard, no alert, no per-family cost tracking, no
  token budgeting.
- **Launch impact:** low now; rises sharply as usage grows.
- **Verification gap:** no aggregation layer.
- **Scope:** M
- **Owner:** ops
- **Acceptance:**
  1. Structured log format: `ai_chat_{start,success,fail}` lines emit
     `trace_id`, `conversation_id`, `tool_name`, `duration_ms`,
     `input_tokens`, `output_tokens`.
  2. A minimal aggregation script in `scripts/` reports totals per
     family per day from the Railway log archive.
  3. Documented in `docs/private_launch.md`.

### 3.5 — AI deploy drift watchdog
- **Area:** ops / ai
- **Status:** DEFERRED (AI Roadmap §11; Unknowns list)
- **Why it matters:** the deployed-smoke artifact should cover all
  smoke tests, not a subset. Today it's auth + surfaces (9 tests); the
  AI panel test is local-only. Every other drift risk in the product
  needs to land against prod at the same cadence.
- **Launch impact:** low today; medium as deploys become routine.
- **Verification gap:** CI job does not run full smoke against the
  deployed URLs.
- **Scope:** S
- **Owner:** ops
- **Acceptance:**
  1. New GitHub Actions job `smoke-deployed` runs the full Playwright
     suite against `https://scout-ui-gamma.vercel.app` after a deploy
     completes.
  2. Result attached to `docs/release_candidate_report.md` as the
     canonical post-deploy check.

### 3.6 — RexOS / Exxir placeholder panel decision
- **Area:** product / frontend
- **Status:** IMPLEMENTED — stub copy (Frontend Roadmap §3)
- **Why it matters:** two visible personal-surface panels that do
  nothing. Either they become features or they should be removed /
  relabeled.
- **Launch impact:** low
- **Verification gap:** product decision pending.
- **Scope:** S (decision) + variable (execution)
- **Owner:** product → frontend
- **Acceptance:** a decision recorded in `docs/ROADMAP_RECONCILIATION.md`
  + the matching code change.

### 3.7 — Notification delivery channel for AI
- **Area:** ai / backend
- **Status:** DEFERRED (Backend Roadmap §7; AI Roadmap §6; ledger #8)
- **Why it matters:** `send_notification_or_create_action` logs but
  does not deliver. The tool name makes a promise the system cannot
  keep. Action Inbox currently covers the need, which is why this is
  not urgent, but the tool name is misleading.
- **Launch impact:** low
- **Verification gap:** no delivery transport.
- **Scope:** M
- **Owner:** backend
- **Acceptance:**
  1. Choose a channel (email or push) and document the decision.
  2. Implement the delivery path or rename the tool to
     `create_action_item`.
  3. Update audit + test coverage to reflect the chosen behavior.

---

## Bucket 4 — Later / strategic

Items that are real work but would be premature before Buckets 1–3 land.

### 4.1 — Real integrations layer (OAuth + API clients + webhooks + schedulers)
- **Area:** backend
- **Status:** PARTIAL (Backend Roadmap §9)
- **Scope:** L (multi-sprint)
- **Notes:** current ingestion path is dev-mode buttons with pre-built
  payloads. Google Calendar, YNAB, Apple Health, Nike Run Club all
  require real OAuth + real API clients + webhook receivers + delta
  sync + ingestion audit log + iCal feed parsing (the CHECK constraint
  already permits `ical`). This is the biggest strategic backend gap.

### 4.2 — Multi-instance safe rate limiter + distributed bootstrap
- **Area:** backend / ops
- **Status:** DEFERRED (Backend Roadmap §1 and ledger)
- **Scope:** M
- **Notes:** blocker only if we horizontally scale. In-memory limiter
  is correct for a single Railway instance.

### 4.3 — Conversation resume across sessions in ScoutPanel
- **Area:** frontend / ai
- **Status:** DEFERRED (AI Roadmap §4 and ledger #10)
- **Scope:** M
- **Notes:** conversations persist server-side; the panel always opens
  blank. Not urgent at family scale.

### 4.4 — Prompt caching
- **Area:** ai
- **Status:** DEFERRED (AI Roadmap ledger #12)
- **Scope:** S
- **Notes:** every turn rebuilds the system prompt. Fine at current
  volume; measurable cost reduction if traffic grows.

### 4.5 — Second AI provider
- **Area:** ai
- **Status:** DEFERRED (AI Roadmap ledger #13)
- **Scope:** L
- **Notes:** single-provider risk is acceptable for private use.

### 4.6 — Bundle-size CI gate + Web Vitals
- **Area:** frontend / ops
- **Status:** DEFERRED (Frontend Roadmap §13)
- **Scope:** M
- **Notes:** unmeasured today.

### 4.7 — Accessibility audit
- **Area:** frontend
- **Status:** DEFERRED (Frontend Roadmap ledger)
- **Scope:** M
- **Notes:** never run.

### 4.8 — Multi-member session switching
- **Area:** frontend
- **Status:** DEFERRED (Frontend Roadmap §2)
- **Scope:** M
- **Notes:** each member signs in individually today. Fine at family
  scale.

### 4.9 — Offline / PWA / service worker
- **Area:** frontend
- **Status:** DEFERRED (Frontend Roadmap §13)
- **Scope:** L
- **Notes:** Expo Web export does not ship one.

### 4.10 — Skeleton loaders (replace spinners)
- **Area:** frontend
- **Status:** DEFERRED (Frontend Roadmap ledger)
- **Scope:** M
- **Notes:** functional polish; no launch impact.

---

## Bucket 5 — Unknowns needing inspection first

These items cannot be ranked without first answering a factual question.
Each one has a cheap investigation task before scope can be sized.

### 5.1 — Does `ai-panel.spec.ts` pass against deployed URLs today?
- **Area:** ai / ops
- **Status:** UNKNOWN (AI Roadmap §11; Unknowns list)
- **Investigation:** run the test once against the production URL.
  Outcome: either promotes the AI panel to VERIFIED or exposes a real
  deploy drift bug. (This is the factual answer that Bucket 1.1 ships.)

### 5.2 — Is the parent household insight banner's `off_track` / `at_risk` heuristic reviewed?
- **Area:** product
- **Status:** UNKNOWN (Frontend Roadmap §4 and §Unknowns)
- **Investigation:** product-owner review of `scout-ui/app/parent/index.tsx`
  banner logic. Outcome: either validated or replaced with a
  rule-engine-backed explanation (which is AI Roadmap Phase B item 2).

### 5.3 — Does `sendChatMessage` gracefully handle a 60s timeout?
- **Area:** frontend / ai
- **Status:** UNKNOWN (Frontend Roadmap Unknowns)
- **Investigation:** force a 60s hang in a test and observe panel
  state. If it tears, add to Bucket 2.

### 5.4 — Do Railway logs show `ai_chat_*` lines from real production traffic since `9481f8f`?
- **Area:** ops
- **Status:** UNKNOWN (AI Roadmap §9; Unknowns list)
- **Investigation:** grep Railway log archive. Outcome: either promotes
  correlation logging to VERIFIED or exposes a format/transport bug.

### 5.5 — Has any tool been invoked in production since deploy?
- **Area:** ops
- **Status:** UNKNOWN (AI Roadmap Unknowns)
- **Investigation:** `SELECT COUNT(*) FROM ai_tool_audit WHERE created_at > '2026-04-12';`
  against production Postgres. Outcome: tells us whether the product
  is being used at all, and whether audit rows actually land in prod.

### 5.6 — Does the weekly meal plan generation loop complete within the 60s request timeout against production Postgres?
- **Area:** ai / backend
- **Status:** UNKNOWN (AI Roadmap §7; Unknowns list)
- **Investigation:** trigger a generation through the deployed UI once
  and time the request. If >60s: bumps `SCOUT_AI_REQUEST_TIMEOUT` or
  moves generation to an async path (potential Bucket 3 item).

### 5.7 — ~~Actual Playwright test count~~
- **Area:** ops
- **Status:** RESOLVED. Current count is **28 tests across 8 files**
  (auth 5 + surfaces 7 + ai-panel 3 + ai-roundtrip 2 + write-paths 6
  + meals-subpages 3 + dev-mode 1 + error-boundary 1). Verified by
  source inspection against `4e8d2e9`.

---

## Top 10 Ranked Backlog (post-Sprint-2-feature-work)

Worst-trust-gap-first. All items below are strategic completion /
polish / observability — none of them gate the current private launch.

| # | Item | Area | Bucket | Scope |
|---|---|---|---|---|
| 1 | Deployed browser smoke in CI against Vercel (full Playwright via Railway smoke creds) | ai/ops | 2 | S |
| 2 | Provider retry / fallback on Anthropic 5xx | backend | 2 | S |
| 3 | Production error reporting wired into `ErrorBoundary` (Sentry-equivalent) | frontend/ops | 2 | M |
| 4 | `dietary_preferences` → weekly meal plan generator wiring | backend / ai | 2 | S |
| 5 | Scheduled daily brief / weekly plan delivery (via `parent_action_items`) | backend / ai | 2 | M |
| 6 | AI cost / latency / per-family observability (structured log format + aggregation) | ops / ai | 2 | M |
| 7 | Streaming assertion depth in Playwright (chunk-by-chunk smoke) | frontend | 3 | S |
| 8 | AI-settings toggle smoke (`allow_general_chat` / `allow_homework_help` round-trip) | frontend | 3 | S |
| 9 | Bonus / penalty parent payout endpoint + UI wiring + `allowance_adjustments` migration | full-stack | 3 | M |
| 10 | Prompt caching for static system-prompt prefix | ai | 3 | S |

**Later / strategic (not ranked above):**
- Real integrations layer (OAuth + API + webhooks + schedulers)
- Multi-instance safe rate limiter
- Conversation resume across sessions in ScoutPanel
- Second AI provider
- RexOS / Exxir product decision
- Notification delivery channel for `send_notification_or_create_action`
- Moderation false-positive feedback loop
- Account create / password reset smoke
- Handoff target-screen content assertion
- Bundle-size CI gate + Web Vitals
- Accessibility audit
- Offline / PWA / service worker
- Skeleton loaders
- Multi-member session switching

---

## Direct answers (post-Sprint-2-feature-work)

**1. What is the single biggest backend gap now?**
→ Provider retry / fallback on Anthropic 5xx + cost / latency
observability. A single upstream hiccup still surfaces as a
user-visible error banner, and there is no dashboard to see how often
this happens. Real integrations layer remains a strategic Bucket-4
item but is not the most immediately useful gap to close.

**2. What is the single biggest frontend gap now?**
→ Deployed browser smoke in CI. 28 Playwright tests run locally, the
production AI backend is verified via direct HTTPS round-trip, but the
full browser-rendered path against `scout-ui-gamma.vercel.app` has
never been run from an automated job. Deploy drift between local and
Vercel is currently invisible.

**3. What is the single biggest AI gap now?**
→ Observability, specifically a structured event store for
conversation-level metrics (duration, tokens, tool calls). The
functional gaps have closed: streaming ships, moderation ships,
broad-chat + homework flags ship, confirmation flow ships, production
round-trip is verified. What's missing is the ability to see how it's
being used at scale.

**4. Which "done" claim should be treated most skeptically?**
→ "Deployed AI verified." True for the backend path (HTTPS round-trip
+ Railway logs + prod DB deltas). Not yet true for the browser
rendering path in CI — that's the single residual item that prevents
a clean "deployed AI = VERIFIED" claim across the whole stack.

**5. Which 3 items most improve trust if completed next?**
1. **#1 — Deployed browser smoke in CI** (closes the last deploy-drift
   gap; cheap; cannot hurt).
2. **#3 — Production error reporting** wired into the existing
   `ErrorBoundary` (closes the "broken prod JS is invisible" gap).
3. **#6 — AI cost / latency observability** (shifts the product from
   "works" to "works and we can see why" for the AI path).
