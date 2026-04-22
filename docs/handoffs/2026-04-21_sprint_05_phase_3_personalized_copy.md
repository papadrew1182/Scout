# Sprint 05 Phase 3 - Personalized Copy + Held-Dispatch Worker - handoff

**Prepared:** 2026-04-21
**Branch:** `sprint/sprint-05-phase-3-personalized-copy`
**Base:** `main` post-PR #55 (Phase 2 merge `c6cd74f`)
**Spec:** `SCOUT_SPRINT_05_PROACTIVE_NUDGES.md`
**Plan:** `docs/plans/2026-04-21-sprint-05-plan.md` §7 Phase 3

## What shipped

### AI composer (revised plan Section 7 Phase 3)
- `orchestrator.generate_nudge_body(...)` in `backend/app/ai/orchestrator.py`:
  - Dedicated entry point; does NOT write `ai_conversations` / `ai_messages` rows.
  - Uses `settings.ai_nudge_model` (PR #48 config).
  - System prompt includes the member's personality preamble + "no em dashes".
  - 80-token cap.
  - 3-second default timeout.
  - Raises on missing model, empty response, moderation/refusal stop_reason, or provider timeout.
  - 14 tests in `backend/tests/test_nudge_composer.py`.

- `nudges_service.compose_body(db, family_id, proposals, now_utc)`:
  - Wraps generate_nudge_body with the four-fallback matrix per plan Section 5:
    1. `ai_available=false` -> fixed template.
    2. Weekly AI soft cap hit -> fixed template.
    3. Moderation/refusal (orchestrator RuntimeError) -> fixed template.
    4. Timeout or any other composer exception -> fixed template.
  - Every fallback logs INFO with a `reason` tag.
  - Single-proposal bundles -> `_render_body`; multi-proposal bundles -> `_render_bundle_body`.

- `dispatch_with_items` now calls `compose_body` instead of `_render_body` / `_render_bundle_body` directly. Body composition runs inside the per-bundle SAVEPOINT so a composer timeout cannot leave orphaned parent/child rows.

- Personality substring matrix tests (3 personalities: terse / warm / formal) confirm the preamble reaches `generate_nudge_body` intact.

### Held-dispatch delivery worker (Phase 2 follow-up absorbed into P3)
- `nudges_service.process_pending_dispatches(db, now_utc)`:
  - Finds `NudgeDispatch` rows with `status='pending'` AND `deliver_after_utc <= now_utc` AND `parent_action_item_id IS NULL`.
  - Writes the ParentActionItem row (using the body already composed at dispatch time), attempts push, flips status to 'delivered'.
  - Per-row SAVEPOINT isolation.
  - Push errors leave Inbox intact.
  - Suppressed rows are never touched.
  - 6 tests.

- `process_pending_dispatches_tick` wrapper + scheduler wiring:
  - Runs immediately after `run_nudge_scan_tick` on each 5-min tick.
  - Same db_factory/try/commit/except/rollback/finally/close pattern as other tick runners.
  - End-to-end test simulates tick 1 (holds) + tick 2 (surfaces).

### Tests
- `backend/tests/test_nudges.py`: 85 pass (prior 66 + 7 compose_body + 3 personality matrix + 2 dispatch-uses-compose + 6 process_pending + 1 end-to-end tick) + 1 pre-existing unrelated failure.
- `backend/tests/test_nudge_composer.py`: 14 pass (new).
- Full regression: 806+ pass.

## What this phase does NOT do

- **AI-driven trigger discovery.** Phase 5 scope.
- **Admin rule engine.** Phase 4 scope.
- **Route-hint deep linking from Recent nudges.** Deferred.
- **Per-member quiet-hours admin UI.** Still only direct `member_config` writes.
- **Held-dispatch body recomposition.** The body is composed at the original dispatch time and reused verbatim when surfaced. If the member changes their personality between dispatch and surfacing, the held body reflects the old preamble. Not a real issue at 10 minute / few-hour hold windows; worth noting.

## Known follow-ups

1. **Pre-existing test failure** `TestScannerStampsOccurrence::test_overdue_task_scanner_stamps_due_at` - DST/TZ assertion that flakes around midnight UTC vs America/Chicago. Documented since Phase 2. Not caused by this sprint.
2. **Admin rule engine (Phase 4)**: SQL whitelist + CRUD + preview.
3. **AI-driven discovery (Phase 5)**: hourly AI scan with soft-cap + dedupe against P1 built-ins.

## Arch check

Run before committing handoff:
- Before: 0 WARN, 1 INFO (seedData drift - pre-existing).
- After: 0 WARN, 1 INFO (seedData drift - pre-existing).
- Delta: 0 new WARNs (Phase 3 is service + scheduler changes, no new routes or mutations).

## On Andrew's plate

- [ ] Review the PR.
- [ ] Merge (squash).
- [ ] No migration this phase -- nothing to apply on Railway.
- [ ] Verify Railway `/health` and Vercel post-merge (no frontend changes this phase; Vercel should no-op).
- [ ] Pull main locally; delete the phase branch.

## Parallel-session note

Concurrent Claude Code sessions continued to drift HEAD during Phase 3; every subagent re-verified branch before each write and before each commit. No rework needed.
