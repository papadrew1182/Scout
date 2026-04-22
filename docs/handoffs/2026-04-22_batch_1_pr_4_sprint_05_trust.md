# Batch 1 PR 4 handoff — Sprint 05 trust items

**Branch:** `batch-1/pr-4-sprint-05-trust`
**Base:** main at `6b2ebbc` (PR 3 squash merge)
**Pulled from:** the 72-item backlog dump, Sprint 05 trust items

## Summary

Two items intended to break the "flag then forget" pattern. Migration
046_* filename collision renamed with a normalize migration to
handle the tracker flip on Railway; flaky test root-caused to a
wall-clock-dependent design and hardened to use fixed datetimes.
No schema change on the user-facing tables, no new routes, no new
config keys.

## Items shipped

### Item 1: Migration 046_* collision renamed

Two SQL files shipped with the same `046_` prefix on 2026-04-21:

- `046_push_notifications.sql` (PR #35, Sprint Expansion Phase 1, earliest)
- `046_ai_conversation_resume.sql` (PR #37, Sprint 04 Phase 1, later)

`migrate.py` tracks by full filename so runtime behavior was correct,
but the on-disk ambiguity was flagged in five handoffs as cosmetic
debt. Renamed to `046a_push_notifications.sql` and
`046b_ai_conversation_resume.sql` with `git mv` so history follows.

Both are mirrored in `backend/migrations/` and
`database/migrations/` (byte-identical pairs per repo convention).

Added `052_normalize_046_collision.sql` to handle the tracker flip:

- **On fresh databases** (local dev, CI test DB): the renamed files
  land as new entries in `_scout_migrations`, then 052 runs and its
  DELETE matches zero rows (old names never existed) and its INSERT
  hits `ON CONFLICT DO NOTHING` against the already-inserted new
  rows. Net no-op. Idempotent.
- **On legacy databases** (Railway production, which already had
  the old 046_* entries applied): the renamed files also land as
  new entries, 052 runs and DELETEs the old entries, INSERTs hit
  ON CONFLICT (rows exist from the rename files) and do nothing.
  End state: only the new names in the tracker.

Migration 052 also does `CREATE TABLE IF NOT EXISTS _scout_migrations`
at the top because the test conftest runs migrations directly
(bypassing `migrate.py`, which is where the tracker table normally
gets created). This keeps 052 self-contained.

Verified locally: `py backend/migrate.py` against the test DB
applies the full chain cleanly, and the simulated legacy-state
test (pre-populating old 046_* in the tracker, then running 052)
produces the correct end state with only new names.

### Item 2: Flaky `test_overdue_task_scanner_stamps_due_at`

The user's spec offered two paths: root-cause-and-fix, or
skip-with-linked-issue. Honest outcome: partial root-cause plus
structural fix.

**What the handoffs claimed:** "flaky DST boundary" across Sprint 05
phases 2-5.

**What I could actually reproduce:** nothing. Evidence is narrow, and
the evidence section below tells you exactly how narrow so you can
judge it for yourself:

- **Test runs, direct**: ran
  `pytest backend/tests/test_nudges.py::TestScannerStampsOccurrence::test_overdue_task_scanner_stamps_due_at`
  five times consecutively in a bash `for` loop. All five passed.
  Limitation: all five executed within the same ~5-second wall-clock
  window, so this only proves the test is not flaky at one point in
  time.
- **Database roundtrip probe**: wrote an inline Python script that
  inserted 96 synthetic naive datetimes (24 hours x 4 quarter-hour
  increments, all on 2026-04-22) via
  `SELECT CAST(:v AS timestamptz)` and checked whether the
  roundtripped `.date()` matched the original's `.date()` under the
  test DB's session TZ (`America/Chicago`). Zero mismatches. **This
  script did not execute the pytest itself.** It exercised only the
  Postgres TZ-reinterpretation step, not the full test fixture + ORM
  + scanner pipeline. If a flake were caused by something downstream
  of the naive-insert roundtrip (e.g. an ORM cache, a scanner code
  path triggered only with specific row state, a fixture interaction),
  this probe would not see it.
- **DST transition dates**: enumerated midnight UTC, 30 min past
  midnight UTC, CDT midnight, the 2026 spring-forward date
  (2026-03-08), and the 2026 fall-back date (2026-11-01) in pure
  Python and printed whether `due.date() == now.date()` at each.
  **Did not actually run the test at those wall-clock times.**
  Freezing the clock in-test would have been the right move; I did
  not do it because the scanner depends on `_utcnow()` indirectly
  and hooking that through a fixture was more scope than the trust
  PR should carry.
- **CI history, mechanical**: ran
  `gh run list --branch main --workflow "Scout CI" --limit 15`. All
  15 runs reported `conclusion: success`. That is the last 15 main
  runs only, covering roughly the Sprint 05 Phase 1 to PR #59 window.
  I did not scan earlier history or per-job conclusions that might
  be hiding under a `continue-on-error` flag.

The roundtrip logic traces cleanly: naive `due` inserted gets stored
as Chicago-local, roundtripped as aware Chicago-local, `.date()`
matches `due.date()` because both represent the same local wall-clock
instant. That inference holds under any session TZ I tried locally.
But the test was not run at the specific wall-clock boundaries the
handoffs implicated, so "I could not reproduce" is a statement about
my narrow evidence, not a proof that the bug was fictional.

**What the design problem actually is:** the three tests in
`TestScannerStampsOccurrence` all called `_utcnow()` at the top and
then asserted on `.date()` equality. Even though the assertion
passes under current conditions, the design is inherently
time-sensitive: any test that reads the wall clock and then
asserts against wall-clock-derived values has a non-zero probability
of failure at clock-crossing moments (midnight local, DST
transitions, leap-second adjustments, container-clock drift in CI).
It was a flake waiting for the right conditions.

**Framing: the fix is pre-emptive.** Given how narrow the evidence
is, the honest statement is not "the bug was never real" but
rather "I could not demonstrate the bug under the conditions I
tested, and the design would be fragile even if today's passing
state is genuine." Six months from now, if this test surfaces a
related failure, the first thing to check is whether the new
failure happens under a wall clock that my evidence did NOT cover:
- within the 00:00 to 06:00 UTC window on America/Chicago,
- on or near a DST transition date,
- against a Postgres with a session TZ other than America/Chicago,
- or in a fixture order that mine did not exercise.

The fix below removes the wall-clock sensitivity regardless of
whether the original complaint was a real flake or a chain of
handoff-reference misreads. If a future flake turns up a different
root cause, this handoff is the trail.

**What I shipped instead:**

1. Replaced `_utcnow()` with a fixed `_FIXED_NOW = datetime(2026, 4, 22, 15, 0, 0)` class constant. Midday UTC, safe from
   any clock-boundary reinterpretation.
2. Tightened the assertion from `.date() == due.date()` to full
   wall-clock equality after normalizing tz, with a diagnostic
   error message showing both values if it fails. A roundtrip
   bug can no longer hide behind a coincidentally-matching date.
3. Added a normalizer helper `_normalize_naive()` that strips
   tzinfo from aware datetimes so both sides compare consistently
   regardless of the DB session's TZ.
4. Extended the same hardening to the sibling tests
   `test_upcoming_event_scanner_stamps_starts_at` and
   `test_missed_routine_scanner_stamps_due_at` (they share the
   same design flaw).
5. Class docstring records the failure history, the root-cause
   finding, and the fix rationale so a future debugger has
   context.

**Why no GitHub issue filed:** the user's rule was "skip without
issue in same PR is not acceptable." I did not skip; I shipped a
fix. The handoff + commit message + class docstring are the
record. If a future engineer ever sees a related flake, they have
the investigation trail here, including the explicit list of
conditions my evidence did NOT cover.

## Verification

- `pytest backend/tests/test_nudges.py::TestScannerStampsOccurrence -xvs`:
  3 passed
- `pytest backend/tests/test_nudges.py`: 125 passed
- `pytest backend/tests/test_ai_conversation_resume.py
  backend/tests/test_push_notifications.py`: 37 passed, 1 skipped
  (migration 046a + 046b consumers)
- `pytest backend/tests/` (full sweep, excluding one unrelated
  test file): 961 passed, 1 skipped
- `node scripts/architecture-check.js`: 0 WARN, 1 INFO (same
  pre-existing seedData drift seen in PRs 1-3)
- `py backend/migrate.py` against test DB: applies 046a + 046b +
  052 cleanly on a fresh schema
- Simulated legacy-state flip: pre-populated old 046_* tracker
  rows, ran 052, verified end state has only new names

## Not in scope

- Broader audit of `_utcnow()` usage across test_nudges.py. 70
  usages total; only the 3 in `TestScannerStampsOccurrence` were
  specifically flagged as flaky. The rest stay as-is; if any
  future flake surfaces, apply the same pattern.
- Production tracker table migration. 052's DELETE/INSERT handles
  it automatically on the next Railway migrate.py pass after this
  PR merges.
- Moving `_scout_migrations` maintenance into a migration rather
  than migrate.py. Out of scope; migrate.py's approach is fine.

## On Andrew's plate

- Review PR 4 when opened
- Squash-merge
- Railway will auto-run migration 052 on deploy; confirm
  `/health` returns ok post-deploy and Vercel prod deploys green
- Check the Railway logs for the applied migration 052 line just
  to confirm the cleanup ran
- Once merged, PR 5 (CI + migration apply verification) starts

## Meta-notes for the batch

- Task #42 (seedData INFO drift watch): unchanged across 4 PRs
  now. Pre-existing background noise fully confirmed. Task #45
  tracks filing as its own ticket once batch-1 wraps.
- Task #48 (PR 4): complete on merge.
