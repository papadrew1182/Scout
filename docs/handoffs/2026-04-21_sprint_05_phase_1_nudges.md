# Sprint 05 Phase 1 - Core Nudge Engine - handoff

**Prepared:** 2026-04-21
**Branch:** `sprint/sprint-05-phase-1-nudges`
**Base:** latest `main` (post-PR #49)
**Spec:** `SCOUT_SPRINT_05_PROACTIVE_NUDGES.md`
**Plan:** `docs/plans/2026-04-21-sprint-05-plan.md`

## What shipped

- Migration 049: `scout.nudge_dispatches` (parent) + `scout.nudge_dispatch_items` (child) with UNIQUE on child.source_dedupe_key. Permission `nudges.view_own` for all user tiers.
- `NudgeDispatch` + `NudgeDispatchItem` SQLAlchemy models.
- `backend/app/services/nudges_service.py`:
  - Three built-in scanners: overdue_task, upcoming_event, missed_routine (each stamps `context['occurrence_at_utc']`).
  - `apply_proactivity`: quiet drops; balanced pass-through; forthcoming shifts (upcoming_event -30 min, missed_routine -10 min, overdue_task unchanged). Per-call member-setting cache.
  - `resolve_occurrence_fields`: reads `context['occurrence_at_utc']`, looks up family timezone, computes `occurrence_local_date` via pytz, builds stable `source_dedupe_key`.
  - `dispatch_with_items`: per-proposal SAVEPOINT, parent-child write, Inbox row, optional push via push_service. Push errors swallowed; Inbox is ground truth.
  - `run_nudge_scan` entry point; `run_nudge_scan_tick` scheduler wrapper.
- Scheduler: wired into the 5-min tick in `backend/app/scheduler.py` using the existing per-runner pattern.
- 33 backend tests in `backend/tests/test_nudges.py`. Tick-time benchmark asserts <10s with 50 overdue tasks + 20 upcoming events.

## What this phase does NOT do

- `GET /api/nudges/me` and `/settings/ai` Recent nudges section -> Phase 2.
- Smoke spec -> Phase 2 (needs the API).
- Quiet hours -> Phase 2.
- Digest batching (parent with >1 child) -> Phase 2. Phase 1 writes exactly one child per parent.
- AI-composed copy -> Phase 3.
- Admin rule engine -> Phase 4.
- AI-driven discovery -> Phase 5.

## Known follow-ups

1. **`parent_action_items.action_type` CHECK constraint.** The Inbox row currently writes `action_type='general'` because `chk_parent_action_items_action_type` (migration 020 era) does not include `nudge.*`. Trigger kind is preserved in `entity_type` for now. A small migration widening the CHECK to include `nudge.overdue_task / nudge.upcoming_event / nudge.missed_routine / nudge.custom_rule / nudge.ai_suggested` is the natural follow-up. Not blocking; inbox functionality works.
2. **Fixed copy templates.** Will be replaced by AI-composed copy in Phase 3. Existing templates remain the fallback path.
3. **Phase 1 cannot batch.** Multiple triggers for the same member become multiple separate Inbox rows + pushes. Phase 2 collapses into one parent dispatch + one Inbox row.

## On Andrew's plate

- [ ] Review PR (link to be filled after `gh pr create`).
- [ ] Merge (squash).
- [ ] Apply migration 049 on Railway via the public proxy URL pattern
      (`SCOUT_DATABASE_URL=<DATABASE_PUBLIC_URL> py backend/migrate.py`).
- [ ] Confirm Railway backend `/health` remains ok post-deploy.
- [ ] Confirm Vercel frontend deploy is green (no frontend changes this phase).
- [ ] Pull main + delete the phase branch locally.

## Arch check

- Baseline before this branch: 0 WARN, 1 INFO (seedData drift — pre-existing).
- After this branch: 0 WARN, 1 INFO. No new warnings introduced by Phase 1 backend work.

## Test suite

- 33 tests pass in `backend/tests/test_nudges.py`.
- Regression suite: 792 passed, 1 skipped, no new failures.

## Deviations from revised plan

1. `action_type="general"` instead of `f"nudge.{trigger_kind}"` — documented above as known follow-up.
2. `source_metadata` serializes datetime/date values via `.isoformat()` to keep JSONB-safe. Not in the spec but required for Postgres JSONB storage.

## Parallel-session note

Concurrent Claude Code sessions flipped HEAD to `fix/ios-push-foreground-handler` several times during Phase 1. Each task re-verified branch before writes and before commits. No rework needed; just adds a few seconds per task.
