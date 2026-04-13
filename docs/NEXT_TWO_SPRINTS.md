# Scout — Next Two Sprints

Last reconciled: 2026-04-13 against commit `4e8d2e9` on `main`.

**Sprint 1 is complete.** All Sprint 1 items have landed. Sprint 2
feature work (broad chat, homework help, moderation, weather, AI
settings, SSE streaming, `conversation_kind`) has also landed.
Production AI backend path is VERIFIED end-to-end.

This document now tracks **Sprint 2 (strategic completion)** and
**Sprint 3 (post-trust-gap polish)**, scoped strictly to items that
are already in `docs/EXECUTION_BACKLOG.md`. It intentionally excludes
real integrations, multi-instance scaling, and other Bucket-4 items.

See `docs/ROADMAP_RECONCILIATION.md` §11 for the execution-mode
constraints that apply from here forward.

---

## Sprint 2 — Close the trust + observability gap

**Goal:** Turn "the product works" into "we can see why it works and
we know immediately when it stops." Plus the one remaining deploy
drift gap.

**Duration target:** 1 week.

**Included items (in execution order):**

1. **Backlog #1 — Deployed browser smoke in CI**
   - Wire a new GitHub Actions job (`smoke-deployed`) that runs the
     full Playwright suite against `https://scout-ui-gamma.vercel.app`
     after each deploy, using the Railway-stored
     `SCOUT_SMOKE_ADULT_EMAIL` / `SCOUT_SMOKE_ADULT_PASSWORD` env vars.
   - Result recorded in `docs/release_candidate_report.md`.
   - **Scope:** S.

2. **Backlog #2 — Provider retry / fallback on upstream 5xx**
   - `AnthropicProvider.chat()` + `chat_stream()` retry once on 5xx
     with exponential backoff.
   - New backend test with a mocked 5xx asserts retry + final error
     copy.
   - **Scope:** S.

3. **Backlog #3 — Production error reporting wired into `ErrorBoundary`**
   - Choose provider (Sentry-equivalent).
   - Wire `dsn` via env var; forward from
     `ErrorBoundary.componentDidCatch` + unhandled promise rejection
     handler.
   - Document setup in `docs/private_launch.md`.
   - **Scope:** M.

4. **Backlog #4 — `dietary_preferences` → weekly meal plan generator**
   - `weekly_meal_plan_service.build_context()` reads preferences.
   - Generator prompt includes a "constraints" block.
   - New test: family with `nut_allergy=true` does not surface
     nut-based staples.
   - **Scope:** S.

5. **Backlog #5 — Scheduled daily brief delivery**
   - Cron (Railway scheduled service or APScheduler) runs
     `generate_daily_brief` for each active adult at 06:00 local.
   - Brief is written as a `parent_action_item`.
   - Backend test covers the cron entry point + action-item creation.
   - **Scope:** M.

6. **Backlog #6 — AI cost / latency observability**
   - Structured log format: `trace_id`, `conversation_id`, `tool_name`,
     `duration_ms`, `input_tokens`, `output_tokens`.
   - Minimal aggregation script in `scripts/` reports totals per family
     per day from the Railway log archive.
   - **Scope:** M.

**Explicitly excluded from Sprint 2:**

- Real integrations layer — strategic Bucket 4; not launch-critical.
- Multi-instance rate limiter — blocker only on horizontal scale.
- Conversation resume in ScoutPanel — Bucket 4.
- Second AI provider — Bucket 4.
- Notification delivery channel for `send_notification_or_create_action`
  — deferred until integrations layer work decides the transport.
- Bundle-size CI gate, accessibility audit, offline/PWA, skeleton
  loaders — all Bucket 4 polish.

**Definition of done for Sprint 2:**

- CI job runs full Playwright against Vercel on every push and records
  the result in `release_candidate_report.md`.
- Provider retry measurable in a test with a mocked 5xx.
- Production JS errors land in the chosen error-reporting provider
  within 60 seconds of the crash.
- A family with a dietary restriction verifiably gets a plan that
  respects it.
- Daily brief lands in the Action Inbox on a schedule.
- AI latency + token usage visible per family in structured logs, and
  a script can roll them up.

---

## Sprint 3 — Post-trust-gap polish

**Goal:** Clean up the remaining "launch-sufficient but not
strategically complete" items that Sprint 2 did not cover.

**Duration target:** 1 week.

**Included items (in execution order):**

1. **Backlog #7 — Streaming assertion depth in Playwright**
   - One new test that opens the stream, consumes events, and asserts
     multiple text deltas arrive before `done`.
   - **Scope:** S.

2. **Backlog #8 — AI-settings toggle smoke**
   - Playwright flips `allow_general_chat` / `allow_homework_help`
     from the Settings page, asserts the PATCH round-trips, and
     optionally asserts a child-surface chat response matches the
     expected variant.
   - **Scope:** S.

3. **Backlog #9 — Bonus / penalty parent payout endpoint + UI**
   - Backend: `POST /families/{id}/allowance/adjustments` with
     `{member_id, cents, reason, kind ∈ {bonus, penalty}}`.
   - Migration: `016_allowance_adjustments.sql`.
   - Backend test + Playwright test covering one bonus + one penalty.
   - **Scope:** M.

4. **Backlog #10 — Prompt caching for static system-prompt prefix**
   - Use the Anthropic SDK's prompt cache flags for the per-turn
     unchanged prefix.
   - Measure reduction on a hot conversation.
   - **Scope:** S.

**Explicitly excluded from Sprint 3:**

- Real integrations layer
- Multi-instance rate limiter
- Conversation resume in ScoutPanel
- Second AI provider
- Notification delivery channel

**Definition of done for Sprint 3:**

- Playwright asserts per-chunk streaming updates.
- AI-settings toggles covered by a browser smoke.
- Bonus / penalty visible on the parent payout card and backed by real
  ledger rows.
- Prompt cache hit rate measurable in a test.

---

## Beyond Sprint 3 — Strategic (not scheduled)

These items are in the backlog but should not be scheduled into a
sprint until Sprint 2 + Sprint 3 land and the team has explicitly
decided to pick one up:

- Real integrations layer (OAuth + API clients + webhook receivers +
  delta sync + ingestion audit log) — Bucket 4, multi-sprint.
- Multi-instance safe rate limiter + distributed bootstrap — Bucket 4.
- Conversation resume across sessions in ScoutPanel — Bucket 4.
- Second AI provider — Bucket 4.
- Moderation false-positive feedback loop — low priority.
- Notification delivery channel for `send_notification_or_create_action`
  — waits on integrations transport decision.
- RexOS / Exxir product decision — Bucket 4 / product.
- Bundle-size CI gate + Web Vitals.
- Accessibility audit.
- Offline / PWA / service worker.
- Skeleton loaders (replace spinners).
- Multi-member session switching.

Nothing in this list is a launch gate. Every item is an
enhancement-over-already-shipped.
