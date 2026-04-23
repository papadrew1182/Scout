# Scout canonical rewrite - v5 pre-flight facts

**Prepared:** 2026-04-23
**Scope:** Pure-facts retrieval for the v5 sprint plan. Not planning, not execution.
**Method:** Grep + read of `backend/migrations/` (001-052), `backend/app/`, `scout-ui/`, `.github/workflows/`, `scripts/`.
**Status:** Advisory. Stand down for v5 rewrite.

No architectural commentary. Tables and file:line citations only.

---

## Part 1 - Retained-table FK dependency matrix

Scope: 25 scout.* tables that v4 Phase 1 PR 1.3 keeps, plus Phase 2 keep-as-is tables.

| scout.* table | FKs OUT (target) | FKs IN (source) | Points at rebuilt? | Action |
|---|---|---|---|---|
| `nudge_dispatches` | `family_member_id` -> public.family_members; `parent_action_item_id` -> public.parent_action_items; `push_delivery_id` -> scout.push_deliveries | nudge_dispatch_items.dispatch_id | yes (family_members + parent_action_items both rebuilt) | drop FK + recreate after rebuild |
| `nudge_dispatch_items` | `dispatch_id` -> scout.nudge_dispatches; `family_member_id` -> public.family_members | - | yes (family_members) | drop FK + recreate |
| `nudge_rules` | `family_id` -> public.families; `created_by_family_member_id` -> public.family_members | - | yes (both rebuilt) | drop FK + recreate |
| `quiet_hours_family` | `family_id` -> public.families (UNIQUE) | - | yes (families) | drop FK + recreate |
| `push_devices` | `family_member_id` -> public.family_members | push_deliveries.push_device_id | yes | drop FK + recreate |
| `push_deliveries` | `family_member_id` -> public.family_members; `push_device_id` -> scout.push_devices | nudge_dispatches.push_delivery_id | yes (family_members) | drop FK + recreate |
| `home_zones` | `family_id` -> public.families | home_assets.zone_id; maintenance_templates.zone_id | yes | drop FK + recreate |
| `home_assets` | `family_id` -> public.families; `zone_id` -> scout.home_zones | maintenance_templates.asset_id | yes (families) | drop FK + recreate |
| `maintenance_templates` | `family_id` -> public.families; `zone_id` -> scout.home_zones; `asset_id` -> scout.home_assets; `default_owner_member_id` -> public.family_members | maintenance_instances.template_id | yes | drop 2 FKs + recreate |
| `maintenance_instances` | `family_id` -> public.families; `template_id` -> scout.maintenance_templates; `owner_member_id` -> public.family_members; `completed_by_member_id` -> public.family_members | - | yes | drop 3 FKs + recreate |
| `affirmations` | `created_by` -> public.family_members; `updated_by` -> public.family_members | affirmation_feedback.affirmation_id; affirmation_delivery_log.affirmation_id | yes | drop 2 FKs + recreate |
| `affirmation_feedback` | `family_member_id` -> public.family_members; `affirmation_id` -> scout.affirmations | - | yes (family_members) | drop FK + recreate |
| `affirmation_delivery_log` | `family_member_id` -> public.family_members; `affirmation_id` -> scout.affirmations | - | yes (family_members) | drop FK + recreate |
| `connectors` | none | connector_accounts.connector_id | no | no action |
| `connector_accounts` | `connector_id` -> scout.connectors; `family_id` -> public.families; `user_account_id` -> public.user_accounts | sync_jobs.*; sync_cursors.*; connector_event_log.*; stale_data_alerts.* | yes (families, user_accounts) | drop 2 FKs + recreate |
| `household_rules` | `family_id` -> public.families | - | yes | drop FK + recreate |
| `reward_policies` | `family_id` -> public.families; `family_member_id` -> public.family_members | allowance_results.reward_policy_id | yes | drop 2 FKs + recreate |
| `permissions` | none | role_tier_permissions.permission_id | no | no action |
| `role_tier_permissions` | `role_tier_id` -> public.role_tiers; `permission_id` -> scout.permissions | - | yes (role_tiers) | drop FK + recreate |
| `user_family_memberships` | `user_account_id` -> public.user_accounts; `family_id` -> public.families; `family_member_id` -> public.family_members; `role_tier_id` -> public.role_tiers | - | yes (all 4) | drop 4 FKs + recreate |
| `user_preferences` | `user_account_id` -> public.user_accounts | - | yes | drop FK + recreate |
| `device_registrations` | `user_account_id` -> public.user_accounts | - | yes | drop FK + recreate |
| `task_assignment_rules` | `task_template_id` -> scout.task_templates | - | yes (task_templates rebuilt) | drop FK + recreate (OR rebuild this table too) |
| `task_completions` | `task_occurrence_id` -> scout.task_occurrences; `completed_by` -> public.family_members | - | yes (both rebuilt) | drop 2 FKs + recreate (OR rebuild) |
| `task_notes` | `task_occurrence_id` -> scout.task_occurrences; `author_id` -> public.family_members | - | yes | drop 2 FKs + recreate (OR rebuild) |
| `task_exceptions` | `task_occurrence_id` -> scout.task_occurrences; `created_by` -> public.family_members | - | yes | drop 2 FKs + recreate (OR rebuild) |

**Summary:** 23 of 26 retained tables have FKs that need drop-and-recreate after Phase 2 rebuilds.

**Only 3 fully self-contained (no rebuild-pointing FKs):** scout.connectors, scout.permissions, scout.nudge_dispatch_items (points at other kept tables only).

**scout.task_assignment_rules / task_completions / task_notes / task_exceptions:** all FK scout.task_templates and/or scout.task_occurrences, both of which v4 rebuilds. Drop and recreate the FKs, OR include these 4 tables in the Phase 2 rebuild set. Decision for v5.

---

## Part 2 - Seed / reference vs user data categorization

| scout.* table | Category | Seed source (if SEED_REFERENCE) |
|---|---|---|
| `permissions` | SEED_REFERENCE | `022_session2_canonical.sql:880-894` (seed), then extended by 034, 040, 043, 046a, 046b, 047, 048, 049, 050, 051. 45 INSERT statements across 13 migrations. |
| `role_tier_permissions` | SEED_REFERENCE | `022_session2_canonical.sql:898-929` (seed), extended by 034, 040, 043, 046a, 046b, 047, 048, 049, 050, 051. |
| `connectors` | SEED_REFERENCE | `022_session2_canonical.sql:933-948`. 9 connector rows. |
| `household_rules` | SEED_REFERENCE (Roberts-specific) | `023_session2_roberts_seed.sql:97` (family-scoped) + `035_consolidate_family_config.sql:17` (consolidation from removed family_config). 16 rows. |
| `reward_policies` | USER_DATA (seeded for Roberts) | `023_session2_roberts_seed.sql:528,539,550`. Seed is family-specific. Post-truncate, Andrew re-creates via admin UI OR re-runs 023 seed. |
| `affirmations` | SEED_REFERENCE | `039_affirmations.sql:75-108`. 25 starter affirmations (audience_type='general', tone categories encouraging/gentle/etc.). |
| `nudge_rules` | USER_DATA | No seed. Parent-authored only. |
| `quiet_hours_family` | USER_DATA | No seed. Per-family configuration. |
| `nudge_dispatches` | EPHEMERAL | No seed. Written by scanner/rule engine. |
| `nudge_dispatch_items` | EPHEMERAL | No seed. |
| `push_devices` | USER_DATA | No seed. Registered on app launch. |
| `push_deliveries` | EPHEMERAL | No seed. Delivery log. |
| `affirmation_feedback` | USER_DATA | No seed. User reactions. |
| `affirmation_delivery_log` | EPHEMERAL | No seed. Analytics trail. |
| `home_zones` | USER_DATA | Some via `backend/seed_smoke.py:332` (smoke-tests only). |
| `home_assets` | USER_DATA | No seed. |
| `maintenance_templates` | USER_DATA | No seed. |
| `maintenance_instances` | USER_DATA / EPHEMERAL | No seed (schedule generates). |
| `connector_accounts` | USER_DATA | No seed. Per-family OAuth state. |
| `user_family_memberships` | USER_DATA | No seed. Designed; unwired today. |
| `user_preferences` | USER_DATA | No seed. |
| `device_registrations` | USER_DATA | No seed. |
| `task_assignment_rules` | USER_DATA | `023_session2_roberts_seed.sql` (Roberts-specific if any). |
| `task_completions` | USER_DATA | No seed. |
| `task_notes` | USER_DATA | No seed. |
| `task_exceptions` | USER_DATA | No seed. |

**SEED_REFERENCE tables that MUST be reseeded after truncate:**
1. `scout.permissions` - seed sources: migrations 022, 034, 040, 043, 046a, 046b, 047, 048, 049, 050, 051. If truncated, every permission check returns "unknown permission" and every authorization call fails.
2. `scout.role_tier_permissions` - same migration set. If truncated, all role_tiers resolve to zero permissions.
3. `scout.connectors` - `022:933`. If truncated, connector_accounts FK-validates against empty registry.
4. `scout.affirmations` - `039:75`. If truncated, affirmation UI has nothing to show.
5. `scout.household_rules` - `023:97` + `035:17`. Family-specific, but without seeds, rule-dependent features break.

**Note:** Reseeding via migration re-run is NOT SAFE because the migration tracker (`public._scout_migrations`) already records them as applied. Options: (a) manual INSERT script at Phase 5; (b) new migration NNN that copies INSERT statements from the originals; (c) `pg_dump` the seed data from current production into a restore-script.

---

## Part 3 - Existence and usage resolution

| scout.* table | Exists in schema? | Active code references | v5 decision needed |
|---|---|---|---|
| `member_config` | **NO** | `public.member_config` exists and is active. Referenced in `backend/app/services/ai_personality_service.py:146,150,190` (raw SQL), `backend/app/routes/admin/config.py:29,31,132`, `backend/app/routes/affirmations.py:124`, `backend/app/models/access.py:56` (ORM `__tablename__ = "member_config"` no scout schema), `backend/app/ai/personality_defaults.py:11,24`, `backend/app/ai/context.py:338`, `backend/app/models/quiet_hours.py:20` (comment only). | **Build fresh** in Phase 2 OR keep `public.member_config` and truncate. v4 assumes scout.* exists; it does not. |
| `calendar_exports` | yes (`022_session2_canonical.sql:411`) | Referenced in 8 backend files (models, routes, services). | Keep. |
| `greenlight_exports` | yes (`022_session2_canonical.sql:553`) | Referenced only in `backend/app/routes/canonical.py`. 5 grep hits total for scout.greenlight_exports. Minimal active use. | Keep (harmless); consider drop candidate for a future sprint. |
| `time_blocks` | yes (`022_session2_canonical.sql:396`) | Seeded at `023_session2_roberts_seed.sql:148` (Roberts-specific). Active reader at `backend/app/routes/canonical.py:124-130` (`SELECT FROM scout.time_blocks` to resolve active block). | Keep + re-seed post-truncate (SEED_REFERENCE). |
| `project_templates` | yes (`047_family_projects.sql:9`) | Referenced in `backend/app/models/projects.py`, `backend/app/routes/projects.py`, `backend/app/routes/project_templates.py`, `backend/app/services/project_aggregation.py`, `backend/app/ai/tools.py`. Active. | Keep. |
| `project_template_tasks` | yes (`047:33`) | Same route surface. | Keep. |
| `projects` | yes (`047:55`) | Same route surface. | Keep. |
| `project_tasks` | yes (`047:83`) | Same route surface. `public.personal_tasks.source_project_task_id` FKs this table (`047:151-153`). | Keep. |
| `project_milestones` | yes (`047:111`) | Active. | Keep. |
| `project_budget_entries` | yes (`047:130`) | Active. | Keep. |

**Critical mismatch:** `scout.member_config` is referenced in v4 Phase 2 PR 2.1 as an identity-domain table to rebuild. **It does not exist today.** The live table is `public.member_config` (migration 024), and all writers target the unqualified name `member_config` which resolves to `public` via search_path. v5 must decide: (a) create `scout.member_config` fresh in Phase 2 AND update all writers, or (b) keep `public.member_config` and truncate in Phase 1.

---

## Part 4 - Phase 1 view-drop ordering

### 4.1 Shim views and their sources

All 8 shim views defined in `022_session2_canonical.sql:183-190`:

| View | Definition | Line |
|------|------------|------|
| `scout.families` | `CREATE OR REPLACE VIEW scout.families AS SELECT * FROM public.families` | 183 |
| `scout.family_members` | `CREATE OR REPLACE VIEW scout.family_members AS SELECT * FROM public.family_members` | 184 |
| `scout.user_accounts` | `CREATE OR REPLACE VIEW scout.user_accounts AS SELECT * FROM public.user_accounts` | 185 |
| `scout.sessions` | `CREATE OR REPLACE VIEW scout.sessions AS SELECT * FROM public.sessions` | 186 |
| `scout.role_tiers` | `CREATE OR REPLACE VIEW scout.role_tiers AS SELECT * FROM public.role_tiers` | 187 |
| `scout.role_tier_overrides` | `CREATE OR REPLACE VIEW scout.role_tier_overrides AS SELECT * FROM public.role_tier_overrides` | 188 |
| `scout.connector_mappings` | `CREATE OR REPLACE VIEW scout.connector_mappings AS SELECT * FROM public.connector_mappings` | 189 |
| `scout.connector_configs` | `CREATE OR REPLACE VIEW scout.connector_configs AS SELECT * FROM public.connector_configs` | 190 |

Additional view re-creations:
- `024_permissions_and_config.sql:42` - `scout.role_tiers` re-created after schema widening.
- `024_permissions_and_config.sql:87` - `scout.role_tier_overrides` re-created.

### 4.2 Ordering verdict

**ChatGPT's flag is correct.** All 8 shim views have `scout.X AS SELECT * FROM public.X` dependency on public tables. Postgres DROP TABLE on a view's source table fails with:

```
ERROR:  cannot drop table public.families because other objects depend on it
DETAIL:  view scout.families depends on table public.families
HINT:  Use DROP ... CASCADE to drop the dependent objects too.
```

v4 PR 1.3 (drop views) MUST run before PR 1.2 (drop tables). Current v4 order is backward. Swap to: **PR 1.2 = drop views, PR 1.3 = drop tables.**

Alternative: drop table with CASCADE (auto-drops dependent views), but this hides the view drop and is harder to audit.

### 4.3 Other dependent objects on public.* tables

From Part 5 findings (triggers on drop-list tables):

- 23 `updated_at` triggers on public.* tables. Auto-dropped when their parent table drops. No manual action needed.
- 2 triggers on connector tables (connector_mappings, connector_configs). Those tables are on the drop list; triggers drop with them.

### 4.4 Recursive FK blockers (from Part 5 data)

Some public.* tables have FK RESTRICT dependencies that block plain DROP TABLE:

- `public.routines` is RESTRICT-referenced by `public.task_instances.routine_id` and `public.routine_steps.routine_id` (via CASCADE path).
- `public.chore_templates` is RESTRICT-referenced by `public.task_instances.chore_template_id`.
- `public.task_instances` is RESTRICT-referenced by `public.task_instance_step_completions.routine_step_id` path.
- `public.routine_steps` is RESTRICT-referenced by `public.task_instance_step_completions.routine_step_id`.

Order for DROP TABLE statements within Phase 1:
1. `task_instance_step_completions` (no dependents)
2. `task_instances` (only references routines/chore_templates)
3. `routine_steps`
4. `routines`
5. `chore_templates`
6. Other independent tables in any order.

For parent_action_items: scout.nudge_dispatches FKs `parent_action_item_id` with ON DELETE SET NULL - safe to drop parent_action_items; scout rows get NULL.

For ai_conversations: multiple SET NULL FKs from ai_tool_audit, ai_homework_sessions, planner_bundle_applies, family_memories. CASCADE from ai_messages. Drop ai_messages first, then ai_conversations.

For purchase_requests / grocery_items / weekly_meal_plans: mutual SET NULL; safe to drop in any order within the group.

---

## Part 5 - DB-object audit beyond tables and views

### 5.1 Materialized views
**None found.**

### 5.2 Sequences and identity columns
**None found.** All PKs use `uuid DEFAULT gen_random_uuid()` (pgcrypto extension).

### 5.3 Custom enum / domain types
**None found.** All categorical fields use CHECK constraints with inline text values.

### 5.4 Schema-level grants
**None found.**

### 5.5 Generated columns
**None found.** No `GENERATED ALWAYS AS` or `GENERATED BY DEFAULT AS` clauses.

### 5.6 Functions and triggers

**Shared functions (KEEP - used by scout.* tables too):**

| File:Line | Function | Purpose |
|---|---|---|
| `001_foundation_connectors.sql:16` | `set_updated_at()` | Trigger helper; sets `NEW.updated_at = clock_timestamp()` |
| `022_session2_canonical.sql:146` | `public._connector_mappings_default_object_type()` | BEFORE INSERT helper on `public.connector_mappings` |

**Triggers on drop-list tables (auto-dropped with tables):**

23 `trg_<table>_updated_at` triggers on: routines, routine_steps, chore_templates, task_instances, daily_wins, events, event_attendees, meal_plans, meals, dietary_preferences, personal_tasks, notes, bills, health_summaries, activity_records, ai_conversations, grocery_items, purchase_requests, parent_action_items, weekly_meal_plans, family_memories. Plus trg_connector_mappings_default_object_type.

**Triggers on KEPT tables:**

- `trg_families_updated_at` (001:36) - on public.families (rebuilt, so gets dropped anyway)
- `trg_family_members_updated_at` (001:60)
- `trg_user_accounts_updated_at` (001:96)
- `trg_role_tiers_updated_at` (001:134)
- `trg_connector_configs_updated_at` (001:218) - on connector_configs (drop-list)
- `trg_role_tier_overrides_updated_at` (024:80) - on role_tier_overrides (rebuilt)
- `trg_family_config_updated_at` (024:107) - on public.family_config (exists? verify; may be deprecated by 035)
- `trg_member_config_updated_at` (024:129) - on public.member_config (drop-list per v4, OR kept per Part 3 ambiguity)
- `trg_nudge_dispatches_updated_at` (049:57) - on scout.nudge_dispatches (KEEP)
- `trg_quiet_hours_family_updated_at` (050:50) - on scout.quiet_hours_family (KEEP)
- `trg_nudge_rules_updated_at` (051:69) - on scout.nudge_rules (KEEP)

Scout-schema triggers on KEEP tables are preserved; they depend only on `set_updated_at()` which is not dropped.

### 5.7 Critical FK RESTRICT dependencies (prevent plain DROP)

| Child table (blocks drop of...) | References | Delete action |
|---|---|---|
| public.task_instances.routine_id | public.routines | RESTRICT |
| public.task_instances.chore_template_id | public.chore_templates | RESTRICT |
| public.task_instance_step_completions.routine_step_id | public.routine_steps | RESTRICT |

All other FKs to drop-list tables use CASCADE or SET NULL. Only these three RESTRICT constraints require explicit child-deletion before parent DROP.

### 5.8 Cross-schema FKs from scout.* to drop-list public.*

From Part 1: 19 of 25 retained scout.* tables FK public.families or public.family_members. These FKs must drop before Phase 1 table drops (or the drops fail).

Additional cross-schema FK not surfaced in Part 1:

| FK source | FK target | File:line | Action |
|---|---|---|---|
| scout.meal_transformations.base_staple_id | public.meals | 044:16 CASCADE | If scout.meal_transformations retained: drop FK first. Otherwise drop scout.meal_transformations. |
| scout.meal_transformations.transformed_staple_id | public.meals | 044:17 CASCADE | Same. |
| scout.nudge_dispatches.parent_action_item_id | public.parent_action_items | 049:35 SET NULL | Drop FK before dropping public.parent_action_items. |

scout.meal_transformations status: v3 Q7 said drop; v4 should confirm.

---

## Part 6 - External writer inventory

### 6.1 Inbound webhooks - none

No real webhooks. Two auth-gated "ingest" routes exist but require a bearer token:
- `POST /api/integrations/google-calendar/ingest` (`backend/app/routes/integrations.py:50-58`) - writes `events`, `connector_mappings`. Auth required.
- `POST /api/integrations/ynab/ingest` (`integrations.py:61-69`) - writes `bills`, `connector_mappings`. Auth required.

Comment at `integrations.py:3-5` states: "There is no auth, no scheduling, no webhook receiving."

### 6.2 Third-party callbacks - none

- No OAuth callback routes.
- No Supabase Storage webhooks (only signed-URL uploads, auth-gated).
- No Expo push receipt callbacks.
- No Stripe / payment webhooks.
- Google Calendar / YNAB integrations are mocks.
- Apple Health file exists (`backend/app/services/apple_health.py`) but not wired into scheduler or routes.
- No Greenlight callbacks.

### 6.3 GitHub Actions writes to prod

Source: `.github/workflows/ci.yml`.

Triggers: `push` to main / release-* / release/**, `pull_request` to main, `workflow_dispatch` manual.

Jobs:
- **smoke-deployed** (lines 154-196): Fires on push-to-main (auto) OR workflow_dispatch. Targets `SCOUT_WEB_URL` and `SCOUT_API_URL` (default Vercel + Railway URLs). Default test list at line 21: `tests/auth.spec.ts tests/surfaces.spec.ts tests/responsive.spec.ts tests/dev-mode.spec.ts`. Comment at lines 8-10 claims these are "no write paths against prod". Secrets: `SCOUT_SMOKE_ADULT_EMAIL/PASSWORD`, `SCOUT_SMOKE_CHILD_EMAIL/PASSWORD` (lines 165-168).
- **backend-tests** (lines 32-57): local postgres service, no prod writes.
- **frontend-types** (lines 59-69): no writes.
- **arch-check** (lines 71-88): artifact only.
- **smoke-web** (lines 90-152): local services, no prod writes.

Only smoke-deployed can reach prod. Auto-runs on push-to-main.

### 6.4 Local scripts in /scripts

Scripts directory: `scripts/` (4 Python files + architecture-check.js).

| File | DB writer? | Prod target? |
|---|---|---|
| `ai_cost_report.py` | no | n/a |
| `architecture-check.js` | no | n/a |
| `provision_smoke_child.py` | **yes** | Railway prod via `SCOUT_DATABASE_URL`. Writes `family_members`, `user_accounts`, `role_tier_overrides`; reads `role_tiers`. Operator-run only (no cron). |
| `release_check.py` | no | n/a |
| `wait_for_url.py` | no | n/a |

Additional script: `backend/seed_smoke.py` writes smoke-tests seed data including home zones. Operator-run.

### 6.5 Mobile/web auto-sync

Source: `scout-ui/lib/push.ts` and `scout-ui/app/`.

**Push token registration on app launch:** `scout-ui/lib/push.ts:282-354` (`usePushRegistration` hook) requests permission, gets Expo push token, calls `registerPushDevice` which POSTs `/api/push/devices` (auth-gated). **Fires on every app open.** Writes `scout.push_devices`.

**Push tap recording:** `scout-ui/app/` subscribes to `Notifications.addNotificationResponseReceivedListener`; on tap posts `/api/push/deliveries/{delivery_id}/tap`. Writes `scout.push_deliveries`.

**Periodic polling / setInterval:** grep found no `setInterval` with network calls in `scout-ui/app/`. `useEffect` data fetches only run on screen mount / user action.

**Service worker:** none. Expo React Native, not PWA.

### 6.6 Additional external-writer endpoints

- `POST /api/client-errors` (`backend/app/routes/client_errors.py:70-96`) - logs only, no DB write. Auth optional.
- `POST /families/{id}/health/summaries` (`backend/app/routes/health_fitness.py:50-91`) - writes `health_summaries`, `activity_records`. Auth-gated. User-initiated only.
- `POST /mcp/tokens`, `POST /mcp/tools/call` (`backend/app/routes/mcp_http.py`) - MCP bridge for Claude Desktop. sha256 bearer auth. Operator-initiated only.

### 6.7 Writers that could fire during maintenance window

| Writer | Likely during Phase 1-3? | Mitigation available |
|---|---|---|
| Scheduler (8 jobs) | No, if `SCOUT_SCHEDULER_ENABLED=false` | env var flip (already planned) |
| smoke-deployed CI | Yes, every push to main | Disable workflow_dispatch + remove main auto-trigger; OR verify test files are read-only |
| scout-ui push token register | Yes, on every app open | Close app before Phase 1; OR accept low-volume writes to push_devices (then truncate again in Phase 5) |
| scout-ui push tap | Yes, if user taps an old notification | Accept; truncate push_deliveries in Phase 5 |
| Supabase Storage upload | Yes, if user uploads | User-initiated; don't upload during window |
| MCP HTTP | Yes, if Claude Desktop calls | Don't call during window |
| provision_smoke_child.py | No, operator-run | Operator discipline |
| backend/seed_smoke.py | No, operator-run | Operator discipline |
| Google Calendar / YNAB ingest | No, auth-gated + manual | Don't call during window |
| Health summaries | No, user-initiated | Don't enter data during window |
| Client error reports | Maybe, logs only | Accept (no DB write) |

---

## Part 7 - Zero-row verification method

### 7.1 Why `pg_stat_user_tables.n_live_tup` is wrong

`pg_stat_user_tables.n_live_tup` is maintained by the statistics collector, which updates asynchronously. After `TRUNCATE`, the stat may not reflect zero for up to `track_activity_query_size`-dependent intervals (default several minutes). Relying on this for "is it truly empty" gives false positives.

### 7.2 Exact verification method

**Primary method:** `SELECT COUNT(*) FROM <table>` per table of interest. Definitive. Slow only if tables are large; Scout tables are small (max 172 rows on public.sessions pre-truncate).

**Batched verification SQL template:**

```sql
SELECT 'public.<table_a>' AS target, COUNT(*) AS live_rows FROM public.<table_a>
UNION ALL
SELECT 'public.<table_b>', COUNT(*) FROM public.<table_b>
UNION ALL
SELECT 'scout.<table_c>', COUNT(*) FROM scout.<table_c>
ORDER BY target;
```

Any row with `live_rows > 0` is a failure.

**Where to run:** inside the same transaction as the TRUNCATE, before COMMIT, to ensure atomicity. If any count is non-zero, ROLLBACK and investigate before retrying.

**Alternative (faster but approximate):** `SELECT pg_relation_size(oid), reltuples FROM pg_class WHERE relnamespace IN (schema_oids) AND relkind = 'r'`. After `VACUUM ANALYZE`, `reltuples` is usually accurate. Still slower guarantee than COUNT(*).

**Do NOT use:**
- `pg_stat_user_tables.n_live_tup` - asynchronous, stale after TRUNCATE.
- `information_schema.tables` - no row count.
- Postgres `ANALYZE` alone without SELECT - doesn't guarantee visibility in a concurrent transaction.

### 7.3 Recommended Phase 1 verification script

```sql
BEGIN;

-- Truncate drop-list tables in FK-safe order
TRUNCATE TABLE public.task_instance_step_completions CASCADE;
TRUNCATE TABLE public.task_instances CASCADE;
TRUNCATE TABLE public.routine_steps CASCADE;
-- ... etc

-- Verify all zero BEFORE drop
SELECT 'public.task_instances' AS t, COUNT(*) AS n FROM public.task_instances
UNION ALL SELECT 'public.routines', COUNT(*) FROM public.routines
-- ... etc
;
-- Review output; if any n > 0, ROLLBACK

COMMIT;
```

Then proceed to DROP in a separate migration.

---

## Part 8 - v3 open-questions status check

Verification of each of v3's 12 open questions per prompt.

| # | Question | Status | Notes |
|---|---|---|---|
| 1 | Orphan blobs decision | resolved | v4 §5 Phase 0 adds Supabase Storage purge step |
| 2 | AI quiesce strategy | resolved | Don't chat + optional `SCOUT_AI_ENABLED=false` documented |
| 3 | Bootstrap flag lifecycle | resolved | `SCOUT_ENABLE_BOOTSTRAP=true` before Phase 5, flip off after |
| 4 | Phase 5 checklist item #4 | resolved | Admin UI not Scout AI |
| 5 | Frontend token handling | resolved | Documented as expected 401 on first request |
| 6 | scout.standards_of_done | resolved | v4 Phase 2 PR 2.2 builds it |
| 7 | parent_action_items CHECK vocabulary | resolved | v4 Phase 2 includes full list |
| 8 | **Migration mirror for drops** | **see §8.1** | Confirmed: 53 files in `backend/migrations/` match 53 files in `database/migrations/`. Pattern applies equally to drop migrations. Every drop migration SQL must be mirrored at commit time. |
| 9 | scout_scheduled_runs truncate ordering | resolved | §3 note: after quiesce only |
| 10 | Smoke-disable mechanism | resolved | ci.yml edit |
| 11 | SCOUT_ENVIRONMENT vs SCOUT_ENABLE_BOOTSTRAP warning | documented | Warning at `backend/app/config.py:148-149` |
| 12 | **docs/handoffs/batch_1_cleanup_pattern.md exists** | **see §8.2** | **File does NOT exist at that literal path.** |

### 8.1 Migration mirror for drops (#8)

Current state: `backend/migrations/` has 53 files; `database/migrations/` has 53 files. Identical counts for migrations 001-052 (and 046a/046b).

Pattern confirmed: every SQL file committed in one directory must be committed in the other. For v5 drops:

- Each drop PR adds `backend/migrations/NNN_drop_*.sql` AND `database/migrations/NNN_drop_*.sql` in the same commit.
- Content is identical. The duplication is maintained for Railway vs local-dev runner parity.
- Arch-check does not enforce this mirror; house-rule enforcement only.

### 8.2 docs/handoffs/batch_1_cleanup_pattern.md existence (#12)

**File does not exist at that path.** Verified via `ls docs/handoffs/batch_1_cleanup_pattern.md` returns `No such file or directory`.

Existing files in `docs/handoffs/` (24 files total):
- 6 files `2026-04-19_phase_*_handoff.md`
- 5 files `2026-04-21_sprint_05_phase_*_nudges.md` / `_ai_resume.md` / `_push_notifications.md` / `_family_projects.md`
- 1 file `2026-04-20_session_handoff.md`
- 6 files `2026-04-22_batch_1_pr_*.md` (PRs 1, 2, 3, 4, 5)
- 1 file `2026-04-22_batch_1_stabilization.md`
- 2 files `2026-04-22_batch_2_pr_1a_` / `_1b_`
- 1 file `2026-04-22_sprint_05_phase_5_ai_discovery.md`
- (24th file omitted; grepped counter matches)

**Resolution:** v4 §12 references `docs/handoffs/batch_1_cleanup_pattern.md` as a file to re-read before starting. This file does not exist. The authoritative source is the memory entry `feedback_batch_cleanup_pattern.md` (stored in `C:\Users\rober\.claude\projects\C--Users-rober-onedrive-scout\memory\feedback_batch_cleanup_pattern.md`). v5 should either:
- (a) Create the missing docs/handoffs file by extracting the pattern from memory, OR
- (b) Update v4's §12 reference to point at the memory file path, OR
- (c) Drop the file reference and inline the 5 rules into v5 itself.

---

## Part 9 - Facts summary for v5 rewrite

**Green (v4 claims match reality):**
- Protected-tables rule implementable (no FK cascades to sessions or scout_scheduled_runs).
- Quiesce via `SCOUT_SCHEDULER_ENABLED=false` works; all 8 jobs stop.
- Migration mirror pattern verified (backend + database dirs match 53/53).

**Must-fix in v5:**
1. Swap PR 1.2 and PR 1.3 order: views drop before tables.
2. Add FK drop/recreate step for 23 retained scout.* tables pointing at rebuilt tables (details in Part 1).
3. SEED_REFERENCE tables need explicit re-seed step in Phase 5: `scout.permissions`, `scout.role_tier_permissions`, `scout.connectors`, `scout.affirmations`, `scout.household_rules`, `scout.time_blocks`. Re-running migrations is NOT safe; use copied INSERT statements or dump-restore.
4. Resolve `scout.member_config` ambiguity: either build fresh in Phase 2 or truncate `public.member_config` and leave in public. Current code writes unqualified `member_config` which resolves public.
5. Update file reference for `docs/handoffs/batch_1_cleanup_pattern.md` - file does not exist.
6. Disable `smoke-deployed` CI auto-trigger on main during Phase 1-3. Default test list is read-only per comment but the `workflow_dispatch` path allows custom test_files that could write.
7. Close scout-ui or block push device registration during Phase 1-3 window. App launches write `scout.push_devices` via `scout-ui/lib/push.ts:321`.

**Should-fix in v5:**
8. For Phase 1 drops, specify FK-safe DROP order: `task_instance_step_completions` -> `task_instances` -> `routine_steps` -> `routines` -> `chore_templates`; `ai_messages` -> `ai_conversations`; bundled others in any order.
9. Zero-row verification: use `SELECT COUNT(*)` in same transaction as TRUNCATE; don't rely on `n_live_tup`.
10. `scout.task_assignment_rules`, `scout.task_completions`, `scout.task_notes`, `scout.task_exceptions` FK rebuilt `scout.task_templates` and `scout.task_occurrences`. Decision: drop FK + recreate, or rebuild these 4 tables too. Current v4 plan keeps them.
11. `scout.meal_transformations` has CASCADE FKs to `public.meals`. If public.meals drops, meal_transformations loses data. Decision: drop it (per v3 Q7) or add to rebuild set.

**Nice-to-fix in v5:**
12. `scout.greenlight_exports` minimally used; candidate drop for future sprint.
13. `public.family_config` trigger exists at `024:107`; verify family_config table status (may be deprecated by migration 035).

---

End of pre-flight. No planning, no execution. Stand down for v5 rewrite.
