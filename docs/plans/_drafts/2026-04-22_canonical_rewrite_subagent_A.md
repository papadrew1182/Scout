# Slice A plan - Chores, Tasks, Routines canonical rewrite

Author: sub-agent A (planning only, no code or schema changes)
Date: 2026-04-22
Scope: Slice A of the scout canonical rewrite. Covers task_templates, task_assignment_rules, task_occurrences, task_completions, task_notes, task_exceptions, routine_templates, and the still-live legacy tables chore_templates, routines, routine_steps, task_instances, task_instance_step_completions, personal_tasks, daily_wins, plus scout.v_household_today.

Status of base audit: `docs/plans/2026-04-22_schema_canonical_audit.md` (2026-04-22).
Architecture references: `docs/architecture/ARCHITECTURE.md`, `docs/architecture/interaction_contract.md`, migration `backend/migrations/022_session2_canonical.sql`.

---

## Section 1. Slice inventory

Legend: "row counts" reproduce the audit. File refs are absolute-style (repo-root relative). Every code ref below was verified via Grep, not inferred from naming.

### 1.1 Canonical scout.* tables

| Table | Rows | Plain English |
|-------|------|---------------|
| `scout.task_templates` | 7 | Definition of a standalone chore or task (name, recurrence, due time, notes). Scope-contract fields are NOT yet present here - they still live in `public.chore_templates`. |
| `scout.task_assignment_rules` | 7 | One or more rules per template describing who owns the occurrence on a given date (fixed, day_parity, week_rotation, dog_walk_assistant, custom). |
| `scout.task_occurrences` | - | Concrete materialization of a template or routine for a single date. Written by the canonical generator, read by `v_household_today`. |
| `scout.task_completions` | - | Per-occurrence completion events (manual, auto, parent_override, ai_recorded). |
| `scout.task_notes` | - | Free-text notes attached to an occurrence. |
| `scout.task_exceptions` | - | Reasons an occurrence was skipped or blocked. |
| `scout.routine_templates` | 25 | Morning / after-school / evening routine definitions per kid. Replaces `public.routines`. |
| `scout.v_household_today` | n/a | Curated view joining occurrences + templates + routines + family_members. CRITICAL: missing chore scope-contract join (see §10). |

Canonical table definitions: `backend/migrations/022_session2_canonical.sql:277-394`.

Canonical routes (only route that writes scout.task_*): `backend/app/routes/canonical.py:235-464`
- `GET /api/household/today` reads `scout.v_household_today` (line 257-280).
- `POST /api/household/completions` writes `scout.task_completions` + updates `scout.task_occurrences.status` (lines 400-428).
- Occurrence generation triggered on every read of `/api/household/today` via `generate_task_occurrences_for_date` (lines 249-255).

Canonical admin routes: `backend/app/routes/admin/chores.py:98-196`
- `GET /admin/chores/routines` / `PUT /admin/chores/routines/{member_id}` / `DELETE /admin/chores/routines/{routine_id}` - all operate on `scout.routine_templates` via `chores_canonical.py`.

Canonical services:
- `backend/app/services/canonical_household_service.py` - occurrence generation, rule evaluation, Daily Win recompute. Reads `scout.routine_templates`, `scout.task_templates`, `scout.task_assignment_rules`; writes `scout.task_occurrences`, `scout.task_completions`, `scout.daily_win_results` (lines 198-475).
- `backend/app/services/chores_canonical.py` - ORM CRUD over `scout.routine_templates` via `app.models.canonical.RoutineTemplate` (whole file).

Canonical ORM models: `backend/app/models/canonical.py:19-49` (only `RoutineTemplate` exposed; `task_templates`, `task_assignment_rules`, `task_occurrences`, `task_completions`, `task_notes`, `task_exceptions` currently have NO ORM model - routes use raw `text()` SQL).

Canonical tests:
- `backend/tests/test_canonical_session2.py:154,196` - scout table presence + view presence.
- `backend/tests/test_canonical_session2.py:439-539` - envelope shape tests including `/api/household/today`.
- `backend/tests/test_canonical_session2_block2.py:325-513` - generation + daily-win recompute against scout.* tables.
- `backend/tests/test_r3_migrations.py` - migration 036 (routines to canonical) coverage.

Seed: `backend/migrations/023_session2_roberts_seed.sql` inserts 25 routine_templates, 7 task_templates, 7 task_assignment_rules for the Roberts family.

### 1.2 Legacy public.* tables (still active)

| Table | Rows | Plain English |
|-------|------|---------------|
| `public.chore_templates` | live | Original chore definition. Holds the scope-contract fields (`included`, `not_included`, `done_means_done`, `supplies`, `photo_example_url`, `estimated_duration_minutes`, `consequence_on_miss`) added by migration 041. |
| `public.routines` | live | Per-member block routine (morning / after_school / evening). Parallel with `scout.routine_templates`. |
| `public.routine_steps` | live | Ordered checklist steps within a routine. No canonical equivalent yet. |
| `public.task_instances` | live | Concrete execution row per kid per day from routine or chore. Parallel with `scout.task_occurrences`. Also carries `in_scope_confirmed` + `scope_dispute_opened_at` from migration 041. |
| `public.task_instance_step_completions` | live | Per-step completion for routine-sourced task_instances only. |
| `public.daily_wins` | live | Materialized Mon-Fri win rollup. Parallel with `scout.daily_win_results`. |
| `public.personal_tasks` | 0 | Adult / general-purpose one-off tasks. Legacy, no live data, still has routes. |

Legacy routes:
- `backend/app/routes/chores.py` - whole file uses `public.chore_templates` via ORM.
- `backend/app/routes/routines.py` - whole file uses `public.routines` + `public.routine_steps`.
- `backend/app/routes/task_instances.py` - uses `public.task_instances`; `/dispute-scope` uses scope-contract field `scope_dispute_opened_at` and writes a `ParentActionItem`.
- `backend/app/routes/daily_wins.py` - uses `public.daily_wins`.
- `backend/app/routes/personal_tasks.py` - uses `public.personal_tasks`.

Legacy services:
- `backend/app/services/chore_service.py:12-74` - CRUD + `resolve_assignees` over ChoreTemplate ORM; reads `included`, `not_included`, `done_means_done`, etc. (lines 43-49).
- `backend/app/services/routine_service.py` - CRUD over Routine + RoutineStep.
- `backend/app/services/task_generation_service.py:55-158` - the *legacy* generator. Reads `public.routines` + `public.chore_templates`, writes `public.task_instances` + `public.task_instance_step_completions`. No scout writes at all.
- `backend/app/services/task_instance_service.py:1-58` - mark_completed / override / step completion on `public.task_instances`.
- `backend/app/services/daily_win_service.py:1-98` - reads `public.task_instances`, writes `public.daily_wins`. Parallel with `recompute_daily_win` in `canonical_household_service.py`.
- `backend/app/services/personal_tasks_service.py` - reads/writes `public.personal_tasks`.

Legacy ORM models: `backend/app/models/life_management.py:11-139` (Routine, RoutineStep, ChoreTemplate, TaskInstance, TaskInstanceStepCompletion, DailyWin), plus `backend/app/models/personal_tasks.py:11-30` (PersonalTask).

Legacy schemas: `backend/app/schemas/life_management.py:1-221`.

Nudge surface that indexes the legacy tables:
- `backend/app/services/nudge_rule_validator.py:58-70` - SQL allowlist includes `personal_tasks`, `events`, `event_attendees`, `task_instances`, `routines`, `chore_templates`, `family_members`, `families`, `bills`. No scout.* entries.
- `backend/app/services/nudge_ai_discovery.py:5-290` - scanner aggregates over `personal_tasks`, `task_instances`, `routines` via raw SQL.
- `backend/app/services/nudges_service.py:104-218` - `scan_overdue_tasks` queries `personal_tasks`; `scan_missed_routines` queries `task_instances` joined with `routines`.

AI tool surface: `backend/app/ai/tools.py:203,234,274-287,1159,1247` - `list_chores_or_routines` reads legacy chore_templates + routines + task_instances; `list_personal_tasks`, `create_personal_task`, `update_personal_task`, `complete_personal_task` all use the legacy PersonalTask service.

Dashboard: `backend/app/services/dashboard_service.py:203` - reads today's chores/routines from `public.task_instances`.

Frontend refs (sampled):
- `scout-ui/lib/api.ts:161,171` - `/families/{id}/routines` and `/families/{id}/routines/{routine_id}/steps` hit the legacy router.
- `scout-ui/lib/api.ts:1160-1176` - admin `/admin/chores/routines` routes (canonical).
- `scout-ui/lib/types.ts:26` - `chore_template_id: string | null` on a task-instance shape.
- `scout-ui/app/admin/chores/new.tsx` + `scout-ui/app/admin/chores/index.tsx` - admin chore-template UI; reads scope-contract fields and the canonical routines surface.

Tests touching the legacy surface:
- `backend/tests/test_task_generation.py:21-151` - full coverage of legacy `task_generation_service`.
- `backend/tests/test_daily_wins.py:56-124` - legacy DailyWin path.
- `backend/tests/test_chore_templates.py:27-140` - scope-contract field persistence on `public.chore_templates`.
- `backend/tests/test_personal_tasks.py:43-260` - legacy personal_tasks path.
- `backend/tests/test_tenant_isolation.py` - includes task_instances tenant checks.
- `backend/tests/test_tier2.py`, `test_tier4.py`, `test_tier5.py` - rely on task_instances / personal_tasks fixtures.

### 1.3 Mirror migrations

Every migration in `backend/migrations/` has a counterpart in `database/migrations/`. Verified 001, 002, 006, 022, 023, 036, 041 are mirrored. The sprint plan must treat `backend/` as canonical and re-mirror on every SQL change (see audit §1).

---

## Section 2. Per-table recommended action

Column headings: Action options are CONSOLIDATE (legacy to scout.*), KEEP+BRIDGE (legacy stays, shim view in scout), DEPRECATE (drop after data move), LEAVE (no change in this slice).

| Table | Action | Justification (grounded in §1 evidence) |
|-------|--------|---|
| `scout.task_templates` | EXPAND (add scope-contract cols) | Audit §6 flags missing scope fields as HIGH severity. `chore_service.py:43-49` already reads them from `public.chore_templates`; canonical reads at `canonical.py:349-359` do not. Adding the columns here is the cheapest path to closing the `v_household_today` gap. |
| `scout.task_assignment_rules` | LEAVE | Canonical-only. Already exercised by `resolve_assignment` (`canonical_household_service.py:58-109`) and tested in `test_canonical_session2_block2.py:253-325`. No legacy parallel. |
| `scout.task_occurrences` | LEAVE (for this slice; write-path expansion is covered in §4) | Canonical-only. Already read by `v_household_today` and written by canonical generator. Legacy `public.task_instances` needs migration into it - see §4. |
| `scout.task_completions` | LEAVE | Canonical-only. Written by `canonical.py:400-428`. |
| `scout.task_notes` | LEAVE | Canonical-only. No live reader / writer at present; keep as-is, wire up when feature ships. |
| `scout.task_exceptions` | LEAVE | Canonical-only, same status as task_notes. |
| `scout.routine_templates` | LEAVE (+expand to own routine_steps replacement) | Already the target of migration 036 and the `/admin/chores/routines` surface. Needs the addition of a canonical `scout.routine_steps` to fully replace `public.routine_steps`; migration 022 created `scout.routine_steps` but it is UNCLEAR-listed in the audit. |
| `public.chore_templates` | CONSOLIDATE into scout.task_templates | Audit §5 recommends this with effort=M. Scope-contract fields must land on `scout.task_templates` (see §3). Data volume is "live" but the 7 rows listed in scout.task_templates suggest most new writes already happen canonically; chore_templates needs a migration path + keep-alive view. |
| `public.routines` | CONSOLIDATE into scout.routine_templates | Parallel tables are a naming-collision risk called out in audit §6. `routine_service.py` still reads the legacy table; `/admin/chores/routines` reads the canonical one. Users on the routine admin page see only canonical; the legacy read-path is now a source of drift. |
| `public.routine_steps` | CONSOLIDATE into scout.routine_steps | scout.routine_steps exists (`022_session2_canonical.sql:294-304`) but has NO ORM / routes / tests. Needs schema verification (UNCLEAR status per audit), then data move + shim view. |
| `public.task_instances` | CONSOLIDATE into scout.task_occurrences | Hot legacy path. Every legacy write (`task_generation_service.py`, `task_instance_service.py`, dashboard, nudges) targets this. Audit §5 suggested "KEEP + FORMALIZE BRIDGE" at effort S; I recommend revisiting: the parallel write path is the single largest drift risk. Formal bridge only (no consolidation) leaves the naming collision and the dispute-tracking fields (`in_scope_confirmed`, `scope_dispute_opened_at`) stranded on the legacy table. |
| `public.task_instance_step_completions` | CONSOLIDATE into a new scout.task_occurrence_step_completions | No canonical analogue exists today. Needed to preserve routine-step completion tracking when the legacy generator retires. This is not in the audit's current table list and needs to be added. |
| `public.personal_tasks` | DEPRECATE or CONSOLIDATE (0 live rows) | Audit §3 marks 0 rows but the route surface + AI tool integration + nudge scanner all exist (`tools.py:234-268`, `nudges_service.py:104-126`). If the table is truly unused by humans, deprecation is safe; if the AI path is actively inserting, those writes are happening to an empty table in prod, so the integration needs a home. My recommendation: CONSOLIDATE into a new `scout.personal_tasks` shape rather than silently drop. Revisit the audit's DEPRECATE suggestion. |
| `public.daily_wins` | CONSOLIDATE into scout.daily_win_results | Canonical `scout.daily_win_results` is already in migration 022 and written by `canonical_household_service.recompute_daily_win`. Two parallel writers (`daily_win_service.py` vs `canonical_household_service.py`) is a bug waiting to happen; pick one. |
| `scout.v_household_today` | UPDATE (bridge gap fix) | Must add a join onto the scope-contract columns once they land on `scout.task_templates` (see §3). |

Flags where I recommend revisiting the audit:
1. `public.task_instances` - audit says KEEP+BRIDGE at S effort; I recommend CONSOLIDATE at M because of dispute-field drift.
2. `public.personal_tasks` - audit silent on action; recommend CONSOLIDATE into scout.*, not DEPRECATE, because AI tools write to it.
3. `public.task_instance_step_completions` - audit doesn't list this one; needs a canonical home.

---

## Section 3. Proposed canonical target shape

Only CONSOLIDATE tables are described. LEAVE tables use the existing shape from `022_session2_canonical.sql:277-394`.

### 3.1 `scout.task_templates` (expanded)

```
id                         uuid PK
family_id                  uuid NOT NULL REFERENCES public.families(id)
template_key               text NOT NULL
label                      text NOT NULL
description                text                  -- NEW, from chore_templates.description
recurrence                 text NOT NULL CHECK IN (daily, weekdays, weekends, weekly, one_off)
due_time                   time                  -- existing
standard_of_done_id        uuid REFERENCES scout.standards_of_done(id)
notes                      text
is_active                  boolean NOT NULL DEFAULT true

-- Scope-contract block (NEW - closes the v_household_today gap)
included                   jsonb NOT NULL DEFAULT '[]'
not_included               jsonb NOT NULL DEFAULT '[]'
done_means_done            text
supplies                   jsonb NOT NULL DEFAULT '[]'
photo_example_path         text                  -- renamed from photo_example_url (it's a Storage path)
estimated_duration_minutes integer
consequence_on_miss        text

created_at                 timestamptz NOT NULL DEFAULT clock_timestamp()
updated_at                 timestamptz NOT NULL DEFAULT clock_timestamp()

UNIQUE (family_id, template_key)
```

Index additions: existing `uq_task_template` is sufficient. Add `idx_task_templates_family_active (family_id, is_active)` for the hot read path at `canonical_household_service.py:250-262`.

### 3.2 `scout.routine_steps` (promote from UNCLEAR to CANONICAL)

Already defined at `022_session2_canonical.sql:294-304`. No schema change needed. The work is writing the data migration (§4), wiring the ORM model in `app/models/canonical.py`, and having the canonical generator create step-completion rows.

### 3.3 `scout.task_occurrence_step_completions` (NEW)

```
id                 uuid PK
task_occurrence_id uuid NOT NULL REFERENCES scout.task_occurrences(id) ON DELETE CASCADE
routine_step_id    uuid NOT NULL REFERENCES scout.routine_steps(id) ON DELETE RESTRICT
is_completed       boolean NOT NULL DEFAULT false
completed_at       timestamptz
created_at         timestamptz NOT NULL DEFAULT clock_timestamp()

UNIQUE (task_occurrence_id, routine_step_id)
```

Mirrors the legacy shape exactly. Needed so the canonical generator can emit per-step rows the way `task_generation_service.py:108-113` does today.

### 3.4 `scout.task_occurrences` (expand with dispute fields)

Add two nullable columns that currently live on `public.task_instances`:

```
in_scope_confirmed      boolean NOT NULL DEFAULT false
scope_dispute_opened_at timestamptz
```

Reason: `/task-instances/{id}/dispute-scope` in `backend/app/routes/task_instances.py:82-110` reads and writes both. When we consolidate, the canonical occurrence must carry these.

### 3.5 `scout.daily_win_results` (already canonical - no shape change)

The consolidation is cutover-only: `daily_win_service.py` stops writing `public.daily_wins` and callers move to `canonical_household_service.recompute_daily_win`. Schema is unchanged.

### 3.6 `scout.personal_tasks` (NEW)

Mirror `backend/migrations/006_personal_tasks.sql` one-for-one in the scout schema. Keep all status and priority CHECK constraints; preserve `source_project_task_id` FK to `scout.project_tasks`. Indexes mirror original.

### 3.7 `scout.v_household_today` (updated)

Add `LEFT JOIN` onto scope-contract fields now living on `scout.task_templates`. Replacement columns exposed to the app:

```
included            jsonb
not_included        jsonb
done_means_done     text
supplies            jsonb
photo_example_path  text
```

After this, `canonical.py:257-280` can return the scope fields in `/api/household/today` without a cross-boundary join to `public.chore_templates`.

### 3.8 FK / index callouts

- All new scout.* tables keep `ON DELETE CASCADE` from `public.families(id)`.
- `task_occurrence_id` cascade stays the same as `task_completions`.
- The photo column rename (`photo_example_url` to `photo_example_path`) needs the migration to also update the frontend consumer at `scout-ui/lib/api.ts:1346` (docstring only). Consider keeping the old name in the schema for zero-friction deploy and updating the docstring later; the audit prefers "don't paper over", which favours the rename.

---

## Section 4. Data migration plan (live-data tables only)

All sketches below are idempotent, re-runnable, and family-scoped. Row counts are live per audit §3; `public.personal_tasks` has 0 rows so it's included for completeness but is a no-op in practice.

### 4.1 `public.chore_templates` -> `scout.task_templates`

Pseudocode:

```
INSERT INTO scout.task_templates (
  family_id, template_key, label, description, recurrence, due_time,
  included, not_included, done_means_done, supplies,
  photo_example_path, estimated_duration_minutes, consequence_on_miss,
  is_active, created_at, updated_at
)
SELECT
  ct.family_id,
  'legacy_chore_' || ct.id::text   AS template_key,
  ct.name                          AS label,
  ct.description,
  ct.recurrence,
  ct.due_time,
  ct.included,
  ct.not_included,
  ct.done_means_done,
  ct.supplies,
  ct.photo_example_url,            -- copy; rename is schema-side only
  ct.estimated_duration_minutes,
  ct.consequence_on_miss,
  ct.is_active,
  ct.created_at,
  ct.updated_at
FROM public.chore_templates ct
ON CONFLICT (family_id, template_key) DO UPDATE SET
  label       = EXCLUDED.label,
  description = EXCLUDED.description,
  ...          -- idempotent update of scope fields
  updated_at  = EXCLUDED.updated_at;

-- Emit a migration row for task_assignment_rules derived from
-- chore_templates.assignment_type + assignment_rule jsonb:
INSERT INTO scout.task_assignment_rules (task_template_id, rule_type, rule_params, priority)
SELECT
  tt.id,
  CASE ct.assignment_type
    WHEN 'fixed'            THEN 'fixed'
    WHEN 'rotating_daily'   THEN 'day_parity'
    WHEN 'rotating_weekly'  THEN 'week_rotation'
  END,
  ct.assignment_rule,
  0
FROM public.chore_templates ct
JOIN scout.task_templates tt
  ON tt.template_key = 'legacy_chore_' || ct.id::text;
```

Preserved: all 13 columns on chore_templates including the scope-contract block.
Dropped: none at this migration. `public.chore_templates` stays in place during the dual-write window.
FK re-point: chore_templates is referenced from `public.task_instances.chore_template_id` (migration 002:118). During the consolidation window, we'll add a `legacy_chore_template_id` side column on `scout.task_occurrences` to carry the source so backfill can match.

Dual-write window: yes. The `create_chore_template` path (`chore_service.py:29-54`) keeps writing public; trigger or service-layer shim copies to scout within the same transaction. After both are consistent, cutover POST /chore-templates to write scout directly and keep the trigger reading-only for a deploy cycle before dropping it.

Cutover sequence:
1. Deploy schema expansion (adds cols to scout.task_templates).
2. Deploy migration (backfill from chore_templates).
3. Deploy dual-write code path.
4. Verify canonical reads on `/api/household/today` now surface scope fields.
5. Cut over `chore_service` to write canonical only; shim stays as read path.
6. Deprecate `public.chore_templates` in a later slice.

### 4.2 `public.routines` -> `scout.routine_templates`

Already partially done by migration 036 (`backend/migrations/036_chores_routines_to_canonical.sql`), which moved member_config `chores.routines` into canonical. The remaining `public.routines` rows (NOT in member_config) need their own migration.

Pseudocode:

```
INSERT INTO scout.routine_templates (
  family_id, routine_key, label, block_label, recurrence,
  due_time_weekday, due_time_weekend, owner_family_member_id,
  created_at, updated_at
)
SELECT
  r.family_id,
  'legacy_' || r.block || '_' || r.id::text  AS routine_key,
  r.name                                     AS label,
  r.block                                    AS block_label,
  r.recurrence,
  r.due_time_weekday,
  r.due_time_weekend,
  r.family_member_id                         AS owner_family_member_id,
  r.created_at,
  r.updated_at
FROM public.routines r
WHERE r.is_active = true
ON CONFLICT (family_id, routine_key, owner_family_member_id) DO NOTHING;
```

Preserved: all scheduling fields. Dropped: `is_active` (inactive routines are filtered out; canonical has no is_active because soft-delete isn't used there).

FK re-point: `public.task_instances.routine_id` will dangle post-move. See §4.4.

### 4.3 `public.routine_steps` -> `scout.routine_steps`

```
INSERT INTO scout.routine_steps (
  routine_template_id, standard_of_done_id, sort_order, label, notes, created_at
)
SELECT
  rt.id          AS routine_template_id,
  NULL,
  rs.sort_order,
  rs.name        AS label,
  NULL,
  rs.created_at
FROM public.routine_steps rs
JOIN public.routines pr          ON pr.id = rs.routine_id
JOIN scout.routine_templates rt  ON rt.routine_key = 'legacy_' || pr.block || '_' || pr.id::text
                                AND rt.family_id = pr.family_id
WHERE rs.is_active = true
ON CONFLICT (routine_template_id, sort_order) DO NOTHING;
```

Idempotent via the UNIQUE constraint defined at `022_session2_canonical.sql:303`.

### 4.4 `public.task_instances` -> `scout.task_occurrences`

Most expensive migration in the slice. Split in three steps to reduce blast radius:

Step A - migrate routine-sourced rows:

```
INSERT INTO scout.task_occurrences (
  family_id, routine_template_id, assigned_to,
  occurrence_date, due_at, status,
  in_scope_confirmed, scope_dispute_opened_at,
  generated_at, created_at, updated_at
)
SELECT
  ti.family_id,
  rt.id,
  ti.family_member_id,
  ti.instance_date,
  ti.due_at,
  CASE
    WHEN COALESCE(ti.override_completed, ti.is_completed) THEN 'complete'
    ELSE 'open'
  END,
  ti.in_scope_confirmed,
  ti.scope_dispute_opened_at,
  ti.created_at, ti.created_at, ti.updated_at
FROM public.task_instances ti
JOIN public.routines pr         ON pr.id = ti.routine_id
JOIN scout.routine_templates rt
  ON rt.routine_key = 'legacy_' || pr.block || '_' || pr.id::text
 AND rt.family_id   = pr.family_id
WHERE ti.routine_id IS NOT NULL
ON CONFLICT DO NOTHING;
```

Step B - migrate chore-sourced rows (mirror of above, joining through `scout.task_templates`).

Step C - migrate completions into `scout.task_completions`:

```
INSERT INTO scout.task_completions (task_occurrence_id, completed_by, completed_at, completion_mode, notes)
SELECT
  occ.id,
  COALESCE(ti.override_by, ti.family_member_id),
  ti.completed_at,
  CASE WHEN ti.override_completed IS NOT NULL THEN 'parent_override' ELSE 'manual' END,
  ti.override_note
FROM public.task_instances ti
JOIN scout.task_occurrences occ
  ON occ.family_id       = ti.family_id
 AND occ.occurrence_date = ti.instance_date
 AND occ.assigned_to     = ti.family_member_id
WHERE ti.is_completed = true OR ti.override_completed IS NOT NULL;
```

Step D - migrate step completions from `public.task_instance_step_completions` to `scout.task_occurrence_step_completions` (straight join via the new mapping).

Preserved: every execution record, override trail, and dispute flag. Dropped: denormalized `chore_template_id` / `routine_id` on the target (replaced by the canonical FKs).

FK re-point: `nudges_service.py:182-198` still queries `FROM task_instances ti JOIN routines r`. This must be updated to `scout.task_occurrences + scout.routine_templates` AFTER the step-C backfill lands. Cross-slice dependency - see §5.

Dual-write window: yes, 1-2 deploys. The legacy generator stays enabled; a canonical shadow-write gets added inside `task_generation_service.generate_for_date` for the duration. Idempotency guarded by unique (family_member_id, routine_id, instance_date) on the legacy side and by the occurrence lookup on the canonical side.

Cutover: only stop the legacy generator once the dashboard (`dashboard_service.py:203`) and AI tools (`tools.py:203`) read from scout.

### 4.5 `public.task_instance_step_completions` -> `scout.task_occurrence_step_completions`

Single backfill join as described in §4.4 Step D. Idempotent via the new unique constraint.

### 4.6 `public.daily_wins` -> `scout.daily_win_results`

scout.daily_win_results already receives canonical writes. This migration is a backfill of legacy rows that haven't been recomputed yet:

```
INSERT INTO scout.daily_win_results (family_id, family_member_id, for_date, earned, total_required, total_complete, missing_items, computed_at)
SELECT
  dw.family_id, dw.family_member_id, dw.win_date,
  dw.is_win, dw.task_count, dw.completed_count,
  '[]'::jsonb, dw.updated_at
FROM public.daily_wins dw
ON CONFLICT (family_member_id, for_date) DO NOTHING;
```

Once migrated, `daily_win_service.compute_daily_win` is replaced at the callsite; daily_wins table stays until a later DEPRECATE pass drops it.

### 4.7 `public.personal_tasks` -> `scout.personal_tasks`

0 live rows, so the "data migration" is schema-only: create the scout table, re-mirror the migration file, and cut the ORM class over. The app code changes are in §6's PR plan.

### 4.8 Re-runnability and idempotency

Every INSERT in §4.1 through §4.6 uses `ON CONFLICT DO NOTHING` or `ON CONFLICT DO UPDATE` keyed on the unique constraints in `022_session2_canonical.sql`. A failed deploy that partially backfills is safe to retry. We will add a migration-verification step in CI (there's a precedent per commit `0142b29 chore(ci): batch 1 PR 5 - smoke-deployed auto-trigger + migration verify`).

---

## Section 5. Dependencies on other slices

Ordered by when they block Slice A work.

1. Slice D (identity / permissions / connectors)
   - `scout.family_members` is a shim view over `public.family_members` (`022_session2_canonical.sql:184`). `scout.task_occurrences.assigned_to` already FKs `public.family_members`. No change needed before Slice A, but Slice D must NOT break the shim view during its work. Dependency = "do not regress".
   - `scout.role_tier_permissions` is the backing store for `household.complete_own_task`, `household.complete_any_task`, `chores.manage_config`, `tasks.manage_self`, `chore.complete_self`. Used by every write route in this slice. If Slice D renames or restructures permission keys, our PRs must absorb that.
2. Slice C (ai-chat / nudges)
   - `nudge_rule_validator.py:58-70` whitelists `public.chore_templates`, `public.task_instances`, `public.routines` by name. Our CONSOLIDATE pass silently breaks nudges unless Slice C lands scout.* in that allowlist BEFORE our deprecate pass. Hard blocker for the final cutover PR of Slice A.
   - AI tools (`app/ai/tools.py:203,234,272-287`) call the legacy services directly. Slice C needs to port these to canonical services before we can retire `task_generation_service`.
   - `nudge_ai_discovery.py:262-290` aggregates `recent_missed_routines_3d` by querying `public.task_instances` + `public.routines`. Same dependency: Slice C must switch the scanner source before our cutover.
3. Slice B (meals / grocery / home)
   - No direct dependencies in scope for Slice A. `scout.standards_of_done` is shared but neither slice mutates it in this cycle.

Explicit non-dependencies for Slice A:
- `public.parent_action_items` (33 rows, active) is read by `task_instances.py:97-107` but creating one is a write; no schema change needed here.
- `public.sessions` (172 rows) is auth infrastructure; slice A does not touch it.

---

## Section 6. Proposed PR count and ordering

Eight PRs, ordered so each can deploy to Railway / Vercel and be verified before the next starts. Every PR ends with `node scripts/architecture-check.js` clean and smoke-deployed green per the `feedback_verify_deploys.md` memory.

| # | Title | Scope | Migration? |
|---|---|---|---|
| A1 | schema: expand scout.task_templates with scope-contract fields | Adds columns, indexes. Docstring notes the rename. No code changes. | yes |
| A2 | schema: add scout.task_occurrences dispute columns + scout.task_occurrence_step_completions + promote scout.routine_steps | Three DDL items, batched because none carry data yet. | yes |
| A3 | schema: add scout.personal_tasks (0-row table mirror) | DDL-only. | yes |
| A4 | service: extend canonical_household_service to materialize step completions + scope fields on generate | Backend code only. Tests added. Updates `scout.v_household_today` to surface scope fields. No migration. | no |
| A5 | data: backfill public.chore_templates, routines, routine_steps into scout.*; add keep-alive view on public.chore_templates for scope reads | The big backfill migration. Family-scoped, idempotent. Dual-write stays intact. | yes |
| A6 | data: backfill public.task_instances, task_instance_step_completions, daily_wins into scout.*; add canonical shadow-write inside task_generation_service | Turns on shadow writes. Risk = high. | yes |
| A7 | cutover: canonical read path (dashboard, AI tools, personal_tasks endpoints). Switch routes to scout, keep legacy writes as shim | Removes legacy reads. Legacy writes remain for rollback safety. | no |
| A8 | cleanup: retire legacy generators + daily_win_service, drop legacy routes, deprecate (not drop) public tables | Code removal + DB deprecate (comments, view on public). No DDL drops yet. | yes (comments only) |

Each PR is small enough to review in one sitting: A1-A3 are DDL-only, A4 is one service file, A5 is one migration, A6 is one migration + one service change, A7 is route changes with a mechanical pattern, A8 is code removal.

Slice-C dependency checkpoints: A6 cannot merge until Slice C's nudge-rule-validator PR adds scout.* to the allowlist. A8 cannot merge until Slice C's AI-tool port lands.

---

## Section 7. Per-PR risk rating

| # | Risk | Reason |
|---|---|---|
| A1 | low | Additive columns with defaults. No data move. Read path still uses public. |
| A2 | low | Additive DDL on canonical-only tables with no readers. |
| A3 | low | 0-row mirror. |
| A4 | medium | Changes view `scout.v_household_today`; if the LEFT JOIN explodes row count we regress the dashboard. Mitigation: unit-test the view cardinality. |
| A5 | medium | Touches live public data. Backfill idempotent but family-scoped correctness must be verified. Dispute fields, scope fields must round-trip. |
| A6 | high | Dual-write on the hottest chores path. If shadow write fails silently, scout.task_occurrences drifts from public.task_instances. Observability: emit a counter on every dual-write mismatch. |
| A7 | high | Breaking read contract: dashboard, AI tools, `/families/.../task-instances` all switch source. No shim. Needs a feature flag or parallel endpoint for rollback. |
| A8 | medium | Code deletion + DDL comments. Irreversible for the code parts; DB parts reversible. |

Anything that touches live public data is at least medium. A6 + A7 both touch route contracts + hot path; they're the two to watch.

---

## Section 8. Per-PR rollback plan

| # | Rollback |
|---|---|
| A1 | "drop the new columns" - simple ALTER TABLE DROP COLUMN on scout.task_templates. No data loss because no writers used them yet. |
| A2 | "drop the new columns / drop the new table" - ALTER TABLE for occurrence columns; DROP TABLE scout.task_occurrence_step_completions. scout.routine_steps had no writers yet so safe to DROP. |
| A3 | "drop the new table" - scout.personal_tasks is 0 rows. |
| A4 | "revert the migration file" - view DDL is reversible via the prior `CREATE OR REPLACE VIEW` in migration 022. Keep the old view body in a rollback SQL fixture. |
| A5 | Reversible per-table: TRUNCATE the rows we just inserted into scout.task_templates (scoped to `template_key LIKE 'legacy_chore_%'`), scout.routine_templates (scoped to `routine_key LIKE 'legacy_%'`), scout.routine_steps cascade. No pre-migration snapshot required because origin rows stay in public. |
| A6 | Reversible but more work. TRUNCATE scoped on scout.task_occurrences for the backfilled range, same for scout.task_completions and scout.task_occurrence_step_completions. daily_win_results reversible via `WHERE for_date < now AND NOT earned IS NULL` scoped delete. Also need to REVERT the shadow-write code path - this is the PR where "revert the migration file AND the code" is mandatory. Manual data restore from a pre-migration Postgres snapshot is the insurance policy; we take one before merging A5. |
| A7 | Reversible via the feature-flag described in §7. If disabled, routes fall back to legacy reads. If flag plumbing fails, revert the PR. Legacy write path wasn't touched, so rollback is bounded. |
| A8 | "revert the migration file" for DDL-comment-only migration; "revert the PR" for the code deletions. Irreversible portion: once legacy routes are removed, any client still hitting the old URLs gets 404 - we accept this because A7 stayed deployed for at least one full release cycle. |

No step in Slice A is labelled "irreversible, don't fail" - all of them have a recovery path. The riskiest case is A6 where we'd restore from snapshot.

---

## Section 9. Smoke test strategy

Existing coverage (grep-verified in `backend/tests/`):

- `test_canonical_session2.py:439-539` - canonical route envelopes. Must stay green through every PR.
- `test_canonical_session2_block2.py:325-513` - occurrence generation + daily-win recompute. Expand with scope-field assertions after A4.
- `test_chore_templates.py:27-140` - chore_template scope-contract persistence. After A1, add a twin test that asserts the same round-trip via scout.task_templates.
- `test_task_generation.py:21-151` - legacy generator. Keep until A8 retires it; in A6 extend to assert scout shadow-write side effect.
- `test_daily_wins.py:56-124` - legacy DailyWin. In A6, duplicate into `test_canonical_daily_wins.py` asserting scout.daily_win_results has the same answer.
- `test_r3_migrations.py` - adds migration-presence checks for 036 etc. Extend for new migrations 053+ that Slice A introduces.
- `test_personal_tasks.py:43-260` - legacy personal_tasks; duplicate in A3/A7 against the canonical shape.
- `test_nudge_rule_validator.py` - Slice C owns the scout.* allowlist test but we assert on it from Slice A smoke once cutover lands.

New coverage to write:

1. `test_canonical_session2_block2.py::test_v_household_today_surfaces_scope_fields` - after A4, query `scout.v_household_today` and assert `included`, `not_included`, `done_means_done` non-null for the seed rows.
2. `test_canonical_backfill_chores.py` - after A5, a fresh-DB smoke that runs the backfill and asserts 1:1 row equivalence between `public.chore_templates` and scout.
3. `test_canonical_task_occurrences_shadow.py` - after A6, assert `generate_for_date` writes BOTH public.task_instances and scout.task_occurrences with matching per-member counts.
4. `test_canonical_dashboard_cutover.py` - after A7, assert `/api/household/today` returns identical items when the feature flag is ON vs OFF (snapshot compare).
5. Playwright: only `playwright tests/example.spec.ts` currently exists at repo root. Slice A needs at least one child-dashboard happy-path spec that (a) loads `/`, (b) completes a chore, (c) verifies the completion persisted. Add `playwright tests/chores_today.spec.ts`.

Smoke runbook (manual, pre-merge):
- Hit `/api/household/today` on preview deploy. Confirm the payload carries `included` / `not_included` arrays after A4.
- Create a chore via `/admin/chores/new`. Confirm it lands in both public.chore_templates and scout.task_templates during dual-write (A5 window).
- Mark a chore complete as a child account. Confirm scout.task_completions row appears and `daily_win_recomputed` is true (A6 window).

---

## Section 10. Known gotchas and stop-conditions

Things a junior engineer executing this plan will absolutely trip over unless called out:

1. Nudge-rule SQL validator (HIGH - already flagged by audit §4).
   `backend/app/services/nudge_rule_validator.py:58-70` has a hardcoded table allowlist. Any rule referencing scout.* will be rejected as "disallowed table". If A8 removes `public.chore_templates` BEFORE Slice C updates this allowlist, every chore-based nudge rule raises RuleValidationError silently and nudges stop firing. STOP CONDITION: do not merge A8 until `'task_occurrences' in _ALLOWED_TABLES` is confirmed live.

2. AI tool integration still points at legacy.
   `backend/app/ai/tools.py:203,234,274-287` uses `task_instance_service.list_task_instances` and `chore_service.list_chore_templates`. If A7 removes the legacy routes without a Slice-C port, AI chat tools start erroring. STOP CONDITION: A7 cannot merge until the Slice-C AI tool port is verified in preview.

3. Dual-write parity bug risk.
   `task_generation_service.py:157` commits `public.task_instances` inside the service. The A6 shadow-write must be inside the same transaction, not a follow-on commit, or a crash between the two leaves scout out of date. See existing pattern in `canonical.py:450-453` which shows the preferred style (explicit db.execute + single db.commit at the bottom of the handler).

4. Photo path rename.
   §3.1 renames `photo_example_url` to `photo_example_path`. `scout-ui/lib/api.ts:1346` has a comment that references the legacy name. Update both sides in A1's PR body; otherwise frontend reviewers will assume we dropped the field. The semantics did not change - it was always a Storage path despite the `_url` suffix.

5. Migrations must be mirrored.
   Every migration file in `backend/migrations/` MUST have an identical copy in `database/migrations/`. Verified that `041_chore_scope_contract.sql` is in both. If a PR in Slice A forgets the mirror, Railway picks it up (runs backend/) but the database/ copy goes stale. The audit calls this out; the house rule is backend/ is canonical, mirror at commit time.

6. `scout.routine_steps` was created in migration 022 but has NO ORM, NO tests, NO routes today. Do not assume it's wired - A4 / A5 are the first PRs that actually populate it.

7. Legacy `routines.block` CHECK constraint is narrow.
   `backend/migrations/002_life_management.sql:31` restricts `block IN ('morning', 'after_school', 'evening')`. Migration 036 already mapped member_config "Chores" block_label into scout.routine_templates, which is a broader vocabulary. When A2 backfills `public.routines`, the `block` value "Chores" won't appear (those were already migrated via member_config), but if any operator-created routine has a non-canonical block label post-036, our INSERT will succeed on the scout side while the public source looks stale. Not a blocker but worth verifying during A2 smoke.

8. Daily-win recompute is called from two routes now.
   `canonical.py:443-451` calls canonical `recompute_daily_win`. `daily_wins.py:28-37` calls legacy `compute_for_family_date`. Both write different tables. If A6 mis-orders the cutover, a child's win card can disagree with the admin's payout screen. STOP CONDITION: A7 must replace the call inside `daily_wins.py::compute_daily_wins` before removing the legacy service.

9. `task_instances.py:82-110` uses `public.parent_action_items`.
   The dispute-scope handler writes a ParentActionItem row. That table is in `public` (33 rows live). Not in scope for this slice but any Slice A work that removes the dispute-scope route must ensure parent_action_items is still reachable via the canonical equivalent. Slice D owns parent_action_items. Cross-slice write.

10. `backend/app/services/dashboard_service.py:203` reads "Today's task instances (chores/routines)" from public.task_instances.
    This is not on the nudge surface so it's easy to miss, but the `/personal` and home dashboards go through it. A7 must include a cutover here.

11. Two generators running after A6 is intentional but time-bounded.
    The A6 dual-write window MUST NOT span a major feature release. Ship A6 and A7 back-to-back. Leaving two generators live for days invites diff bugs on every incremental chore-template change.

---

## Open questions

- `scout.task_notes` and `scout.task_exceptions` are listed as CANONICAL in the audit but have no route, service, or test coverage found by grep. Decision needed: do we leave them as "ready when needed" (my current plan) or deprecate them now? I recommend leave; Andrew should confirm.
- `public.personal_tasks` has 0 rows per audit but `backend/app/ai/tools.py:939` does `personal_tasks_service.create_personal_task_nocommit(...)` inside an AI tool path. Is anything actually hitting that path in prod? If yes, the "0 rows" count is misleading and the table needs live coverage in A3; if no, A3 is a pure schema mirror. Need prod-DB inspection to confirm.
- scout schema currently has 8 shim views for the foundation tables (`families`, `family_members`, etc.). If Slice D converts any of these from views to real tables during its work, Slice A's migrations that reference `public.families(id)` must be re-pointed. Awaiting Slice D scope to know.
- The audit's effort=S estimate for `public.task_instances` suggests Andrew's mental model is KEEP+BRIDGE. My plan goes further (CONSOLIDATE). If KEEP+BRIDGE is what's actually desired, drop PRs A6 / A7 and keep only the scope-field columns on scout.task_templates - the slice compresses to 4 PRs. Need confirmation.
- Playwright coverage is thin (1 file in the root `playwright tests/`). Is there a preferred location for new specs, or does Slice A get to propose one?
