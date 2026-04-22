# Batch 1 PR 1 handoff — Nudges hygiene

**Branch:** `batch-1/pr-1-nudges-hygiene`
**Base:** main (post-Phase-5 squash, `5145800` docs/atr tracker update)
**Pulled from:** the 72-item backlog dump, nudges domain, three XS items

## Summary

Three self-contained cleanups in the nudge engine. No schema change, no
new routes, no new config keys. Each change is defended by a test.

## Items shipped

### Item 1: Bundle mixed-kind action_type — document + test

Two places in `backend/app/services/nudges_service.py` write an Inbox
`action_type` from the first child's `trigger_kind` when a bundle
contains multiple children: `dispatch_with_items` line 941 (already
had a comment) and `process_pending_dispatches` line 1360 (did not).

Changes:
- Added a matching comment at the second site so both call sites
  explain the convention and point at the same reason.
- Added regression test
  `TestDispatchBundles::test_mixed_kind_bundle_uses_first_childs_kind_for_action_type`
  that builds a bundle with `overdue_task` + `missed_routine`
  children, dispatches it, and asserts `inbox.action_type ==
  "nudge.overdue_task"` plus both kinds survive on the children.

Formalizing a dedicated `nudge.mixed` action_type was considered and
rejected for this PR because it requires widening
`chk_parent_action_items_action_type` (last set in migration 050 to
5 specific `nudge.*` values). Tracked as a separate backlog item for
a future PR with a migration.

### Item 2: Empty-body dedupe hardening

`resolve_occurrence_fields` in `nudges_service.py` had
`if body:` which collapses empty-string with missing-body. Pydantic's
`DiscoveryProposal.min_length=1` blocks this on the normal path, but
a direct `NudgeProposal` caller could reach here with `body=""`.

Change: `if body:` becomes `if body is not None`. Empty-string now
hits the body-hash branch and produces `ai:<sha256('')[:16]>` —
stable across empty-body proposals regardless of other context keys.
Non-`body` context keys with no body still fall to the context-hash
branch as before.

Test: `TestAISuggestedDedupeKey::test_ai_suggested_empty_body_uses_body_hash_not_context`
constructs two proposals with `context={'body': '', 'variant': 'a'}`
and `{'body': '', 'variant': 'b'}` and asserts the dedupe_keys match,
proving the body-hash branch fires and collapses them.

### Item 3: _strip_tz symmetry in throttle helpers

`_is_throttled` and `_mark_discovery_ran` in
`backend/app/services/nudge_ai_discovery.py` did not normalize
`now_utc` with `_strip_tz`, unlike `build_family_state_digest`
which did. Current callers pass naive UTC so no bug today, but
a direct caller passing aware would TypeError on the
`(now_utc - last).total_seconds()` subtraction.

Change: both helpers now call `_strip_tz(now_utc)` at entry. The
marker stores naive. Mixed naive-plus-aware callers no longer
raise.

Test: `test_throttle_helpers_accept_tz_aware_datetimes` exercises
four combinations (aware-then-naive, aware-then-aware crossing the
window, naive-then-aware) and asserts the throttle state stays
correct without TypeError.

## Verification

Local test sweep:

```
py -m pytest backend/tests/test_nudges.py backend/tests/test_ai_discovery_service.py backend/tests/test_ai_discovery.py
==> 154 passed in 8.28s
```

`node scripts/architecture-check.js`:

```
Warnings: 0  |  Info: 1
All checks passed.
```

The 1 INFO is pre-existing seedData drift unrelated to this PR.

## Not in scope

These were considered but deliberately deferred:

- Formal `nudge.mixed` action_type. Requires migration 052.
- `_strip_tz` defense throughout the nudge engine (many more call
  sites exist). This PR covers the three specific helpers the
  backlog item flagged; broader audit is separate.
- Empty-body semantic question (should `body=""` collapse with
  `body=None`?). Current design treats them as distinct because
  the schema contract distinguishes "field absent" from
  "field present but empty." If product disagrees, revisit with
  an explicit spec.

## On Andrew's plate

- Review PR 1 when opened
- Squash-merge
- Confirm Railway + Vercel deploys green post-merge
- Once merged, PR 2 (AI chat polish) starts
