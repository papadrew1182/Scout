# Batch 1 PR 3 handoff — Seed data refresh

**Branch:** `batch-1/pr-3-seed-refresh`
**Base:** main at `159f91e` (PR 2 squash merge)
**Pulled from:** the 72-item backlog dump

## Summary

One seeding addition to `backend/seed_smoke.py` (Roberts zone pack).
The originally-scoped second item (base-cook staples) was pulled
during review. No schema change, no new routes, no new config keys.
CI smoke-web exercises the seed on every PR so any column or FK
mismatch fails CI before browser tests run.

## Scope change during review

PR 3 originally shipped two seed blocks: base-cook staples plus
Roberts zone pack. The base-cook staples block was pulled with
the review reasoning:

> Content belongs in the admin UI, not hardcoded in a seed script.
> The staples get added organically once admin screens ship, not
> via seed.

Zone pack stays. Zones are home infrastructure seed data — a
different category from user-facing content. A family's zone list
is roughly static once established; the seed is a reasonable
default-starter. Base-cook staples are taste-and-habit-specific
and should come from the meals admin surface, not from a shipped
default list.

The "Seed base-cook staples" backlog item is re-flagged with a
note linking it to the admin UI sweep. It closes once the meals
admin UI can accept staple content (create, edit, delete) with
the base-cook fields exposed in the Meal schema. Session task
#47 tracks this.

## Item shipped

### Roberts family zone pack

The 2026-04-19 Phase 4 handoff flagged "Roberts family zone pack
seeding (deferred — requires running seed_smoke.py)." No zone-pack
concept exists anywhere in code; it's handoff language for a
starter set of `scout.home_zones` rows. Chose 6 zones:

- Kitchen (room)
- Living Room (room)
- Master Bedroom (room)
- Hall Bathroom (room)
- Laundry Room (room)
- Outdoor (exterior)

Each has `sort_order` spacing of 10 so a future reorder-zone UI
can insert between them without shifting existing rows. Notes
strings give the family a starting vocabulary.

Idempotent: check for existing zone by `family_id` + `name`, skip
if present. Matches the query-first pattern the rest of
`seed_smoke.py` uses.

## Verification

- Syntax + import: `py -c "ast.parse..."` passes. HomeZone import
  resolves.
- Content count: 6 zones (awk + grep verified).
- Backend test sweep: 856 passed, 1 skipped.
- `node scripts/architecture-check.js`: 0 WARN, 1 INFO (same
  pre-existing seedData drift across PRs 1 + 2 + 3; not from
  this PR).
- End-to-end: CI smoke-web runs `seed_smoke.py` at step 3 of the
  workflow. Schema mismatch fails CI there.

## Not in scope

- Base-cook staples seed (see scope change above).
- Meal model placeholder issue (base-cook staples need `meal_date`
  + `meal_type` NOT NULL). Not this PR's problem now that staples
  are pulled.
- Maintenance templates bound to each zone. Zones stand alone;
  future PR can layer `MaintenanceTemplate` rows on `zone_id`.
- Production seeding. `seed_smoke.py` is a smoke-test fixture.
  Running it against prod adds the gummy bears + draft meal plan
  + pending purchase request that are smoke-test data, not real.

## Meta-notes for the batch

- Task #42 (seedData INFO drift watch): unchanged across 3 PRs.
  Pre-existing background noise confirmed. Task #45 tracks
  filing it as its own ticket after batch-1 wraps.
- Task #47 (new, this PR): re-flag "Seed base-cook staples" in
  the backlog. Closes when meals admin UI accepts staple content;
  do not revive the seed approach.

## On Andrew's plate

- Review PR 3 when opened
- Squash-merge
- Confirm Railway + Vercel deploys green post-merge
- Optional: run `python backend/seed_smoke.py` against your local
  dev DB to materialize the 6 zones. Not required; CI exercises
  the seed on every subsequent PR
- Once merged, PR 4 (Sprint 05 trust items: migration 046 rename
  plus flaky test root-cause-or-skip) starts
