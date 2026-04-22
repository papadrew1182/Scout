# Sprint 05 Phase 5 - AI-Driven Nudge Discovery - handoff

**Prepared:** 2026-04-22
**Branch:** `sprint/sprint-05-phase-5-ai-discovery`
**Base:** `main` post-PR #57 (Phase 4 merge `0ee597f`)
**Spec:** `SCOUT_SPRINT_05_PROACTIVE_NUDGES.md`
**Plan:** `docs/plans/2026-04-21-sprint-05-plan.md` Phase 5

## Summary

Phase 5 adds an hourly AI-driven discovery pass that proposes nudges from
a bounded family-state digest. The discovery service builds an allowlist-only
read-only projection of the family's structured state, calls
`orchestrator.propose_nudges_from_digest` (cache-prefixed Claude call),
converts each returned `DiscoveryProposal` into a `NudgeProposal` with
`trigger_kind='ai_suggested'`, and hands those proposals to the existing
P1/P2/P3 dispatch pipeline. Quiet hours, batching, dedupe, and the Phase 3
held-copy composer all apply for free. The service self-throttles to one AI
call per family per hour and respects the weekly AI soft cap. Ships no new
REST routes, no admin UI, no migration.

## What shipped (by commit)

- **`c682e00` - feat(ai): DiscoveryProposal schema + propose_nudges_from_digest (Task 1).**
  Adds `backend/app/schemas/nudge_discovery.py::DiscoveryProposal` pydantic model
  and `backend/app/ai/orchestrator.py::propose_nudges_from_digest`. The
  orchestrator strips code fences, parses JSON, validates each item, drops
  malformed proposals item-by-item, and caps results. Returns `[]` on
  ai_available=False, timeout, APIError, or empty post-validation. Test file
  `backend/tests/test_ai_discovery.py` (10 tests).

- **`c776f35` - feat(nudges): nudge_ai_discovery service with digest, rate limit, cap (Task 2).**
  Adds `backend/app/services/nudge_ai_discovery.py`. Functions: `build_family_state_digest`
  (allowlist-only projection over personal_tasks, events with attendees, task_instances,
  routines, family_members), `_is_throttled` / `_mark_discovery_ran` (module-level
  in-memory hourly rate limit), `propose_nudges` (full pipeline with weekly soft-cap
  check and DiscoveryProposal->NudgeProposal conversion). Test file
  `backend/tests/test_ai_discovery_service.py` with digest, throttle, and cap cases.

- **`ebe0279` - fix(nudges): hash body into dedupe_key for ai_suggested proposals (Task 3).**
  Updates `backend/app/services/nudges_service.py::resolve_occurrence_fields`:
  when `trigger_entity_id IS NULL` (as it is for all ai_suggested proposals),
  falls back from the literal `"null"` token to a `sha256(body)[:16]` fragment
  so two different AI proposals for the same member on the same day produce
  different dedupe keys. Adds targeted tests to `test_nudges.py`.

- **`dccc7e0` - feat(nudges): scheduler wiring for nudge_ai_discovery_tick (Task 4).**
  Adds `nudge_ai_discovery_tick` in `backend/app/services/nudge_ai_discovery.py`
  and wires it into `backend/app/scheduler.py` alongside the existing 5-minute
  scan. The tick iterates families, calls `propose_nudges` per family (self-
  throttled), converts to NudgeProposal, and hands to the existing
  apply_proactivity -> batch_proposals -> dispatch_with_items pipeline. Logs
  and continues on per-family exceptions; one bad family never poisons the tick.

- **`9c19d16` - fix(nudges): stamp occurrence_at_utc inside _convert_proposal (Task 4 follow-up).**
  Ensures `occurrence_at_utc` lives in `NudgeProposal.context` at the
  ai_discovery converter boundary rather than relying on downstream callers
  to stamp it. Simplifies `nudge_ai_discovery_tick` and adds
  `test_convert_proposal_stamps_occurrence_at_utc`.

- **`1a3c60f` - test(nudges): P1-P5 dedupe boundary regression (Task 5).**
  Adds a test class to `backend/tests/test_nudges.py` that pins the design
  choice: since `source_dedupe_key` includes `trigger_kind`, a P1 scanner
  proposal (`overdue_task`) and a P5 AI proposal (`ai_suggested`) about the
  same entity on the same day for the same member produce different keys
  and BOTH dispatch. Includes an end-to-end case seeding an overdue
  PersonalTask, running `scan_overdue_tasks` + a P5 proposal, flowing both
  through `apply_proactivity -> batch_proposals -> dispatch_with_items`,
  and asserting two `nudge_dispatch_items` rows (one per trigger_kind).
  If an upper layer later blocks cross-kind double-fires, this test fails
  and forces a deliberate design-change conversation.

## Test counts

- **39 new tests added in Phase 5** (10 in `test_ai_discovery.py` + 17 in
  `test_ai_discovery_service.py` + 12 added to `test_nudges.py`).
- **Pass/fail:** all new Phase 5 tests green locally. The single pre-existing
  flaky DST case (`TestScannerStampsOccurrence::test_overdue_task_scanner_stamps_due_at`)
  is unchanged from prior phases.

## No migration

Phase 5 ships NO migration per plan. The AI discovery path reuses:
- `nudge_dispatches` + `nudge_dispatch_items` from Phase 1.
- `quiet_hours_family` from Phase 2.
- Weekly AI soft-cap plumbing from Phase 3.
- No new columns, no new tables, no new indexes. `trigger_kind='ai_suggested'`
  is a new string literal but there is no CHECK constraint on that column, so
  no migration is required to accept it.

## Rate limit / cost cap

The per-family hourly rate limit is a module-level dict
(`_last_ai_discovery_run_utc: dict[UUID, datetime]` in
`nudge_ai_discovery.py`). Deliberate trade-offs:
- **No migration requirement** (plan constraint) rules out a DB-backed
  counter for Phase 5.
- **Restart loses state** - acceptable because the rate limit is a cost
  guardrail, not a correctness invariant. Worst case on a restart is one
  extra AI call per family in the hour of the restart.
- **Multi-worker drift** - if Railway scales to multiple workers, each
  worker holds its own dict. A family could be called up to N times per
  hour where N = worker count. Accepted: the weekly soft-cap still bounds
  total spend, and Phase 6 would add persistence if we need tighter SLOs.

The weekly soft-cap reuses the existing Phase 3 counter; `propose_nudges`
short-circuits and returns `[]` when the cap is hit.

## Dedupe boundary (by design)

`source_dedupe_key` is
`{family_member_id}:{trigger_kind}:{entity_part}:{local_date}`. Because
`trigger_kind` is part of the key, two proposals about the same
entity on the same day for the same member produce different keys when
they came from different sources:
- P1 scanners: `trigger_kind='overdue_task' | 'upcoming_event' | 'missed_routine'`.
- P5 AI discovery: `trigger_kind='ai_suggested'`.

Both dispatch. This is the intended behavior: a scanner-detected overdue
task and an AI observation about that same task may carry different
surface value (stock reminder vs. a coached suggestion). The P1-P5
regression test in commit `1a3c60f` locks this contract so a future
cross-kind dedupe layer cannot silently introduce drops.

For within-kind dedupe, Task 3's body-hash fix ensures two different AI
proposals on the same day DO dedupe per body (see
`test_p5_duplicate_same_day_dedupes`).

## Deferred / follow-up

1. **Empty-body nuance in dedupe key.** Task 3 uses `if body:` to decide
   between body-hash and context-hash dedupe fragments. An empty string
   (`body == ""`) is falsy and therefore falls through to the context hash
   path rather than hashing the empty body. Acceptable for v1 because the
   orchestrator drops empty-body proposals, but a stricter
   `if body is not None` would be slightly more defensive if the validator
   ever loosens.

2. **`_strip_tz` symmetry.** `build_family_state_digest` normalizes `now_utc`
   via `_strip_tz`, but `_is_throttled` / `_mark_discovery_ran` compare raw
   `now_utc` against the stored value. They happen to work today because
   callers consistently pass naive datetimes, but a mixed-awareness call
   site could raise `TypeError`. Low risk (all current callers are
   controlled), but a natural cleanup is to push `_strip_tz` into the
   throttle helpers for symmetry.

3. **Digest freshness under long ticks.** If a tick takes more than the
   5-minute scheduler interval (pathological), a second tick could start
   while the first is still running. The service-level throttle
   (`_is_throttled`) catches this for a given family but does not
   coordinate across ticks.

4. **Admin visibility.** No UI surface in Phase 5 to inspect or hand-rate
   AI-suggested nudges. `/settings/ai` Recent Nudges from Phase 3 shows
   delivered dispatches but does not label the trigger source.

## Deploy / verification

- **No migration to run.**
- `ANTHROPIC_API_KEY` and `SCOUT_AI_NUDGE_MODEL` env vars must be present
  on Railway for Phase 5 to actually fire. Both already exist from Phase 3,
  so no Railway action is needed. When absent, `propose_nudges_from_digest`
  returns `[]` and the tick logs + continues; the pipeline degrades
  silently to P1/P2/P3 behavior.
- Vercel: no frontend changes in Phase 5; the preview should be a no-op.
- smoke-web: `nudges-phase-5.spec.ts` runs a non-regression pass on
  `/api/nudges/me` + `/personal` console cleanliness. Skips cleanly when
  AI is disabled.

## On Andrew's plate

- [ ] Review the PR.
- [ ] Merge (squash).
- [ ] Verify Railway deploy green (no migration; the service picks up the
  new scheduler wiring on restart).
- [ ] Verify Vercel preview/production green (no frontend changes but the
  build should still pass).
- [ ] Pull main locally; delete the phase branch.

## Parallel-session note

Concurrent sessions during Phase 5 followed the same branch-verify-before-
write pattern as earlier phases. HEAD stayed on
`sprint/sprint-05-phase-5-ai-discovery` throughout.
