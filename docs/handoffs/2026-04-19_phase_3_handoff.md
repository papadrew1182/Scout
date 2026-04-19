# Phase 3 Handoff - Chore Ops Engine v2

**Branch:** `sprint/operability-phase-3-chore-ops`
**Date:** 2026-04-19

---

## Migrations added

- `041_chore_scope_contract.sql` - scope contract columns on chore_templates, dispute tracking on task_instances

## Permission keys added

None (uses existing `chore.complete_self`).

## Tables / columns added

| Table | Columns |
|-------|---------|
| `chore_templates` | included, not_included, done_means_done, supplies, photo_example_url, estimated_duration_minutes, consequence_on_miss |
| `task_instances` | in_scope_confirmed, scope_dispute_opened_at |

## Endpoints added

| Endpoint | Permission | Description |
|----------|-----------|-------------|
| `POST /task-instances/{id}/dispute-scope` | `chore.complete_self` | Opens scope dispute, creates parent_action_items row |

## Frontend files modified

| File | Change |
|------|--------|
| `scout-ui/app/(scout)/members/[id]/index.tsx` | Upgraded from placeholder to live child master card with today's progress, weekly rewards, chores list |

## Smoke tests added

| File | Count |
|------|-------|
| `smoke-tests/tests/chore-ops.spec.ts` | 3 tests |

## Known follow-ups

- Chore card inline expand with scope contract (included/not_included/done_means_done) - deferred to when scope contract data is populated
- Admin form for scope contract fields - extends Phase 2 chore template form
- Photo example upload UI - column exists, UI is later phase

## Narrative summary

Phase 3 added the chore scope contract schema (7 columns on
chore_templates, 2 on task_instances) and the dispute-scope endpoint.
The child master card was upgraded from a placeholder to a live screen
showing today's progress, weekly rewards summary, and chore lists.
The dispute endpoint writes to the existing parent_action_items table
with a new chore_scope_dispute action type.
