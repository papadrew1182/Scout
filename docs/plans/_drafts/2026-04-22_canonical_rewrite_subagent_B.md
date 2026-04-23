# Canonical rewrite plan, Slice B: meals / grocery / home maintenance / bills

Author: subagent B (planning only, no code changes)
Date: 2026-04-22
Baseline audit: `docs/plans/2026-04-22_schema_canonical_audit.md`
Architecture reference: `docs/architecture/ARCHITECTURE.md`, `docs/architecture/interaction_contract.md`
Migration source of truth: `backend/migrations/*.sql` (mirror at `database/migrations/*.sql`)

This document proposes a canonical consolidation for the meals, grocery, home-maintenance, and bills surfaces. Andrew decides final direction; this file is evidence-based planning input.

---

## Section 1. Slice inventory

The table lists every slice table found by grep. Row counts come from the baseline audit (section 3). Route and service paths are absolute inside the repo.

### 1.1 Meals cluster

| Name | Schema | Rows | Introduced | Routes | Services | Models | Tests |
|------|--------|------|------------|--------|----------|--------|-------|
| `meals` | public | 0 | `backend/migrations/005_meals.sql:48` | `backend/app/routes/meals.py:273` (`POST /meals`) | `backend/app/services/meals_service.py:121` | `backend/app/models/meals.py:25` (Meal) | `backend/tests/test_meals.py`, `backend/tests/test_meals_routes.py`, `backend/tests/test_meal_plan_dietary.py` |
| `meal_plans` | public | 0 | `backend/migrations/005_meals.sql:17` | `backend/app/routes/meals.py:35` (`/meal-plans`) | `backend/app/services/meals_service.py:28` | `backend/app/models/meals.py:11` | `backend/tests/test_meals.py` |
| `dietary_preferences` | public | 0 | `backend/migrations/005_meals.sql:88` | `backend/app/routes/meals.py:308` | `backend/app/services/meals_service.py:183` | `backend/app/models/meals.py:47` | `backend/tests/test_meal_plan_dietary.py` |
| `weekly_meal_plans` | public | 0 | `backend/migrations/013_meals_weekly_plans.sql:24` | `backend/app/routes/meals.py:79` (generate), `:105` (list), `:118` (current), `:161` (approve) | `backend/app/services/weekly_meal_plan_service.py:366` | `backend/app/models/meals.py:59` | `backend/tests/test_weekly_meal_plans.py` |
| `meal_reviews` | public | 0 | `backend/migrations/013_meals_weekly_plans.sql:79` | `backend/app/routes/meals.py:225` (create), `:238` (list), `:249` (summary) | `backend/app/services/weekly_meal_plan_service.py:752`, `:783`, `:796` | `backend/app/models/meals.py:81` | `backend/tests/test_weekly_meal_plans.py` |
| `scout.meal_transformations` | scout | 0 (UNCLEAR in audit) | `backend/migrations/044_meal_base_cooks.sql:13` | none grep-found | none | none | none |

Notes:
- `public.meals` was extended with base-cook columns in `backend/migrations/044_meal_base_cooks.sql:6-10` (`is_base_cook`, `base_cook_yield_servings`, `base_cook_keeps_days`, `storage_notes`).
- `public.meals` in practice plays two roles: a daily-calendar meal row AND a staple-meal registry (confirmed by `044_meal_base_cooks.sql:4-6` comment "The existing public.meals table serves as the staple registry").
- `public.weekly_meal_plans` holds three JSONB blobs: `week_plan`, `prep_plan`, `grocery_plan`, plus a `constraints_snapshot`.
- `scout.meal_transformations` FKs into `public.meals` (migration 044 line 16-17), so meal_transformations is scout-resident but anchored to public.
- `weekly_meal_plan_entries` is referenced in `backend/migrations/044_meal_base_cooks.sql:30` but only via conditional DO block. It does not exist in migration source; the ALTER fires only if it exists. Treat as a phantom.

### 1.2 Grocery cluster

| Name | Schema | Rows | Introduced | Routes | Services | Models | Tests |
|------|--------|------|------------|--------|----------|--------|-------|
| `grocery_items` | public | 2 (ACTIVE) | `backend/migrations/011_grocery_purchase_requests.sql:13` | `backend/app/routes/grocery.py:25` (list), `:52` (create), `:68` (update) | `backend/app/services/grocery_service.py:81`, `:145`, `:157`, `:208`, `:220` | `backend/app/models/grocery.py:12` | `backend/tests/test_qa.py`, indirectly `test_weekly_meal_plans.py` via sync |
| `purchase_requests` | public | 1 (ACTIVE, per audit) | `backend/migrations/011_grocery_purchase_requests.sql:55` | `backend/app/routes/grocery.py` (later blocks) | `backend/app/services/grocery_service.py:236-387` | `backend/app/models/grocery.py:36` | `backend/tests/test_qa.py` |

Notes:
- Slice A (chores/tasks) owns `parent_action_items` (33 rows) per audit but the meals slice reuses it through `_create_meal_plan_review_action` at `backend/app/services/weekly_meal_plan_service.py:167`. Hand-off boundary.
- Later migrations (`013_meals_weekly_plans.sql:124-131`) added `weekly_plan_id` and `linked_meal_ref` to `grocery_items` to sync from approved meal plans. That FK ties grocery to weekly_meal_plans.

### 1.3 Home maintenance cluster

| Name | Schema | Rows | Introduced | Routes | Services | Models | Tests |
|------|--------|------|------------|--------|----------|--------|-------|
| `scout.home_zones` | scout | UNCLEAR (seeded by `backend/seed_smoke.py:332` when present) | `backend/migrations/042_home_maintenance.sql:3` | `backend/app/routes/home_maintenance.py:109` (list), `:115` (create) | inline in route | `backend/app/models/home_maintenance.py:11` | `smoke-tests/tests/home-maintenance.spec.ts` |
| `scout.home_assets` | scout | 0 | `backend/migrations/042_home_maintenance.sql:15` | `backend/app/routes/home_maintenance.py:130`, `:136` | inline | `backend/app/models/home_maintenance.py:26` | same |
| `scout.maintenance_templates` | scout | 0 | `backend/migrations/042_home_maintenance.sql:33` | `backend/app/routes/home_maintenance.py:151`, `:157` | inline | `backend/app/models/home_maintenance.py:47` | same |
| `scout.maintenance_instances` | scout | 0 | `backend/migrations/042_home_maintenance.sql:53` | `backend/app/routes/home_maintenance.py:172`, `:182`, `:195` | inline | `backend/app/models/home_maintenance.py:70` | same |

Notes:
- Home maintenance was introduced canonical-first in migration 042. Already scout-resident. This is the cleanest part of the slice.
- Its permissions live in `backend/migrations/043_home_maintenance_permissions.sql` with keys `home.view`, `home.manage_zones`, `home.manage_assets`, `home.manage_templates`, `home.complete_instance`.
- Frontend surfaces: `scout-ui/app/(scout)/home/index.tsx` (user surface) and `scout-ui/app/admin/home/index.tsx` (admin).
- The four tables do hard FKs into `public.families` and `public.family_members` (confirmed in migration 042 lines 5, 17, 47, 56, 60). This is the established pattern from 022.

### 1.4 Bills cluster

| Name | Schema | Rows | Introduced | Routes | Services | Models | Tests |
|------|--------|------|------------|--------|----------|--------|-------|
| `bills` | public | 0 | `backend/migrations/008_finance.sql:25` | `backend/app/routes/finance.py:15` (list), `:51` (create), `:77` (pay), `:91` (delete) | `backend/app/services/finance_service.py:39-208` | `backend/app/models/finance.py:11` (Bill) | `backend/tests/test_integrations.py`, `backend/tests/test_qa.py` |

Notes:
- `bills` is finance-adjacent. Included in this slice per user spec.
- Referenced from dashboard service: `backend/app/services/dashboard_service.py:69-72` (unpaid count), `:371-378` (overdue count), and feeds `app/ai/tools.py:212-225`.
- Referenced by nudge SQL whitelist: `backend/app/services/nudge_rule_validator.py:68` lists `bills` as an allowed public table.

### 1.5 Views that touch slice tables

Grep of migrations for `CREATE .* VIEW` against the slice tables:

- None in `backend/migrations/022_session2_canonical.sql` touch meals, grocery, bills, or home maintenance. `scout.v_household_today` reads only tasks and routines (lines 761-789).
- `database/migrations/*.sql` mirrors the same set.
- No views need updating in Slice B aside from any net-new views we add. This is a significant simplifier.

---

## Section 2. Per-table recommended action

Legend: CONSOLIDATE means physically move to `scout.*`. KEEP+BRIDGE means leave in place and expose a scout view. DEPRECATE means drop after verifying no writes. LEAVE means no action in this slice.

| Table | Rows | Routes active? | Recommendation | Justification |
|-------|------|----------------|----------------|---------------|
| `public.meals` | 0 | yes (meals.py, weekly plan sync, AI tools) | CONSOLIDATE to `scout.meal_staples` and `scout.meal_plan_entries` | Dual-role today. Splitting into staple registry and per-date entry clarifies semantics. 0 rows means no migration risk. |
| `public.meal_plans` | 0 | yes (meals.py lines 35-71) | DEPRECATE | Superseded by `public.weekly_meal_plans` (richer JSONB model). 0 rows. Frontend code (`scout-ui/lib/api.ts:632+`) uses weekly endpoints, not `/meal-plans`. |
| `public.weekly_meal_plans` | 0 | yes, heavily | CONSOLIDATE to `scout.meal_weekly_plans` | Source of truth for AI meal planning. JSONB shape stable. 0 rows means rename-and-redirect is safe. |
| `public.meal_reviews` | 0 | yes | CONSOLIDATE to `scout.meal_reviews` | Tied to meal weekly plans. Move together. |
| `public.dietary_preferences` | 0 | yes | CONSOLIDATE to `scout.member_dietary_preferences` | Per-member data. Fits Layer 1 (member_config) per ARCHITECTURE.md but existing shape is relational, not JSONB. Keep relational under scout. |
| `public.grocery_items` | 2 (ACTIVE) | yes | CONSOLIDATE to `scout.grocery_items` with data migration | Only live-data table in slice. Requires dual-write window and explicit migration. |
| `public.purchase_requests` | 1 (ACTIVE) | yes | CONSOLIDATE to `scout.purchase_requests` with data migration | Tightly coupled to grocery_items (FK both ways). Move in same PR as grocery_items. |
| `public.bills` | 0 | yes (finance.py) | KEEP+BRIDGE via `scout.bills` view, defer CONSOLIDATE | 0 rows but live routes, dashboard reads, AI tool reads, and nudge whitelist. A no-op view that selects `*` from `public.bills` matches the 022 shim pattern and unblocks Slice C/D without code churn. Full consolidation is a finance sprint, not part of this slice. |
| `scout.home_zones` | present | yes | LEAVE, already canonical | No action needed. |
| `scout.home_assets` | 0 | yes | LEAVE, already canonical | No action needed. |
| `scout.maintenance_templates` | 0 | yes | LEAVE, already canonical | No action needed. Note `done_means_done` / `included` / `not_included` / `supplies` columns already in canonical position here (`backend/migrations/042_home_maintenance.sql:42-45`), which is the pattern the Slice A audit wants for chores. |
| `scout.maintenance_instances` | 0 | yes | LEAVE, already canonical | No action needed. |
| `scout.meal_transformations` | 0 | none | HOLD (audit as UNCLEAR) | Created in migration 044 but grep finds no routes, services, or tests. Either remove in a separate cleanup PR or wire up. Do not fold into the slice. |

Key caveat: every recommendation above assumes the production row counts in the audit are current. Before cutover, re-query `SELECT COUNT(*)` for each CONSOLIDATE table in production and confirm still zero (except grocery_items, purchase_requests, and home_zones if seeded). Stop-condition if row count grew unexpectedly.

---

## Section 3. Proposed canonical target shape

Column lists and constraints below preserve the existing public shapes unless noted. No column renames are proposed for live-data tables.

### 3.1 `scout.meal_staples` (from legacy `public.meals` with `is_base_cook=true` semantics)

```
id                          uuid PK default gen_random_uuid()
family_id                   uuid NOT NULL REFERENCES public.families (id) ON DELETE CASCADE
created_by                  uuid REFERENCES public.family_members (id) ON DELETE SET NULL
title                       text NOT NULL CHECK (length(btrim(title)) > 0)
description                 text
notes                       text
is_base_cook                boolean NOT NULL DEFAULT false
base_cook_yield_servings    integer
base_cook_keeps_days        integer
storage_notes               text
created_at                  timestamptz NOT NULL DEFAULT now()
updated_at                  timestamptz NOT NULL DEFAULT now()
```

Notes:
- Removes `meal_date`, `meal_type`, `meal_plan_id` fields from legacy `public.meals` since staples are not calendar entries. Those move to `scout.meal_plan_entries`.
- The existing staples UI (`scout-ui/app/admin/meals/staples/new.tsx`) only uses title + base-cook fields today, so no UI regression.

### 3.2 `scout.meal_plan_entries` (from legacy `public.meals` calendar-entry usage)

```
id                      uuid PK default gen_random_uuid()
family_id               uuid NOT NULL REFERENCES public.families (id) ON DELETE CASCADE
weekly_plan_id          uuid REFERENCES scout.meal_weekly_plans (id) ON DELETE SET NULL
meal_staple_id          uuid REFERENCES scout.meal_staples (id) ON DELETE SET NULL
created_by              uuid REFERENCES public.family_members (id) ON DELETE SET NULL
meal_date               date NOT NULL
meal_type               text NOT NULL CHECK (meal_type IN ('breakfast','lunch','dinner','snack'))
title                   text NOT NULL
description             text
notes                   text
is_base_cook_execution  boolean NOT NULL DEFAULT false
base_cook_source_entry_id uuid REFERENCES scout.meal_plan_entries (id) ON DELETE SET NULL
created_at              timestamptz NOT NULL DEFAULT now()
updated_at              timestamptz NOT NULL DEFAULT now()
UNIQUE (family_id, meal_date, meal_type)
```

Notes:
- Union of `public.meals` calendar columns + the never-realized `weekly_meal_plan_entries` phantom from migration 044.
- Ties explicitly into `scout.meal_weekly_plans` rather than the old `public.meal_plans` which is being deprecated.

### 3.3 `scout.meal_weekly_plans` (lift-and-shift from public)

Preserve every column from `backend/migrations/013_meals_weekly_plans.sql:24-68`. JSONB shapes stay identical:

- `constraints_snapshot` jsonb, free-form snapshot of family preferences at generation time.
- `week_plan` jsonb, per-day/meal-type structure the AI emits. Shape sketched in `backend/app/services/weekly_meal_plan_service.py:63` (validate_plan_payload).
- `prep_plan` jsonb, batch cook tasks + timeline.
- `grocery_plan` jsonb, store-grouped grocery snapshot. Sync target for scout.grocery_items.

Other columns unchanged: `id`, `family_id`, `created_by_member_id`, `week_start_date`, `source`, `status`, `title`, `plan_summary`, `approved_by_member_id`, `approved_at`, `archived_at`, `created_at`, `updated_at`. Keep all CHECK constraints and the partial unique index for `status='approved'`.

### 3.4 `scout.meal_reviews` (lift-and-shift from public)

Preserve columns from `backend/migrations/013_meals_weekly_plans.sql:79-109`. Only change: FK `weekly_plan_id` re-points to `scout.meal_weekly_plans`.

### 3.5 `scout.member_dietary_preferences` (from `public.dietary_preferences`)

Preserve columns from `backend/migrations/005_meals.sql:88-103`. No rename of `family_member_id` column (keeps model import trivial).

### 3.6 `scout.grocery_items` (lift-and-shift from public with live data)

Preserve every column from `backend/migrations/011_grocery_purchase_requests.sql:13-49` PLUS the 013 extensions (`weekly_plan_id`, `linked_meal_ref`). FK `weekly_plan_id` re-points to `scout.meal_weekly_plans`. FK `purchase_request_id` re-points to `scout.purchase_requests` (introduced in same PR).

CHECK constraints preserved exactly:
- `source IN ('meal_ai','manual','purchase_request')`
- `approval_status IN ('active','pending_review','approved','rejected')`
- title not blank.

### 3.7 `scout.purchase_requests` (lift-and-shift from public with live data)

Preserve every column from `backend/migrations/011_grocery_purchase_requests.sql:55-95`. FK `linked_grocery_item_id` re-points to `scout.grocery_items`.

### 3.8 `scout.bills` (KEEP+BRIDGE path)

Not a new table. Add:

```
CREATE OR REPLACE VIEW scout.bills AS SELECT * FROM public.bills;
```

This matches the eight existing shim views in `backend/migrations/022_session2_canonical.sql:183-190`. No write routes change. Future Slice (finance-specific) can do full consolidation later.

### 3.9 Home maintenance, no changes

`scout.home_zones`, `scout.home_assets`, `scout.maintenance_templates`, `scout.maintenance_instances` are already canonical. Recommend documenting them as CANONICAL in the next audit update so they drop from the UNCLEAR-35 bucket.

---

## Section 4. Data migration plan

### 4.1 `public.grocery_items` (2 rows live, only real data in slice)

Pseudocode migration sketch:

```sql
-- Step 1: CREATE TABLE scout.grocery_items (as in 3.6) WITHOUT FK to scout.purchase_requests
--         (added in step 3 to avoid chicken-and-egg).

INSERT INTO scout.grocery_items (
    id, family_id, added_by_member_id, title, quantity, unit, category,
    preferred_store, notes, source, approval_status, purchase_request_id,
    weekly_plan_id, linked_meal_ref, is_purchased, purchased_at, purchased_by,
    created_at, updated_at
)
SELECT * FROM public.grocery_items;

-- Step 2: CREATE TABLE scout.purchase_requests with NO FK to scout.grocery_items yet.

INSERT INTO scout.purchase_requests (<all cols>) SELECT * FROM public.purchase_requests;

-- Step 3: Add both cross-FKs after both tables and data exist.
ALTER TABLE scout.grocery_items
    ADD CONSTRAINT fk_scout_grocery_items_purchase_request
    FOREIGN KEY (purchase_request_id) REFERENCES scout.purchase_requests (id) ON DELETE SET NULL;

ALTER TABLE scout.purchase_requests
    ADD CONSTRAINT fk_scout_purchase_requests_linked_grocery
    FOREIGN KEY (linked_grocery_item_id) REFERENCES scout.grocery_items (id) ON DELETE SET NULL;
```

Preserved columns: all. No columns dropped.

FK re-pointing:
- `scout.grocery_items.weekly_plan_id` references `scout.meal_weekly_plans(id)`, which must exist first (PR ordering in section 6).
- `scout.grocery_items.added_by_member_id`, `purchased_by` continue to FK into `public.family_members` (this is the 022 pattern).

Dual-write window: Recommended. For the smoke window (one deploy cycle) keep both tables, add a trigger on `public.grocery_items` that also writes to `scout.grocery_items` (or vice versa). Cleanest: services write only to scout.* after model switch, and a one-way backfill trigger on the legacy table catches any stray callers. Remove trigger after the smoke passes.

Cutover sequence for grocery/purchase_requests PR:
1. Deploy migration that creates `scout.grocery_items` + `scout.purchase_requests`, copies data, adds cross-FKs.
2. Deploy code that flips `backend/app/models/grocery.py:13,37` to point at `scout` schema (add `__table_args__ = {"schema": "scout"}`).
3. Verify `GET /families/{id}/groceries/current` and `GET /families/{id}/groceries/pending-review` return the same 2 rows.
4. Mark legacy tables as read-only via trigger or DROP behind a feature flag in a later PR.

### 4.2 `public.meal_*` tables (0 rows)

No data to move. Migrations are pure DDL:
1. `CREATE TABLE scout.meal_weekly_plans` + indexes + unique constraint (clone from 013).
2. `CREATE TABLE scout.meal_reviews` with FK into scout.meal_weekly_plans.
3. `CREATE TABLE scout.meal_staples`, `scout.meal_plan_entries`, `scout.member_dietary_preferences`.
4. Swap `__tablename__`/`__table_args__` on all models in `backend/app/models/meals.py`.
5. Update `backend/app/services/weekly_meal_plan_service.py:681-752` grocery sync to write scout.grocery_items (depends on grocery PR landing first).
6. After two successful deploys with no reads on public.meal_* tables, drop them.

Stop condition: if `SELECT COUNT(*) FROM public.weekly_meal_plans` is non-zero at migration time, STOP and add a backfill step.

### 4.3 `public.bills` (0 rows, KEEP+BRIDGE)

Single statement:
```sql
CREATE OR REPLACE VIEW scout.bills AS SELECT * FROM public.bills;
```

No data migration. No model change. No route change. Purely additive.

### 4.4 Home maintenance

No migration. Already canonical.

---

## Section 5. Dependencies on other slices

| Slice | What Slice B needs from it | Why |
|-------|----------------------------|-----|
| A (chores/tasks/routines) | `scout.task_occurrences` stable for nudge consumption; `parent_action_items` canonicalization NOT required mid-slice | `backend/app/services/weekly_meal_plan_service.py:167-218` writes rows to `public.parent_action_items` with `action_type='meal_plan_review'`. This coupling should not move until Slice A's parent_action_items consolidation decides its destination. Slice B must not block on it. |
| A | Chore scope-contract pattern (`included`, `not_included`, `done_means_done`, `supplies`) | Home maintenance already has these fields canonical (`backend/migrations/042_home_maintenance.sql:42-45`). Slice A can copy the pattern from here. This is a reverse dependency: Slice B provides a reference shape. |
| C (ai-chat/nudges) | Nudge SQL whitelist update | `backend/app/services/nudge_rule_validator.py:58-70` only whitelists public.* tables (`bills` at line 68). After Slice B moves grocery and meals to scout.*, nudge rules referencing those tables will fail silently. Must coordinate whitelist expansion with Slice C. |
| C | AI tool context | `backend/app/ai/tools.py:211-226` joins meals + bills + grocery for the daily brief. Will break immediately if tables move without tool patch. Must ship in same PR or pin AI tool deploy behind Slice B. |
| D (identity/permissions/connectors) | Nothing blocking | The permission keys `grocery.add_item`, `grocery.approve`, `meal.review_self`, `meal_plan.generate`, `meal_plan.approve`, `home.*` already exist. No D dependency. |
| D | `scout.connector_mappings` | `public.grocery_items.source='meal_ai'` and YNAB bill sync rely on `connector_mappings`. Table-of-record already well-bridged per audit. No action. |

Hard blocker none; soft blockers are the AI tools file and the nudge whitelist.

---

## Section 6. Proposed PR count and ordering

Five PRs. Titles mirror the existing batch naming style (`feat(slice-b): ...`).

| Order | PR title | Scope | Migration? |
|-------|----------|-------|------------|
| B1 | `feat(slice-b): scout.bills shim view (KEEP+BRIDGE)` | Adds `scout.bills` view. No model change. Unblocks Slice C reads. | Yes, additive only. |
| B2 | `feat(slice-b): canonical meals tables (0-row lift)` | Creates `scout.meal_weekly_plans`, `scout.meal_reviews`, `scout.meal_staples`, `scout.meal_plan_entries`, `scout.member_dietary_preferences`. Switches SQLAlchemy models. Leaves grocery sync on legacy until B3. Drops `public.meal_plans` table (0 rows, no route traffic to its endpoints since UI uses weekly). | Yes. |
| B3 | `feat(slice-b): canonical grocery + purchase_requests (data migration)` | Creates `scout.grocery_items`, `scout.purchase_requests`. Copies 2 + 1 live rows. Rewires FKs. Updates models + services. Re-links `weekly_meal_plan_service.sync_grocery_items_from_plan` to new tables. Adds dual-write trigger on public.grocery_items as safety net for one deploy cycle. | Yes. Highest risk migration in slice. |
| B4 | `chore(slice-b): nudge + AI tool refits` | Updates `backend/app/services/nudge_rule_validator.py:58-70` to include `scout.*` table names. Updates `backend/app/ai/tools.py` `list_meals_or_meal_plan`, `_add_grocery_item`, and `daily_brief` tool to resolve new scout models. No schema changes. | No. |
| B5 | `chore(slice-b): drop legacy meals/grocery/bills remnants` | After 1 deploy cycle with dual-write and no reads, removes dual-write trigger, DROPs `public.meals`, `public.meal_plans`, `public.weekly_meal_plans`, `public.meal_reviews`, `public.dietary_preferences`, `public.grocery_items`, `public.purchase_requests`. Does NOT drop `public.bills` (kept per B1 decision). | Yes, destructive. Gated by Andrew sign-off. |

Out of scope:
- `scout.meal_transformations` lifecycle decision. Propose separate tiny PR after audit clarifies.
- Full finance canonicalization. Deferred to a finance-specific sprint.

---

## Section 7. Per-PR risk rating

| PR | Risk | Primary reason |
|----|------|----------------|
| B1 | low | Purely additive view over 0-row table. Matches established shim pattern in `022_session2_canonical.sql`. Rollback is `DROP VIEW`. |
| B2 | low | 0-row tables, no data to lose. JSONB shapes identical. Highest regression risk is the model `__table_args__` swap, easily caught by `backend/tests/test_weekly_meal_plans.py` and `backend/tests/test_meals*.py`. |
| B3 | medium | Live data (3 rows total), cross-FK dance, and grocery is on the critical path for the child-facing Grocery tab (`scout-ui/app/grocery/index.tsx`). A regression visible to all users. Mitigated by dual-write trigger and 2-row backfill. |
| B4 | medium | Nudge validator changes are security-relevant (SQL allowlist); careless regex edit could permit cross-schema writes. AI tools file is heavily exercised by users on every chat. |
| B5 | medium | Destructive. Low risk IF B1-B4 have been deployed successfully for at least one cycle AND dashboards show zero reads on legacy tables. High risk if rushed. Must gate on observed query traffic. |

No PR rated high assuming serial ordering and the pre-migration row-count check.

---

## Section 8. Per-PR rollback plan

| PR | Rollback |
|----|----------|
| B1 | `DROP VIEW scout.bills;` Safe. No dependents unless later PRs added. |
| B2 | `DROP TABLE scout.meal_weekly_plans CASCADE; DROP TABLE scout.meal_reviews CASCADE; DROP TABLE scout.meal_staples CASCADE; DROP TABLE scout.meal_plan_entries CASCADE; DROP TABLE scout.member_dietary_preferences CASCADE;` plus revert the models PR. Legacy public tables still intact (B2 does not drop them). Re-deploy the previous backend image. |
| B3 | The fastest rollback is to flip models back to public schema (single-line `__table_args__` revert) and redeploy. Leave scout.* tables in place (orphaned, 2 duplicate rows, harmless). Then in a follow-up migration `DROP TABLE scout.grocery_items, scout.purchase_requests`. Do NOT truncate public tables at any point during rollback; they remain source of truth. |
| B4 | Revert the validator and tool code. No schema impact. |
| B5 | Cannot rollback a DROP TABLE without a backup. Requirement: pre-PR, snapshot the seven tables to `backup.b_slice_2026MMDD.*`. Rollback = `CREATE TABLE public.<t> AS SELECT * FROM backup.b_slice_2026MMDD.<t>` + restore CHECK/FK with an inverse migration script kept alongside the drop migration. |

General rollback principle: every migration in this slice ships with a sibling `*_down.sql` or documented inverse statements in the PR body.

---

## Section 9. Smoke test strategy

### 9.1 Existing playwright specs that exercise slice tables

| Spec | What it covers |
|------|----------------|
| `smoke-tests/tests/meals-subpages.spec.ts` | `/meals/this-week`, `/meals/prep`, `/meals/reviews` render; reviews form accepts save. Implicitly exercises weekly_meal_plans and meal_reviews reads. |
| `smoke-tests/tests/meal-base-cooks.spec.ts` | `/admin/meals/staples/new` renders; `/meals/this-week` renders. Exercises staple subset of public.meals. |
| `smoke-tests/tests/home-maintenance.spec.ts` | `/home` and `/admin/home` render, zone create works. Exercises scout.home_zones write path end-to-end. |
| `smoke-tests/tests/write-paths.spec.ts` | Parent approves a pending grocery item (lines 60-100), approves a weekly plan (lines 100-130), converts purchase request to grocery (lines 163-200), writes a meal review (lines 225-270). Covers the 4 riskiest flows in Slice B. |
| `smoke-tests/tests/data-entry.spec.ts` | Admin staple creation (lines 138, 158). Covers public.meals write path. |

### 9.2 Existing pytest coverage

| Test file | Covers |
|-----------|--------|
| `backend/tests/test_meals.py` | CRUD across meal_plans, meals, dietary_preferences. |
| `backend/tests/test_meals_routes.py` | Meal route permission gating. |
| `backend/tests/test_meal_plan_dietary.py` | Dietary preference edge cases. |
| `backend/tests/test_weekly_meal_plans.py` | Weekly plan generate, approve, regenerate day, grocery sync, reviews. Most important pytest for B2 and B3. |
| `backend/tests/test_qa.py` | Grocery happy path + purchase request conversion. |
| `backend/tests/test_integrations.py` | Bills + YNAB (keep working through B1). |

### 9.3 New coverage needed

- `smoke-tests/tests/canonical-grocery.spec.ts` (new): After B3 deploys, re-run the grocery flows from `write-paths.spec.ts` against the scout.* backed endpoints AND query Postgres directly to confirm rows land in scout.grocery_items not public.grocery_items. Specific assertion: `COUNT(*) FROM public.grocery_items` should equal zero after dual-write window closes.
- `backend/tests/test_canonical_meals.py` (new): Verify `scout.meal_weekly_plans` picks up `ON CONFLICT` unique constraint for `(family_id, week_start_date) WHERE status='approved'` (the partial index from migration 013 line 62-64 must be recreated in scout).
- `smoke-tests/tests/nudge-rule-sql.spec.ts` (new): Exercise a nudge rule that queries `scout.meal_weekly_plans` after B4 deploys. Confirms the allowlist actually permits scout.* references.

### 9.4 Pre-PR verification

Before every PR merge:
```bash
psql -c "SELECT 'public.meals', count(*) FROM public.meals UNION ALL SELECT 'public.meal_plans', count(*) FROM public.meal_plans UNION ALL SELECT 'public.weekly_meal_plans', count(*) FROM public.weekly_meal_plans UNION ALL SELECT 'public.grocery_items', count(*) FROM public.grocery_items UNION ALL SELECT 'public.purchase_requests', count(*) FROM public.purchase_requests UNION ALL SELECT 'public.bills', count(*) FROM public.bills;"
```

Stop if counts differ from audit (0, 0, 0, 2, 1, 0).

---

## Section 10. Known gotchas and stop-conditions

### 10.1 Frontend hard-codes the legacy URL structure

`scout-ui/lib/api.ts:304` calls `/families/{id}/groceries/current`. The route prefix is set at `backend/app/routes/grocery.py:20` (`APIRouter(tags=["grocery"])` with no prefix; prefix comes from the path in each route). Moving the table does NOT change the URL. Good.

Same check for meals: `scout-ui/lib/api.ts:632-706` hits `/families/{id}/meals/weekly/*` and `/families/{id}/meals/reviews`. Route prefix set at `backend/app/routes/meals.py:30` (`APIRouter(prefix="/families/{family_id}", tags=["meals"])`). Moving tables does not change URLs. Good.

### 10.2 `scout-ui/lib/api.ts:13` imports `MealReview` type and `:698` sends `member_id: "00000000-0000-0000-0000-000000000000"`

Placeholder UUID. Backend overwrites with `actor.member_id` at `backend/app/routes/meals.py:234`. Behavior must be preserved across the move. Assertion: after B2, ensure `test_weekly_meal_plans.py` still passes the placeholder.

### 10.3 `public.meals` dual-role is a correctness hazard

`backend/migrations/044_meal_base_cooks.sql:4-6` says meals IS the staple registry. But `backend/app/services/meals_service.py:121` (`create_meal`) writes a calendar-style row with `meal_date` and `meal_type` NOT NULL. Today, creating a staple via `/admin/meals/staples/new` probably creates a row with a forced meal_date and meal_type. Need to confirm. Splitting in B2 fixes the ambiguity but requires inspecting `scout-ui/app/admin/meals/staples/new.tsx` to confirm what it actually sends. Stop condition: if the staples form currently sends a fake `meal_date`, B2 must handle it in the service layer and migrate accordingly.

### 10.4 AI tool will break on B2 deploy if not patched

`backend/app/ai/tools.py:211-226` (daily brief) and `:336-385` (list meals, generate grocery list) import `meals_service` and expect public.meals. Model swap in B2 means the `from app.models.meals import Meal` still works because only `__table_args__` changes. BUT `tools.py:212` does `finance_service.list_unpaid_bills` which reads `public.bills`. That keeps working (B1 is a view, not a move). So B2 is safe; B4 is still needed for the grocery tool because `backend/app/ai/tools.py:437-455` uses `grocery_service` which writes through SQLAlchemy models pointing to scout after B3. Confirm B3 and B4 ship in that order or as one deploy.

### 10.5 Nudge validator is an SQL allowlist; changing models is not enough

`backend/app/services/nudge_rule_validator.py:53` sets `_ALLOWED_SCHEMA = "public"`. Line 58-70 `_ALLOWED_TABLES` is public-only. After B2 and B3, any nudge rule referencing the new scout.* tables will be rejected at parse time. B4 is mandatory, not optional. Failure mode: silent nudge non-delivery.

### 10.6 Home maintenance permissions are complete, do not touch

`backend/migrations/043_home_maintenance_permissions.sql` seeds the five keys. Interaction with `backend/app/auth.py` Actor.require_permission is already working (per existing home-maintenance smoke test). Do not re-seed or edit.

### 10.7 Dashboard service aggregates three slice tables

`backend/app/services/dashboard_service.py:63-101` and `:163-188` and `:365-382` build reasons for three different dashboard surfaces. Each references Bill, GroceryItem, Meal, PurchaseRequest. After B2 and B3, these imports must resolve to scout models. Since B2 and B3 only change `__table_args__`, existing imports continue to work. Stop condition: if any service imports by raw table name string (grep `\"meals\"`, `\"grocery_items\"`), flag for patch.

### 10.8 `public.meal_plans` deprecation may surprise integrators

`backend/app/routes/meals.py:35-71` still exposes `/meal-plans` endpoints. Frontend does not call them (`grep '/meal-plans' scout-ui/` returns only `/admin/meals/staples/new`, a different route). Safer to delete routes in B2 rather than B5 to flush them from the OpenAPI spec early. Stop if external integrators exist.

### 10.9 Production row counts are a 2026-04-21 snapshot

The audit states grocery_items=2, purchase_requests=1, bills=0, all meals tables=0. Before B3 deploy, re-query production. If grocery_items growth is non-trivial (say >50 rows), upgrade migration from straight INSERT-SELECT to a batched copy to avoid long locks. Stop condition threshold: 1000 rows.

### 10.10 `scout.meal_transformations` is an orphan

Created in migration 044, FKs into public.meals. After B2 splits public.meals into staples+entries, those FKs dangle. Current row count is 0 and no code references it. Options: (a) drop in B5; (b) re-FK to scout.meal_staples in B2 addendum. Recommend (a) and let Andrew confirm meal_transformations is not a dormant feature.

---

## Open questions

1. Is `public.meals` create path actually used as a staple-only registry, or is there undocumented calendar usage? Need `grep '\\bcreate_meal(' backend/` plus a production row sample to confirm.
2. Does Andrew want bills canonical in this slice, or deferred to a dedicated finance sprint? Plan assumes deferred (B1 only).
3. Is `scout.meal_transformations` live/planned or dead code? Zero evidence of use. Recommend drop.
4. Should the dual-write trigger in B3 live on scout.grocery_items (catches legacy writers) or public.grocery_items (catches new writers)? Recommend public, because the only risk is a lingering caller. After 7 days, drop the trigger and DROP the public table in B5.
5. Do any production nudge rules reference `bills`, `grocery_items`, or `meals` today? If yes, B4 must ship before B2/B3 (validator can accept both public and scout during transition). Need to check `scout.nudge_rules` content.
6. `weekly_meal_plan_entries` phantom in migration 044 - is this a planned table that never landed, or a leftover? Either way, it does not block B2.

---

End of Slice B plan.
