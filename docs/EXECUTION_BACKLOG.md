# Scout Execution Backlog

Last built: 2026-04-13 from `BACKEND_ROADMAP.md`, `FRONTEND_ROADMAP.md`,
`AI_ROADMAP.md`, `docs/ROADMAP_RECONCILIATION.md`, `docs/release_candidate_report.md`,
`docs/private_launch.md`.

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

Items that, if left broken, can degrade the single family currently using
Scout. These are the only items that should block a fresh deploy today.

### 1.1 — Deployed AI-panel smoke (first-ever against Railway + Vercel)
- **Area:** ai / ops
- **Status:** PARTIAL (AI Roadmap §10, §11)
- **Why it matters:** `ai-panel.spec.ts` has never been recorded as run
  against the deployed URLs. The 9/9 deployed smoke in
  `release_candidate_report.md` covered auth + surfaces only. Drift
  between local main and production is currently invisible.
- **Launch impact:** high
- **Verification gap:** zero evidence the ScoutPanel actually gets a 200
  from Railway through Vercel today.
- **Scope:** S
- **Owner:** ops
- **Acceptance:**
  1. `npx playwright test smoke-tests/tests/ai-panel.spec.ts` runs
     against `https://scout-ui-gamma.vercel.app` with the production
     backend and passes.
  2. Result recorded in `docs/release_candidate_report.md` as "10/10
     deployed smoke".
  3. Railway logs spot-checked for one `ai_chat_success` line with a
     real `X-Scout-Trace-Id`.

### 1.2 — ScoutPanel disabled-state handling
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

### 5.7 — Actual Playwright test count: 12 or 13?
- **Area:** ops
- **Status:** UNKNOWN (Frontend Roadmap Unknowns)
- **Investigation:** `npx playwright test --list`. Reconcile with the
  "12/12 preflight" number recorded at `549723b` vs the 13 `test(`
  declarations visible in the repo today.

---

## Top 25 Ranked Backlog

Worst-impact-first, biased toward closing verification gaps, finishing
over-called "done" areas, and improving real-world trust.

| # | Item | Area | Bucket | Scope |
|---|---|---|---|---|
| 1 | Deployed AI-panel smoke against Railway + Vercel | ai/ops | 1 | S |
| 2 | Write-path E2E smoke suite (six tests) | full-stack | 2 | M |
| 3 | AI panel verification depth (content + tool round-trip + child + handoff) | full-stack | 2 | M |
| 4 | Confirmation-flow UI inside ScoutPanel | frontend | 2 | M |
| 5 | Global frontend error boundary | frontend | 2 | S |
| 6 | ScoutPanel disabled-state handling | frontend | 1 | S |
| 7 | Production error reporting (Sentry-equivalent) | frontend/ops | 2 | M |
| 8 | Meals `prep.tsx` + `reviews.tsx` + generation-loop smoke | frontend | 2 | S |
| 9 | Provider retry / fallback on upstream 5xx | backend | 3 | S |
| 10 | AI streaming response pipeline | full-stack | 3 | L |
| 11 | `dietary_preferences` → weekly meal plan generator | backend | 2 | S |
| 12 | Scheduled daily brief delivery | backend | 3 | M |
| 13 | Cost / latency observability for AI | ops | 3 | M |
| 14 | AI deploy drift watchdog (full smoke against deployed URLs in CI) | ops | 3 | S |
| 15 | Bonus / penalty parent payout endpoint + UI | full-stack | 2 | M |
| 16 | Dev-mode ingestion button prod-behavior audit | frontend | 1 | S |
| 17 | Investigate: does `ai-panel.spec.ts` pass against deployed URLs (feeds #1) | ai/ops | 5 | S |
| 18 | Investigate: Railway logs showing `ai_chat_*` lines | ops | 5 | S |
| 19 | Investigate: audit-table rows since deploy | ops | 5 | S |
| 20 | RexOS / Exxir product decision + execution | product/frontend | 3 | S |
| 21 | Notification delivery channel for `send_notification_or_create_action` | backend | 3 | M |
| 22 | Real integrations layer (OAuth + API + webhooks + schedulers) | backend | 4 | L |
| 23 | Multi-instance safe rate limiter + distributed bootstrap state | backend/ops | 4 | M |
| 24 | Investigate: sendChatMessage 60s timeout behavior | frontend | 5 | S |
| 25 | Conversation resume across sessions in ScoutPanel | frontend/ai | 4 | M |

---

## Direct answers to required questions

**1. What is the single biggest backend gap now?**
→ Real integrations layer (§4.1). Google Calendar / YNAB / Apple Health /
Nike Run Club ingestion today is dev-mode buttons hitting pre-built
payloads. No real OAuth, no live API clients, no webhooks, no
schedulers, no delta sync, no ingestion audit log. The scaffolding is
correct; the real-world integration story is not built. Everything
else in the backend is either VERIFIED or small-scope debt.

**2. What is the single biggest frontend gap now?**
→ Write-path E2E smoke coverage (§2.1). Every main surface is read-path
only. Task completion, grocery approve, weekly payout, meal-plan
approve, and meal-review submit are the user flows that define the
product's daily value, and regressions in any of them would escape CI.

**3. What is the single biggest AI gap now?**
→ Deployed browser verification + thin smoke assertions combined (§1.1
and §2.2). `ai-panel.spec.ts` has never been recorded as run against
Railway + Vercel, and even locally it only checks "no 5xx and no error
banner." The real behavior through the real UI against the real
backend is UNKNOWN. Streaming is the biggest *feature* gap, but
verification is the biggest *trust* gap.

**4. Which "done" claim should be treated most skeptically?**
→ "AI orchestration layer — DONE" as it appeared in the old
`BACKEND_ROADMAP.md §10`. Reality: the backend orchestration is solid
and covered by 29 backend tests, but the deployed UX is PARTIAL, smoke
is thin, confirmation flow cannot complete through the UI, streaming
does not exist, and deployed verification is UNKNOWN. Calling that
"done" was launch-sufficient, not strategically complete.

**5. Which 3 items most improve trust if completed next?**
1. **#1 — Deployed AI-panel smoke run** (closes the single biggest
   UNKNOWN in the entire product; cheap; cannot hurt).
2. **#2 — Write-path E2E smoke suite** (the six tests that would catch
   the most impactful regressions across every main surface).
3. **#5 + #7 — Global error boundary + production error reporting**
   (together, they close the "broken prod would be invisible" gap).
