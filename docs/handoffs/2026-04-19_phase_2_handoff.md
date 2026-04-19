# Phase 2 Handoff - Manual Data Entry Restoration

**Branch:** `sprint/operability-phase-2-data-entry`
**Date:** 2026-04-19

---

## Migrations added

- `040_phase2_permissions.sql` - New permission keys: tasks.manage_self, calendar.manage_self, meals.manage_staples

## Permission keys added

| Key | Tiers |
|-----|-------|
| `tasks.manage_self` | YOUNG_CHILD, CHILD, TEEN, PARENT, PRIMARY_PARENT |
| `calendar.manage_self` | TEEN, PARENT, PRIMARY_PARENT |
| `meals.manage_staples` | PARENT, PRIMARY_PARENT |

## Tables / columns added

None.

## Endpoints modified (permission-gated)

| Route file | Endpoints gated | Permission key |
|-----------|----------------|----------------|
| `personal_tasks.py` | POST, PATCH, POST complete, DELETE (4) | `tasks.manage_self` |
| `chores.py` | POST create template (1) | `chores.manage_config` |
| `calendar.py` | POST, PATCH, DELETE event + POST instance + POST/PATCH/DELETE attendee (7) | `calendar.manage_self` |
| `meals.py` | POST/PATCH/DELETE meal-plans (3), POST generate + POST regenerate (2), POST approve (1), PATCH/POST archive weekly (2), POST/DELETE meals (2), POST review (1), POST/DELETE dietary-preferences (2) | `meals.manage_staples`, `meal_plan.generate`, `meal_plan.approve`, `meal.review_self` |

## Frontend files added

| File | Purpose |
|------|---------|
| `scout-ui/features/today/AddTaskSheet.tsx` | Inline personal task creation sheet |
| `scout-ui/features/calendar/AddEventSheet.tsx` | Inline calendar event creation sheet |
| `scout-ui/app/admin/chores/new.tsx` | Admin chore template create form |
| `scout-ui/app/admin/meals/staples/new.tsx` | Admin meal staple create form |
| `smoke-tests/tests/data-entry.spec.ts` | Playwright tests for all data entry flows |

## Frontend files modified

| File | Change |
|------|--------|
| `scout-ui/lib/api.ts` | Added createPersonalTask, createEvent, createChoreTemplate |
| `scout-ui/features/today/TodayHome.tsx` | Added "Add task" button and AddTaskSheet |
| `scout-ui/features/calendar/CalendarPreview.tsx` | Added "Add event" button and AddEventSheet |

## Arch-check delta

| Check | Before (Phase 1 end) | After |
|-------|---------------------|-------|
| Check 1: Backend missing permission | 65 WARN | 39 WARN (-26) |
| Check 5: Dead tap-target | 0 WARN | 0 WARN |

## Known follow-ups

- Grocery routes still need permission gates (8 endpoints) - not in Phase 2 scope per sprint spec
- Grocery UI polish (keyboard handling, "add another" flow) deferred
- Admin chore form does not yet include Phase 3 scope-contract fields
- Meal staple form uses the existing meals POST endpoint; dedicated staple model is Phase 5

## Narrative summary

Phase 2 restored manual data entry across four domains. Three new
permission keys were introduced via migration 040 and 26 backend
mutation endpoints were gated with require_permission calls, reducing
the architecture check WARN count from 65 to 39. Frontend forms were
added for personal tasks (inline sheet on /today), calendar events
(inline sheet on /calendar), chore templates (admin form at
/admin/chores/new), and meal staples (admin form at /admin/meals/
staples/new). All forms use useHasPermission for submit gating. Six
Playwright smoke tests cover happy paths and permission-denial cases.
