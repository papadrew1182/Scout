# Expansion Phase 3 Handoff — Family projects engine

**Branch:** `sprint/expansion-phase-3-family-projects`
**Date:** 2026-04-21
**Spec:** `SCOUT_EXPANSION_SPRINT_V2.md` §Phase 3
**Base commit:** `70bde59` (post-Phase-1, post-Sprint-2)

---

## Summary

First-class support for multi-week family projects — birthdays, trips,
holidays, home projects, weekend resets. Ships the engine only
(templates + tasks + milestones + budget); built-in template content
is deferred to Sprint 3B per spec.

## Coordination with parallel work

Another Claude Code session is working Sprint 04 Phase 1 on branch
`sprint/sprint-04-ai-conversation-resume`. That session owns migration
numbers **045** (drift sync) and **046** (Sprint 04 P1 — wait, my
Phase 1 already used 046 for push — conflict check). Phase 3 uses
**047** to stay clear.

Known minor conflict surfaces flagged in the user prompt:

- `scout-ui/app/settings/index.tsx` — both sessions edit
- `docs/atr tasks/open_items.md` — the tracker file

These will merge cleanly or get small-conflict resolution at merge.

## Migrations added

- `047_family_projects.sql` (mirrored to `database/migrations/`)
  - Six new tables under `scout.*`:
    - `project_templates`
    - `project_template_tasks`
    - `projects`
    - `project_tasks`
    - `project_milestones`
    - `project_budget_entries`
  - Additive FK on `public.personal_tasks.source_project_task_id`
    → `scout.project_tasks(id) ON DELETE SET NULL`, with a unique
    partial index so a given project task is promoted at most once.
  - Seven permission keys (see below).

### Tier-name note (important)

Migration 024 seeded lowercase tier names (`admin / parent_peer / teen /
child / kid`). **Migration 034 deleted all five** and re-pointed every
override at the UPPERCASE canonical names
(`PRIMARY_PARENT / PARENT / TEEN / CHILD / YOUNG_CHILD / DISPLAY_ONLY`)
seeded originally in migration 022. The Phase 3 prompt's F2 rule said
"verify in migration 024" but the current DB state uses UPPERCASE —
matching my Phase 1 (PR #35) migration. Migration 047 uses UPPERCASE
names in the seed JOINs; this is what works in the live DB. Recommend
updating the unblock checklist's §F2 to reflect post-034 state.

## Permission keys added

- `projects.create` → `PRIMARY_PARENT`, `PARENT`, `TEEN`
- `projects.manage_own` → all tiers except `DISPLAY_ONLY`
- `projects.manage_any` → `PRIMARY_PARENT`, `PARENT`
- `projects.view` → all tiers except `DISPLAY_ONLY`
- `project_tasks.update_assigned` → all tiers except `DISPLAY_ONLY`
- `project_templates.manage` → `PRIMARY_PARENT`, `PARENT`
- `project_templates.view` → all tiers except `DISPLAY_ONLY`

`update_task` route uses `require_permission("project_tasks.update_assigned")`
as the floor gate (every non-DISPLAY tier holds it); in-body branching
then enforces the narrow `{status, notes}`-only field set when the
actor is only the assignee. Editors outside that narrow set must also
hold `projects.manage_own` (owner) or `projects.manage_any` (admin).

## Backend added

- `backend/app/models/projects.py` — six SQLAlchemy models.
- `backend/app/models/personal_tasks.py` — adds `source_project_task_id`
  column and FK to `scout.project_tasks`.
- `backend/app/services/project_service.py` —
  `create_template`, `add_template_task`, `create_blank`,
  `create_from_template` (copies every template task with
  due_date = start + relative_day_offset), `instantiate_template_tasks`,
  `add_task`, `complete_task`, `add_milestone`, `complete_milestone`,
  `add_budget_entry`, `promote_project_task_to_personal_task`
  (idempotent via unique index).
- `backend/app/services/project_aggregation.py` —
  `list_active_projects`, `list_active_projects_for_family_member`
  (owned OR task-assigned), `project_health_summary`,
  `list_due_project_tasks_for_today`.
- `backend/app/routes/projects.py` — ten endpoints under
  `/api/projects/*`, all mutations gated by `require_permission` at
  the top + a helper for scope (owner vs manage_any).
- `backend/app/routes/project_templates.py` — family-local template
  CRUD plus `/tasks` nested route.
- `backend/app/ai/tools.py` — two new confirmation-required tools
  (`create_project_from_template`, `add_project_task`); registered in
  `TOOL_FUNCTIONS`, `TOOL_DEFINITIONS`, and added to adult
  `write_tools_adult` in `app/ai/context.py`.
- `backend/app/ai/tools.py:_get_today_context` now includes
  `project_tasks_today` derived from
  `project_aggregation.list_due_project_tasks_for_today`.
- `backend/app/main.py` — includes `projects.router` and
  `project_templates.router`.

## Frontend added

- `scout-ui/lib/projects.ts` — API wrappers and hooks
  (`useProjects`, `useProject`, `useProjectHealth`,
  `useMyProjectTasksToday`, `useProjectTemplates`).
- `scout-ui/app/projects/index.tsx` — active projects list.
- `scout-ui/app/projects/[id].tsx` — tabs Tasks / Milestones /
  Budget / Info with inline create forms on each write tab.
- `scout-ui/app/projects/new.tsx` — create form with template chip
  row (Blank + per-template) and seven-category chip row.
- `scout-ui/app/admin/projects/index.tsx` — admin tabs
  "All projects", "Family templates", "Health" (placeholder summary).
- `scout-ui/app/admin/index.tsx` — adds a Projects admin card gated
  by `projects.manage_any`.
- `scout-ui/features/projects/ProjectsTodayCard.tsx` — renders project
  tasks due today for the current actor; imported into
  `scout-ui/features/today/TodayHome.tsx` between the Affirmation card
  and the filter chips.

Deliberately did **not** touch `scout-ui/app/settings/index.tsx` beyond
what Phase 1 already added (Notifications row). The parallel Sprint 04
session may edit this file; the merge should be trivial.

## Tests added

- `backend/tests/test_family_projects.py` — 7 tests:
  - template instantiation with five tasks (due-date math)
  - child tier 403 on `POST /api/projects`
  - kid-tier assignee can update `status` on own task; 403 on
    `owner_family_member_id` change via the same endpoint
  - Today endpoint returns due project tasks without any promotion
  - promote twice — idempotent via `source_project_task_id` unique
  - AI tool registry contains both new names
  - health summary completion-percent math

Smoke: `smoke-tests/tests/projects.spec.ts` — list page renders,
blank-project create → task add → mark complete → health updates,
`/admin/projects` loads for admins.

## Test counts

| Suite | Before | After | Delta |
|---|---|---|---|
| Backend pytest | 737 | 744 | +7 |
| AI tool registry | n | n + 2 | +2 |
| Smoke specs | (unchanged) | +1 file | +1 |

## Arch-check

- Baseline on main @ `70bde59`: 41 WARN, 1 INFO.
- After Phase 3 code (initial): 47 WARN (6 net new from
  `routes/projects.py` — my `_authorize_project_mutation` helper's
  permission check was invisible to the static scan).
- After fix (explicit `actor.require_permission` calls at each
  mutation endpoint top, keyed to `projects.manage_own` or
  `project_tasks.update_assigned` as the floor): **41 WARN, 1 INFO**
  — baseline preserved.

## Scheduler / workers

No new scheduled work in Phase 3. Existing APScheduler tick is
untouched.

## Not included (per spec §Out of scope)

- Built-in project template content (Sprint 3B).
- Grocery impact automation.
- YNAB integration.
- Gantt view, dependency graph.
- Recurring projects.
- Cross-family projects.

## Out-of-scope debt still present

- `database/migrations/045_ai_message_metadata.sql` has no
  `backend/migrations/` twin — pre-existing drift from PR #25. The
  parallel Sprint 04 session is slated to own the fix via migration
  045's drift sync. Leave alone here.

## HALT per user instruction

PR opened, not merged. Andrew's review + merge, then Railway migration
run, then Vercel verification.
