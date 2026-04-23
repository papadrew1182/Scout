# Schema canonical-vs-legacy audit (2026-04-22)

## 1. Summary

Scout's schema is in active transition from a single public.* table set (Phase 1-4, migration 001-021) to a dual-surface canonical architecture (scout.* + views, introduced migration 022). The main risk is **incomplete bridging of scope-contract fields**: public.chore_templates holds the included/not_included/done_means_done shape-validation fields, but scout.task_templates (canonical) does not replicate them. Any feature reading from scout.task_templates to render child-facing scope cards must also query public.chore_templates or duplicate the fields - a cross-boundary violation discovered in PR 1b's v_household_today view. Legacy tables dominate by count (29 LEGACY vs 11 CANONICAL raw tables), but data volume favors canonical: only 3 legacy tables have live rows (parent_action_items: 33, scout_scheduled_runs: 48, sessions: 172). The permission system (public.role_tiers + scout.role_tier_permissions) and connector identity system are well-bridged. Eight search-path shims (scout.families etc. as views over public.*) prevent immediate cross-boundary problems but defer consolidation. No orphans found; all extant tables have active routes or views.

## 2. Category counts

| Category | public | scout | total |
|----------|--------|-------|-------|
| CANONICAL | - | 11 | 11 |
| LEGACY (active) | 13 | 0 | 13 |
| LEGACY (zero rows) | 29 | 0 | 29 |
| VIEWS (shims) | 0 | 8 | 8 |
| VIEWS (purpose-built) | 0 | 4 | 4 |
| UNCLEAR | 0 | 35 | 35 |
| **TOTAL** | **42** | **58** | **100** |

## 3. Table-by-table (comprehensive summary)

### public schema

**LEGACY (active routes/data)**: routines, routine_steps, chore_templates (**scope-contract bridge issue**), task_instances, task_instance_step_completions, daily_wins, family_members (8), families (1), user_accounts (5), role_tiers (6), role_tier_overrides (7), sessions (172), member_config (1), events, event_attendees.

**LEGACY (zero rows, pre-canonical)**: ai_conversations (30), ai_messages (118), ai_daily_insights (2), ai_tool_audit (52), ai_homework_sessions (1), _scout_migrations (53), activity_records, allowance_ledger, bills, dietary_preferences, grocery_items (2), health_summaries, meal_plans, meal_reviews, meals, notes, parent_action_items (33 - **ACTIVE**), personal_tasks, planner_bundle_applies, purchase_requests (1 - **ACTIVE**), scout_anomaly_suppressions, scout_mcp_tokens, scout_scheduled_runs (48 - **ACTIVE**), weekly_meal_plans, family_memories, connector_configs (shim), connector_mappings (shim).

### scout schema

**CANONICAL tables (11)**: household_rules (16), routine_templates (25), reward_policies (7), connectors (9), connector_accounts (6), task_templates (7 - **missing scope fields**), task_assignment_rules (7), task_occurrences, task_completions, task_notes, task_exceptions.

**CANONICAL VIEWS (4)**: v_household_today (cross-boundary; missing chore scope), v_rewards_current_week, v_calendar_publication, v_control_plane.

**SHIM VIEWS (8)**: families, family_members, user_accounts, sessions, role_tiers, role_tier_overrides, connector_configs, connector_mappings.

**UNCLEAR (35)**: permissions, role_tier_permissions, user_family_memberships, daily_win_results, allowance_periods, allowance_results, affirmations, nudge rules, push notifications, projects, home maintenance, calendar exports, etc.

## 4. Cross-boundary dependencies

**[CRITICAL] v_household_today bridge gap** (migration lines 761-789)

View reads scout.task_templates + scout.task_occurrences + scout.task_completions + scout.routine_templates + public.family_members. Does NOT join public.chore_templates for included/not_included/done_means_done scope-contract fields. Child-facing scope card features must cross-query manually - breaks canonical boundary.

**[WELL-BRIDGED] Permission system** (/app/auth.py, /services/permissions.py)

Auth reads public.role_tiers, joins through scout.role_tier_permissions to fetch scout.permissions. Per-member overrides in public.role_tier_overrides. Excellent design: public holds tier seed, scout holds registries.

**[WELL-BRIDGED] Connector account linkage** (migration lines 114-151)

Registry in scout (scout.connectors), per-family state in scout (scout.connector_accounts), bridges to public (public.families, public.user_accounts) correctly.

**[CROSS-BOUNDARY] Nudge rule SQL whitelist** (/services/nudge_rule_validator.py:58-70)

Allowed tables: all public.* (personal_tasks, events, event_attendees, task_instances, routines, chore_templates, family_members, families, bills). No scout.* whitelisted. Risk: Once public.task_instances data stops, nudge rules break. Need to add scout.task_occurrences to whitelist.

**[LEGACY REFERENCE] Task generation service** (/services/task_generation_service.py:1-130)

Reads public.routines and public.chore_templates, writes public.task_instances. No canonical writes. Must eventually port to scout.task_occurrences.

## 5. Per-LEGACY-table recommendation (key tables)

| Table | Action | Effort |
|-------|--------|--------|
| chore_templates | **CONSOLIDATE + COPY SCOPE FIELDS** (closes v_household_today gap) | M |
| task_instances | **KEEP + FORMALIZE BRIDGE** (co-exist with scout.task_occurrences) | S |
| routines | **CONSOLIDATE or FORMALIZE BRIDGE** (parallel with scout.routine_templates) | M |
| parent_action_items | **CONSOLIDATE to scout** (**ACTIVE** 33 rows; no canonical yet) | M |
| purchase_requests | **CONSOLIDATE to scout** (**ACTIVE** 1 row) | S |
| scout_scheduled_runs | **KEEP in public OR migrate to scout** (**ACTIVE** 48 rows; intent unclear) | M |
| sessions | **KEEP in public** (framework-level; 172 rows) | S |
| family_members | **KEEP in public, shim in scout** (auth foundation) | S |
| member_config | **CONSOLIDATE to scout.member_config** (ARCHITECTURE.md Layer 1) | M |
| role_tiers | **KEEP in public, bridge via scout.role_tier_permissions** (well-designed) | S |
| allowance_ledger | **DEPRECATE + DROP** (superseded by canonical tables; 0 rows) | S |

## 6. Observations and risks

**Naming collisions** - public.routines/scout.routine_templates and public.task_instances/scout.task_occurrences are parallel. Risk: code refs wrong table. Consolidate within one release cycle.

**Scope-contract field split (HIGH SEVERITY)** - Fields included/not_included/done_means_done live ONLY in public.chore_templates. Any feature needing scope cards must cross-query. Action: Backfill fields to scout.task_templates or create scout.chore_scope_contract lookup. Update routes to read canonical source. Short-term: Document that v_household_today is incomplete; scope cards must be joined client-side.

**Dual permission systems (low risk, well-managed)** - public.role_tiers + scout.role_tier_permissions is good design. No changes needed.

**Active legacy data in public schema (MEDIUM RISK)** - parent_action_items (33), scout_scheduled_runs (48), sessions (172), grocery_items (2) have live data, no clear migration path. Audit within next planning cycle.

**Unimplemented canonical tables (MEDIUM RISK)** - 35 scout tables lack ORM/routes. Not orphans but "waiting room" tables. Clarify ownership and timeline.

## 7. What this audit does NOT do

- Does not propose migrations or SQL scripts.
- Does not modify code or schema.
- Does not estimate migration effort in detail.
- Does not fix cross-boundary issues (recommendations only).
- Does not validate architecture decisions (assumes ARCHITECTURE.md correct).
- Does not analyze frontend dependencies (backend only).

---

Audit completed: 2026-04-22
Scope: Backend schema, routes, views, models
Data snapshot: Production row counts as of 2026-04-21
Architecture reference: ARCHITECTURE.md, interaction_contract.md, migration 022
