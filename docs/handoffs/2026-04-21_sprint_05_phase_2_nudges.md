# Sprint 05 Phase 2 - Quiet Hours + Batching + Recent Nudges - handoff

**Prepared:** 2026-04-21
**Branch:** `sprint/sprint-05-phase-2-quiet-hours-batching`
**Base:** `main` post-PR #53 (Phase 1 merge `44c43c0`)
**Spec:** `SCOUT_SPRINT_05_PROACTIVE_NUDGES.md`
**Plan:** `docs/plans/2026-04-21-sprint-05-plan.md` §7 Phase 2

## What shipped

### Schema
- Migration 050:
  - `scout.quiet_hours_family` (UNIQUE family_id; CHECK 0 <= minute < 1440; CHECK start != end; trigger on updated_at).
  - Permission `quiet_hours.manage` granted to PARENT + PRIMARY_PARENT.
  - Widens `chk_parent_action_items_action_type` to include the five `nudge.*` types (preserving all 10 original values from migration 020).

### Models
- `backend/app/models/quiet_hours.py` `QuietHoursFamily`.

### Service (`nudges_service.py`)
- `should_suppress_for_quiet_hours(db, member_id, severity, now_utc)` -> `(decision, hold_until_utc)`. Three decisions: deliver / drop / hold. Per-member override in `member_config['nudges.quiet_hours']` wins over family default. Midnight-wrapping window supported.
- `resolve_deliver_after(db, proposal, now_utc)` -> `(deliver_after_utc, suppressed_reason)`. Never mutates occurrence_at_utc or occurrence_local_date.
- `ProposalBundle` dataclass + `batch_proposals(proposals, window_minutes=10)`. Anchor-based clustering (not nearest-neighbour drift). One-proposal-bundles pass through unchanged.
- `dispatch_with_items` refactored to accept `list[ProposalBundle]`. Three paths:
  - **deliver**: status='delivered', Inbox + push.
  - **hold**: status='pending', `deliver_after_utc` = window end. No Inbox yet, no push yet. Child rows still written to claim the dedupe key.
  - **drop**: status='suppressed', `suppressed_reason='quiet_hours'`. Child rows still written for audit + dedupe.
- `action_type` now `f"nudge.{first_kind}"` (Phase 1's `"general"` workaround removed).
- `run_nudge_scan` now chains scan -> apply_proactivity -> batch_proposals -> dispatch_with_items.

### Routes
- `GET /api/nudges/me` (auth, `nudges.view_own`) - caller's last 20 dispatches with items. Eager-loaded via `selectinload` (no N+1).
- `GET /api/admin/family-config/quiet-hours` (`quiet_hours.manage`) - family window or default.
- `PUT /api/admin/family-config/quiet-hours` (`quiet_hours.manage`) - upsert.

### Frontend
- `scout-ui/lib/nudges.ts` - plain fetch helpers.
- `/settings/ai` - Recent nudges card (last 20 dispatches, shows delivered / held / suppressed status).
- `/admin/ai/nudges` - quiet-hours editor (HH:MM inputs, save button).
- `/admin` index - Nudges nav row, gated by `quiet_hours.manage`.

### Tests
- `backend/tests/test_nudges.py`: ~66 pass (prior 33 + 9 quiet-hours + 8 batching + 5 bundles + 1 cross-midnight + 5 nudges/me + 6 admin quiet-hours).
- `smoke-tests/tests/nudges-phase-2.spec.ts`: new Phase 2 smoke spec.
- Full regression suite: 792 pass, 1 pre-existing failure unrelated to this sprint.

## What this phase does NOT do

- **Held-dispatch delivery worker.** A held dispatch (status='pending') currently sits in the table until manually consumed. Phase 2 records the intent (deliver_after_utc, dedupe claimed) but does not yet have a background job to surface held nudges when the quiet window ends. Options for Phase 3 (or a 2.5 follow-up): a `process_pending_dispatches(db, now_utc)` that finds pending rows whose `deliver_after_utc <= now_utc` and writes the Inbox row + push. This is the most important follow-up.
- **Route-hint deep linking.** `/settings/ai` Recent nudges shows status + body but doesn't yet tap through to the source entity. Next phase will use `items[0].trigger_entity_id` + kind to deep-link.
- **Bundle mixed-kind action_type.** If a bundle mixes trigger kinds, the Inbox row uses the first kind as its action_type. Documented inline. Harmonic bundles are rare at v1 volumes.
- **Per-member quiet-hours admin UI.** Only family-wide control ships; per-member overrides live in `member_config` and are editable via direct writes.
- **Push scheduling respect.** A delivered dispatch still sends push immediately even if `deliver_after_utc` is in the future. Moot for today (hold path skips push entirely) but worth remembering when building the held-dispatch worker.

## Known follow-ups (in priority order)

1. **Held-dispatch delivery worker** (above). Without it, held nudges never actually surface to the user. Phase 3 or a standalone 2.5 follow-up.
2. **`TestScannerStampsOccurrence::test_overdue_task_scanner_stamps_due_at` pre-existing failure on main.** Wall-clock midnight edge case introduced before this phase. Not caused by Phase 2. Investigate separately.

## Arch check

Run `node scripts/architecture-check.js`. Record before/after counts below; Phase 2 should add zero new WARNs.

- Before (main post-PR #53): 0 WARN, 1 INFO (seedData drift - pre-existing).
- After this branch: 0 WARN, 1 INFO (seedData drift - pre-existing).
- Delta: 0.

## On Andrew's plate

- [ ] Review the PR (URL after `gh pr create`).
- [ ] Merge (squash).
- [ ] Apply migration 050 on Railway via the public proxy URL pattern.
- [ ] Verify Railway backend `/health` post-deploy.
- [ ] Verify Vercel frontend deploy green.
- [ ] Pull `main` locally; delete the phase branch.

## Parallel-session note

Concurrent Claude Code sessions kept drifting HEAD to `fix/ios-push-foreground-handler` during Phase 2, same as Phase 1. Every subagent re-verified branch before each write and before each commit. No rework needed.
