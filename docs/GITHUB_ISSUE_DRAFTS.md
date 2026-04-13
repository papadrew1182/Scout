# GitHub Issue Drafts

Last reconciled: 2026-04-13 against commit `4e8d2e9` on `main`.

Source: `docs/EXECUTION_BACKLOG.md`. Copy-paste ready, ordered by the
post-Sprint-2-feature-work top 10. Every draft here is a strategic
completion / observability / polish item — none of them are
launch-stability work.

## Closed items — do NOT re-open these

All of the previously-drafted issues below have landed on `main` and
been VERIFIED. If you suspect a regression, open a new bug issue
against the specific symptom, do not reopen the old draft.

- ~~Run `ai-panel.spec.ts` against Railway + Vercel for the first time~~
  — **RESOLVED 2026-04-13** via `smoke@scout.app` direct HTTPS
  round-trip + Railway log evidence + prod DB row deltas (`782c3ef`).
- ~~Add write-path E2E smoke suite (6 tests)~~ — **RESOLVED** in Sprint
  1 residual closeout.
- ~~Deepen AI panel smoke — content + tool round-trip + role variants~~
  — **RESOLVED** in Sprint 1 closeout + residual closeout.
- ~~Render confirmation-flow UI inside ScoutPanel~~ — **RESOLVED** in
  Sprint 1 closeout (`5f11821`).
- ~~Add global frontend error boundary~~ — **RESOLVED** in Sprint 1
  closeout + residual closeout.
- ~~ScoutPanel disabled-state handling~~ — **RESOLVED** in Sprint 1
  closeout (`5f11821`).
- ~~Cover `meals/prep.tsx`, `meals/reviews.tsx`, weekly generation
  loop with smoke tests~~ — **RESOLVED** in Sprint 1 closeout.
- ~~Decide production behavior for dev-mode ingestion buttons~~ —
  **RESOLVED** in Sprint 1 closeout.
- ~~AI streaming response pipeline~~ — **RESOLVED** in `4e8d2e9`.

---

## 1. Deployed browser smoke in CI against Vercel

**Problem statement**

The production AI backend path is verified end-to-end via a direct
HTTPS round-trip (`smoke@scout.app`), and Railway logs confirm the
`ai_chat_*` pipeline is reaching the log layer. What is **not** wired
up is a CI job that runs the full 28-test Playwright suite against
`https://scout-ui-gamma.vercel.app` on every push. Deploy drift
between local `main` and the Vercel bundle is currently invisible.

**Acceptance criteria**

- [ ] New GitHub Actions job `smoke-deployed` runs after each push to
      `main` that produces a successful deploy.
- [ ] Uses `SCOUT_SMOKE_ADULT_EMAIL` / `SCOUT_SMOKE_ADULT_PASSWORD`
      from GitHub Actions secrets (mirroring the Railway env vars).
- [ ] Points at `SCOUT_WEB_URL=https://scout-ui-gamma.vercel.app` and
      `SCOUT_API_URL=https://scout-backend-production-9991.up.railway.app`.
- [ ] Runs the full 28-test suite (or at minimum `auth`, `surfaces`,
      `ai-panel`, `ai-roundtrip`).
- [ ] Result posted to `docs/release_candidate_report.md` on each
      successful run.

**Evidence / source**

- `AI_ROADMAP.md` §12, §13
- `docs/EXECUTION_BACKLOG.md` top 10 item #1
- `docs/AI_OPERATOR_VERIFICATION.md`

**Labels:** `ai`, `ops`, `verification`, `scope:S`

---

## 2. Provider retry / fallback on Anthropic 5xx

**Problem statement**

A single 5xx from Anthropic currently surfaces to the user as an error
banner. No retry, no backoff. `AnthropicProvider.chat()` and
`chat_stream()` both need a bounded retry + backoff path.

**Acceptance criteria**

- [ ] `AnthropicProvider.chat()` retries once on 5xx with exponential
      backoff (e.g. 250ms + jitter).
- [ ] `AnthropicProvider.chat_stream()` retries at stream-start on 5xx
      (not mid-stream).
- [ ] New backend test with a mocked 5xx asserts the retry path and
      the final error copy when both attempts fail.
- [ ] Log line `ai_chat_retry trace=... attempt=1 reason=...`.

**Evidence / source**

- `AI_ROADMAP.md` §1 — gaps
- `BACKEND_ROADMAP.md` §7 — gaps

**Labels:** `ai`, `backend`, `reliability`, `scope:S`

---

## 3. Production error reporting wired into `ErrorBoundary`

**Problem statement**

The global `ErrorBoundary` exists and is verified via the gated
`/__boom` Playwright route, but it logs to stdout only. Production JS
errors are currently invisible unless a user reports them or they
correlate with backend log noise.

**Acceptance criteria**

- [ ] Error provider (Sentry-equivalent) chosen and documented in
      `docs/private_launch.md`.
- [ ] `dsn` exposed via `EXPO_PUBLIC_*` env var in the Vercel build.
- [ ] `ErrorBoundary.componentDidCatch` forwards errors upstream.
- [ ] Global unhandled-promise-rejection handler also reports.
- [ ] A deliberate error thrown via the `/__boom` test path shows up
      in the provider within 60 seconds.

**Evidence / source**

- `FRONTEND_ROADMAP.md` §11, §13 — gaps

**Labels:** `frontend`, `ops`, `reliability`, `scope:M`

---

## 4. Wire `dietary_preferences` into the weekly meal plan generator

**Problem statement**

`dietary_preferences` table exists (migration `005_meals.sql`) but
`weekly_meal_plan_service.py` (790 lines) never reads it. Families
with real dietary restrictions get generic plans.

**Acceptance criteria**

- [ ] `weekly_meal_plan_service.build_context()` reads
      `dietary_preferences` rows for the target family.
- [ ] Prompt includes a "constraints" block describing allergies,
      dislikes, and diet labels.
- [ ] New test in `test_weekly_meal_plans.py`: family with
      `nut_allergy=true` does not surface nut-based staples.

**Evidence / source**

- `BACKEND_ROADMAP.md` §5 — gaps
- `AI_ROADMAP.md` §7 — gaps

**Labels:** `backend`, `ai`, `scope:S`

---

## 5. Scheduled daily brief delivery

**Problem statement**

`generate_daily_brief` works on demand but nobody sees the output
without tapping a button. No cron, no push, no Action Inbox entry on
a schedule.

**Acceptance criteria**

- [ ] Daily job (Railway scheduled service or APScheduler) runs
      `generate_daily_brief` for each active adult at 06:00 local.
- [ ] Brief is written as a `parent_action_item` so it surfaces in the
      existing Action Inbox.
- [ ] Backend test covers the cron entry point + action-item creation.
- [ ] Documented in `docs/private_launch.md`.

**Evidence / source**

- `AI_ROADMAP.md` §8 — gaps
- Backend §7 deferred ledger

**Labels:** `ai`, `backend`, `scope:M`

---

## 6. AI cost / latency observability

**Problem statement**

The only AI observability today is `ai_chat_start` / `ai_chat_success`
/ `ai_chat_fail` stdout log lines. No dashboard, no alert, no per-family
cost tracking, no token budgeting.

**Acceptance criteria**

- [ ] Structured log format on success: `trace_id`, `conversation_id`,
      `tool_name` (or `null` if no tool), `duration_ms`, `input_tokens`,
      `output_tokens`, `model`.
- [ ] Minimal aggregation script in `scripts/` that reports totals per
      family per day by parsing Railway log archives.
- [ ] Documented in `docs/private_launch.md` with a sample output.
- [ ] No production code path is load-bearing on the aggregation; it
      runs out-of-band.

**Evidence / source**

- `AI_ROADMAP.md` §11 — gaps

**Labels:** `ai`, `ops`, `observability`, `scope:M`

---

## 7. Streaming assertion depth in Playwright

**Problem statement**

The SSE streaming path is live and used by the panel by default, but
no Playwright test asserts chunk-by-chunk rendering. The
`ai-panel.spec.ts` / `ai-roundtrip.spec.ts` tests only assert final
content, not the stream's incremental behavior.

**Acceptance criteria**

- [ ] New `smoke-tests/tests/ai-streaming.spec.ts` (or extension to
      `ai-panel.spec.ts`) that:
  - [ ] Opens the panel and fires a quick action.
  - [ ] Observes the assistant bubble's text content growing across
        multiple observation points before the final `done`.
  - [ ] Skips if `ai_available=false`.

**Evidence / source**

- `AI_ROADMAP.md` §5, §12

**Labels:** `ai`, `frontend`, `verification`, `scope:S`

---

## 8. AI-settings toggle smoke

**Problem statement**

The Settings page has adult-only toggles for `allow_general_chat` and
`allow_homework_help` wired to `PATCH /api/families/{id}/ai-settings`.
Backend prompt variants for all four combinations are covered by
`test_ai_context.py`, but no Playwright test exercises the UI round-trip.

**Acceptance criteria**

- [ ] New Playwright test that logs in as an adult, navigates to
      Settings, toggles each of the two flags, and asserts the UI
      reflects the new state after the PATCH.
- [ ] Optional: fire a child-surface chat after each toggle and assert
      the response category matches the expected variant (may be
      flaky; skip if so).

**Evidence / source**

- `FRONTEND_ROADMAP.md` §8
- `AI_ROADMAP.md` §10

**Labels:** `ai`, `frontend`, `verification`, `scope:S`

---

## 9. Bonus / penalty parent payout endpoint + UI wiring

**Problem statement**

The parent payout card renders "Bonus" and "Penalty" buttons but the
handlers are explicit stubs. No backend endpoint, no model support, no
test.

**Acceptance criteria**

- [ ] Backend: `POST /families/{id}/allowance/adjustments` with
      `{member_id, cents, reason, kind ∈ {bonus, penalty}}`.
- [ ] Migration `016_allowance_adjustments.sql` adds the
      `adjustment_kind` column (or separate table, whichever fits the
      existing `allowance_ledger` model).
- [ ] Adjustment row appears in the payout calculation path.
- [ ] Backend test covers create + appears-in-payout.
- [ ] Parent payout card wires the two buttons through.
- [ ] Playwright test covers one bonus + one penalty adjustment.

**Evidence / source**

- `BACKEND_ROADMAP.md` §2 — gaps
- `FRONTEND_ROADMAP.md` §4 — gaps

**Labels:** `backend`, `frontend`, `full-stack`, `scope:M`

---

## 10. Prompt caching for static system-prompt prefix

**Problem statement**

Every turn rebuilds the system prompt from scratch. At current volume
this is fine; at higher volume it's a measurable cost.
`AnthropicProvider.chat()` can use the Anthropic SDK's prompt cache
flags for the unchanging prefix (the tool definitions + static
persona copy).

**Acceptance criteria**

- [ ] `AnthropicProvider.chat()` marks the static prompt prefix as
      cacheable via the SDK's cache flag.
- [ ] Test asserts the cache flag is set on the request.
- [ ] Documentation note in `AI_ROADMAP.md` §1 on the cache hit rate
      on a hot conversation.

**Evidence / source**

- `AI_ROADMAP.md` §1 — gaps
- `AI_ROADMAP.md` deferred ledger #8

**Labels:** `ai`, `backend`, `performance`, `scope:S`
