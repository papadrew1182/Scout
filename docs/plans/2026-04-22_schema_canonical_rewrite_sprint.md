# Schema Canonical Rewrite Sprint Plan

**Date:** 2026-04-22
**Planner:** Claude (main agent), synthesizing four parallel slice drafts
**Source drafts:** `docs/plans/_drafts/2026-04-22_canonical_rewrite_subagent_{A,B,C,D}.md`
**Baseline audit:** `docs/plans/2026-04-22_schema_canonical_audit.md`
**Architecture:** `docs/architecture/ARCHITECTURE.md`, `docs/architecture/interaction_contract.md`
**Status:** Proposal. Andrew decides in the morning. No execution before sign-off.

---

## 0. Executive summary

This is the synthesized sprint plan for finishing the scout canonical rewrite. It integrates four independently-planned slices (A chores/tasks/routines, B meals/grocery/home, C ai-chat/nudges/affirmations/push, D identity/permissions/connectors/framework) into one dependency-respecting PR ordering with explicit stop-conditions, per-PR risk and rollback, and a live-data preservation plan.

**Total PR count: 25.** Breakdown: A=8, B=5, C=5, D=7. No PRs reconcile away when merged - each slice's work is orthogonal on the code surface even where dependencies chain across slices.

**Sprint shape:**
- **Phase 0 (5 PRs, low risk, parallel-safe):** docs + labels + additive shims.
- **Phase 1 (6 PRs, mixed risk, partly parallel):** permission ORM foundation + additive scout.* DDL.
- **Phase 2 (1 PR, low-med risk):** member_config dry-run.
- **Phase 3 (1 PR, med risk):** scope-contract view closure - fixes the audit's HIGH-severity `v_household_today` gap.
- **Phase 4 (1 PR, med risk):** chore/routine backfill.
- **Phase 5 (2 PRs, HIGH risk):** nudge safety rails (security-critical whitelist + scanner dual-read).
- **Phase 6 (3 PRs, med risk, serial):** purchase_requests + grocery consolidation + nudge/AI tool refit for meals/grocery.
- **Phase 7 (1 PR, med-high risk):** parent_action_items consolidation (33 live rows, AI-orchestrator writer).
- **Phase 8 (2 PRs, HIGH risk):** task_instances shadow-write + canonical read cutover.
- **Phase 9 (4 PRs, mixed risk):** legacy retirement + shim cleanup.

**Three critical-path facts from synthesis:**

1. **"CANONICAL-in-public" is a category, not a compromise.** Slice C found that `public.ai_conversations` (30 rows), `public.ai_messages` (118 rows), `public.ai_tool_audit` (52 rows), `public.ai_daily_insights` (2), `public.ai_homework_sessions` (1) have no scout.* counterpart anywhere in migrations. Sprint 04 shipped features on these tables; sprint 05 deliberately did not migrate them. Proposal: promote the label to CANONICAL-in-public rather than migrate. This removes an entire migration work-stream from the sprint.

2. **Two hard cross-slice handshakes.** The sprint cannot progress past Phase 5 without the nudge safety rails. `backend/app/services/nudge_rule_validator.py:58-70` whitelists nine `public.*` tables; if Slice A's task_instances deprecation lands before Slice C extends the whitelist to include `scout.task_occurrences`, every chore-based nudge rule rejects silently at execution time. The scanner SQL at `nudges_service.py:193-206` is identical risk via a different code path. Both handshakes must resolve in Phase 5.

3. **Slice D defines the spine.** `D1` (ORM for scout.permissions + scout.role_tier_permissions) unblocks every slice's permission-key seeding. `D5` (purchase_requests move) unblocks Slice B's grocery consolidation via the FK. `D4` (parent_action_items, 33 rows + AI orchestrator writes) is the highest-risk Slice D work and must not collide with Slice B grocery work in the schedule.

**Three live-data tables that STAY PUT** despite being in `public`:
- `public.sessions` (172 rows, framework auth - any move logs users out).
- `public.scout_scheduled_runs` (48 rows, scheduler mutex - migration risks duplicate AI jobs + re-issued billing).
- `public._scout_migrations` (53 rows, migration tracker - touching it breaks the migration runner).

**Wall-clock estimate (serial deploy gates, solo operator):** 4-6 calendar days of focused execution. Parallel-aware lower bound: ~10-12 hours of pure execution (limited by deploy time), but the reality at Scout's pace (one operator, verify each deploy green before next serial PR, handoff doc per PR) is multi-day.

---

## 1. PR ordering (dependency-respecting)

Every PR is named `<slice><number>` for cross-reference. Every PR ends with `node scripts/architecture-check.js` clean and a Railway/Vercel green gate before the next serial PR starts (`feedback_verify_deploys.md` rule, and the batch-cleanup PR pattern in `feedback_batch_cleanup_pattern.md`).

### Phase 0 - Docs, labels, shims (5 PRs, fully parallel-safe)

| # | PR | Slice | Migration? | Unlocks |
|---|----|-------|------------|---------|
| 1 | D0 - docs: do-not-touch list for sessions / family_members / families / user_accounts / role_tiers / role_tier_overrides / _scout_migrations / scout_scheduled_runs | D | no | sibling-slice clarity |
| 2 | C1 - docs: promote public.ai_* to CANONICAL-in-public + ai_messages retention policy note | C | no | audit labeling fix |
| 3 | C4 - docs: mark scout.affirmations / push / scout_scheduled_runs as explicitly audited | C | no | audit labeling fix |
| 4 | C5 - migration-comment: parent_action_items.action_type contract note (COMMENT ON CONSTRAINT only) | C | yes (comment only) | multi-slice action_type coordination |
| 5 | B1 - feat: scout.bills shim view (KEEP+BRIDGE) | B | yes (additive) | Slice C reads; finance-slice future deferral |

Phase 0 can be a single "docs batch" PR or 5 individual PRs. Either works. No cross-slice dependencies within phase 0.

### Phase 1 - Permission foundation + additive scout.* DDL (6 PRs)

D1 must land first. D2 depends on D1. A1, A2, A3, B2 are parallel-safe with each other and with D2 (different migration numbers + different schema surfaces).

| # | PR | Slice | Migration? | Depends on | Unlocks |
|---|----|-------|------------|------------|---------|
| 6 | D1 - chore(orm): ORM models for scout.permissions + scout.role_tier_permissions | D | no | - | D2, and declarative permission seeding in A/B/C |
| 7 | D2 - chore(seeds): pre-seed permission keys for upcoming A/B/C consolidations (idempotent INSERT) | D | yes (seed) | D1 | clean seed ergonomics |
| 8 | A1 - schema: expand scout.task_templates with scope-contract fields (included, not_included, done_means_done, supplies, photo_example_path, estimated_duration_minutes, consequence_on_miss) | A | yes (additive) | D1 (optional) | A4, A5 |
| 9 | A2 - schema: scout.task_occurrences dispute columns + new scout.task_occurrence_step_completions + promote scout.routine_steps from UNCLEAR to CANONICAL | A | yes (additive) | D1 (optional) | A4, A5 |
| 10 | A3 - schema: scout.personal_tasks mirror (0-row lift) | A | yes (DDL only) | D1 (optional) | A7 |
| 11 | B2 - feat: canonical meals tables (scout.meal_weekly_plans, scout.meal_reviews, scout.meal_staples, scout.meal_plan_entries, scout.member_dietary_preferences); drops public.meal_plans (0-row, orphan endpoints) | B | yes (DDL + drop) | D1 (optional) | B3 grocery FK target, B4 AI tool refit |

### Phase 2 - Live-data dry-run (1 PR)

| # | PR | Slice | Migration? | Depends on | Unlocks |
|---|----|-------|------------|------------|---------|
| 12 | D3 - feat: move member_config to scout.member_config (1 row; atomic; forwarding view on public) | D | yes | D1, D2 | dry-run pattern for D4/D5 |

### Phase 3 - Close the v_household_today gap (1 PR)

| # | PR | Slice | Migration? | Depends on | Unlocks |
|---|----|-------|------------|------------|---------|
| 13 | A4 - service+view: extend canonical_household_service to materialize step completions + scope fields; update scout.v_household_today to join scope-contract columns from scout.task_templates | A | no (view `CREATE OR REPLACE` counts as DDL; no table change) | A1, A2 | A5, closes audit §6 HIGH gap |

### Phase 4 - Backfill chore + routine source data (1 PR)

| # | PR | Slice | Migration? | Depends on | Unlocks |
|---|----|-------|------------|------------|---------|
| 14 | A5 - data: backfill public.chore_templates + public.routines + public.routine_steps into scout.task_templates + scout.routine_templates + scout.routine_steps; keep-alive view on public.chore_templates for scope reads during transition | A | yes | A1, A2, A4 | A6 (needs scout routines populated) |

### Phase 5 - Nudge safety rails (2 PRs, HIGH risk; serial)

These two PRs are the gate for Phase 8 onward. Without them, any deprecation of `public.task_instances` / `public.routines` / `public.chore_templates` silently breaks nudges.

| # | PR | Slice | Migration? | Depends on | Unlocks |
|---|----|-------|------------|------------|---------|
| 15 | C2 - feat: nudge_rule_validator whitelist extension to scout.task_occurrences + scout.task_completions + scout.task_templates + scout.routine_templates; flip `_is_disallowed_schema` to per-table allow | C | no | A5 (scout populated first) | A6, A7, A8 |
| 16 | C3 - feat: built-in scanner dual-read bridge (scout.task_occurrences primary, public.task_instances fallback) behind `family_config['scout.task_occurrences.canonical']` flag | C | no | C2 | A6, A7, A8 |

### Phase 6 - Purchase + grocery move + nudge/AI tool refit for meals (3 PRs, serial)

| # | PR | Slice | Migration? | Depends on | Unlocks |
|---|----|-------|------------|------------|---------|
| 17 | D5 - feat: move purchase_requests to scout.purchase_requests; drop grocery_items.purchase_request_id FK (temporary) | D | yes | D3 | B3 |
| 18 | B3 - feat: canonical grocery consolidation (scout.grocery_items + scout.purchase_requests FK re-point); 2 rows + 1 row live data; dual-write trigger on public.grocery_items for one deploy cycle | B | yes | D5, B2 | B4, B5 |
| 19 | B4 - chore: nudge_rule_validator + AI tools refit for meals/grocery (extend whitelist with scout.meal_weekly_plans etc.; update `app/ai/tools.py` daily_brief and grocery tool) | B | no | B3 | B5 |

### Phase 7 - parent_action_items consolidation (1 PR)

| # | PR | Slice | Migration? | Depends on | Unlocks |
|---|----|-------|------------|------------|---------|
| 20 | D4 - feat: move parent_action_items to scout.parent_action_items (33 rows; atomic + forwarding view; 30-day legacy-rename retention); update ParentActionItem ORM `__table_args__` | D | yes | D3 | D-cleanup |

### Phase 8 - task_instances shadow-write + canonical read cutover (2 PRs, HIGH risk; serial)

| # | PR | Slice | Migration? | Depends on | Unlocks |
|---|----|-------|------------|------------|---------|
| 21 | A6 - data+code: backfill public.task_instances + public.task_instance_step_completions + public.daily_wins into scout.task_occurrences + scout.task_occurrence_step_completions + scout.daily_win_results; add canonical shadow-write INSIDE task_generation_service transaction | A | yes | A5, C2, C3 | A7 |
| 22 | A7 - cutover: canonical read path (dashboard_service.py, app/ai/tools.py, daily_wins.py, personal_tasks.py) behind feature flag for rollback | A | no | A6, C2, C3 (AI tool port) | A8 |

### Phase 9 - Retire legacy (4 PRs, serial but low contention)

| # | PR | Slice | Migration? | Depends on | Unlocks |
|---|----|-------|------------|------------|---------|
| 23 | A8 - cleanup: retire legacy generators (task_generation_service, daily_win_service); drop legacy routes; deprecate public.task_instances / public.chore_templates / public.routines / public.routine_steps / public.daily_wins via keep-alive views | A | yes (comments + view swaps) | A7, C2 | closes A slice |
| 24 | B5 - cleanup: drop public.meals + public.meal_plans + public.weekly_meal_plans + public.meal_reviews + public.dietary_preferences + public.grocery_items + public.purchase_requests (destructive, gated on Andrew sign-off + one-cycle dual-write observability) | B | yes (destructive) | B4 + 7-day observability window | closes B slice |
| 25 | Dc - cleanup: drop 8 unused scout shim views (scout.families, scout.family_members, scout.user_accounts, scout.sessions, scout.role_tiers, scout.role_tier_overrides, scout.connector_configs, scout.connector_mappings); drop public.connector_configs | D | yes (drops) | D4, D5 | closes D slice |

C5 was landed in Phase 0; no trailing C work needed.

---

## 2. Migration sequence graph

```
Phase 0 (docs/labels/shim):    [D0] [C1] [C4] [C5] [B1]        parallel
                                      |         |         |
Phase 1 (perm + additive):           D1 → D2                    serial
                                          |
                                     [A1] [A2] [A3] [B2]        parallel after D1

Phase 2 (dry-run):                        D3

Phase 3 (view close):                    A4                     (A1+A2+D3)

Phase 4 (chore backfill):                A5                     (A4)

Phase 5 (nudge rails):                   C2 → C3                (A5)

Phase 6 (grocery):                       D5 → B3 → B4           (C2+C3+B2)

Phase 7 (action items):                  D4                     (D3)

Phase 8 (task cutover):                  A6 → A7                (A5+C2+C3+D4)

Phase 9 (retire):                        A8 → B5 → Dc           (all prior)
```

**Migration number plan:** current highest is `023_session2_roberts_seed.sql` plus Sprint 05's `049_nudge_engine.sql` / `050_nudge_quiet_hours_and_batching.sql` / `051_nudge_rules.sql` / `052_normalize_046_collision.sql`. The 041, 042, 043, 044, 045, 046a, 046b, 048 migrations exist from intervening sprints. Next available: **053**. Allocate 053-075 for this sprint (25 PRs; not all need migrations, so the range suffices). Reserve exact numbers at commit time to avoid collisions with concurrent work.

**Migration mirroring:** every file in `backend/migrations/` must be mirrored in `database/migrations/` (the audit's §1 observation and Slice A's §10.5 reiterate this). Each PR's checklist includes "mirror verified."

---

## 3. Per-PR detail (risk, rollback, scope)

Compact per-PR spec. Each PR references its slice draft for full depth.

| # | PR | Risk | Rollback | Smoke gate |
|---|----|------|----------|------------|
| 1 | D0 docs | low | revert | arch-check clean |
| 2 | C1 docs | low | revert | arch-check clean |
| 3 | C4 docs | low | revert | arch-check clean |
| 4 | C5 comment-only | low | revert | arch-check clean |
| 5 | B1 scout.bills shim | low | `DROP VIEW scout.bills` | existing bills tests |
| 6 | D1 ORM models | low | revert branch (no schema) | new test_permissions_orm.py + backend-tests |
| 7 | D2 seed perms | low | `DELETE FROM scout.permissions WHERE key IN (...)` scoped | test_canonical_session2_block3 |
| 8 | A1 expand task_templates | low | `ALTER TABLE ... DROP COLUMN` (no writers yet) | test_chore_templates (assert round-trip) |
| 9 | A2 dispute cols + step completions + promote routine_steps | low | DROP COLUMN / DROP TABLE | test_canonical_session2_block2 |
| 10 | A3 scout.personal_tasks | low | `DROP TABLE scout.personal_tasks` | new test_canonical_personal_tasks |
| 11 | B2 canonical meals | low | `DROP TABLE scout.meal_* CASCADE` + revert model flips; restore `/meal-plans` route if removed | test_weekly_meal_plans + test_meals_routes |
| 12 | D3 member_config move | low-med | drop view + rename legacy back + DROP TABLE scout.member_config | test_member_config_scout + smoke ai-personality.spec.ts |
| 13 | A4 v_household_today + service update | medium | revert view DDL to 022 body; revert service diff | test_v_household_today_surfaces_scope_fields (new) |
| 14 | A5 backfill chore/routines | medium | TRUNCATE scoped on `template_key LIKE 'legacy_%'` etc.; origin rows remain in public | test_canonical_backfill_chores (new) |
| 15 | C2 nudge validator whitelist | **high** | revert validator; edit any scout.* rules to public.* or deactivate | test_nudge_rule_validator expanded attack suite |
| 16 | C3 scanner dual-read | **high** | flip `scout.task_occurrences.canonical` feature flag OFF for all families | new dual-read tests for scan_missed_routines / scan_overdue_tasks |
| 17 | D5 purchase_requests move | medium | rename legacy back + re-add grocery_items FK | test_grocery end-to-end |
| 18 | B3 grocery consolidation | medium | flip model `__table_args__` back to public (scout tables become orphan 2 rows, harmless) | smoke write-paths.spec.ts + new canonical-grocery.spec.ts |
| 19 | B4 nudge + AI tool refit (meals/grocery) | medium | revert diff | extended test_nudge_rule_validator + ai-roundtrip smoke |
| 20 | D4 parent_action_items | **medium-high** | drop scout table + rename legacy back; 30-day retention window | new test_parent_action_items_scout + smoke chore-ops.spec.ts |
| 21 | A6 task_instances shadow-write | **high** | revert migration + revert shadow-write code; pre-migration Postgres snapshot is the insurance | new test_canonical_task_occurrences_shadow + mismatch-counter observability |
| 22 | A7 canonical read cutover | **high** | feature-flag toggle; legacy reads intact for fallback | new test_canonical_dashboard_cutover + smoke chores_today.spec.ts |
| 23 | A8 retire legacy | medium | revert code removal (DB views still present); some destructive code-delete not reversible by rollback alone | full backend-tests + arch-check |
| 24 | B5 drop legacy meals/grocery tables | medium | cannot recover DROP without backup; **pre-migration snapshot required** to `backup.b_slice_2026MMDD.*` | full backend-tests |
| 25 | Dc shim cleanup | low | re-create views via 022 bodies; drop of public.connector_configs is destructive but 0 writes, so acceptable loss | full backend-tests + arch-check |

---

## 4. Live-data preservation - table-by-table

This is the "don't lose data" playbook. Every non-zero table is listed with its plan.

| Table | Rows | Plan | Preservation mechanism |
|-------|------|------|------------------------|
| `public.sessions` | 172 | **DO NOT TOUCH** | No DDL of any kind. 172 live tokens = 172 active logins. |
| `public.ai_messages` | 118 | **LEAVE in public, promote to CANONICAL-in-public** | Zero data movement. Column-name landmine `metadata` → attribute `attachment_meta` preserved as-is. |
| `public.ai_tool_audit` | 52 | **LEAVE, promote** | Zero data movement. Compliance audit trail. |
| `public.scout_scheduled_runs` | 48 | **LEAVE in public** | Scheduler mutex. Any move risks duplicate AI jobs. |
| `public.parent_action_items` | 33 | **D4: atomic copy → scout** | `INSERT INTO scout.parent_action_items SELECT * FROM public.parent_action_items` + rename legacy to `_legacy` + forwarding view. 30-day legacy-rename retention. |
| `public.ai_conversations` | 30 | **LEAVE, promote** | Zero data movement. 11 migrations of accumulated contract. |
| `scout.routine_templates` | 25 | already canonical | no-op. |
| `public.role_tier_overrides` | 7 | **KEEP in public** | FK'd to family_members (cascade); parent table not moving, override cannot move either. |
| `scout.reward_policies` | 7 | already canonical | no-op. |
| `scout.task_templates` | 7 | **A1 expands schema, A5 backfills scope fields from chore_templates** | Existing 7 rows preserved; scope columns added NULL-able with backfill. |
| `scout.task_assignment_rules` | 7 | already canonical | no-op. |
| `public.family_members` | 8 | **KEEP in public** | Auth/tenancy foundation. Every other table FKs this. |
| `public.role_tiers` | 6 | **KEEP in public** | Public tier seed + scout registry pair is intentional (ARCHITECTURE.md:29-42). |
| `public.user_accounts` | 5 | **KEEP in public** | Auth foundation. |
| `scout.connectors` | 9 | already canonical | no-op. |
| `scout.connector_accounts` | 6 | already canonical | no-op. |
| `scout.household_rules` | 16 | already canonical | no-op. |
| `public.ai_daily_insights` | 2 | **LEAVE, promote** | Cache table, small, indefinite retention. |
| `public.grocery_items` | 2 | **B3: atomic copy → scout** | Dual-write trigger on public for one deploy cycle; then `INSERT INTO scout.grocery_items SELECT * FROM public.grocery_items`; rename legacy. |
| `public.ai_homework_sessions` | 1 | **LEAVE, promote** | FKs public.ai_conversations; cannot move without moving parent. |
| `public.purchase_requests` | 1 | **D5: atomic copy → scout** | Small-surface migration. Grocery FK temporarily dropped; B3 re-adds pointing at scout. |
| `public.member_config` | 1 | **D3: atomic copy → scout** | Simplest live-data move; serves as rehearsal for D4. |
| `public.families` | 1 | **KEEP in public** | Foundation. |
| `public._scout_migrations` | 53 | **ABSOLUTE DO-NOT-TOUCH** | Migration runner owns it. |

**Zero-row tables are migrated schema-only.** `public.meals`, `public.meal_plans`, `public.weekly_meal_plans`, `public.meal_reviews`, `public.dietary_preferences`, `public.bills`, `public.personal_tasks`, `public.task_notes`, `public.task_exceptions`, etc. - these are pure DDL operations with no data-loss risk.

**Pre-migration snapshots required:**
- Before A5: Postgres logical dump of `public.chore_templates`, `public.routines`, `public.routine_steps` (no row loss tolerated in rollback).
- Before A6: Postgres logical dump of `public.task_instances`, `public.task_instance_step_completions`, `public.daily_wins`. **Mandatory.** A6 is the riskiest PR in the sprint.
- Before B5: Postgres logical dump of the seven tables being dropped (destructive operation).
- Before D4: Postgres logical dump of `public.parent_action_items` (33 rows, AI writer, 5 services).

Snapshots live in `backup.<slice>_2026MMDD.*` schemas per Slice B §8 pattern.

---

## 5. Smoke test strategy per phase

Per the `feedback_batch_cleanup_pattern.md` memory, smoke-web is optional but backend/frontend/arch are load-bearing. Each phase has a mandatory smoke gate.

### Phase 0 smoke gate
- `backend-tests` green.
- `frontend-types` green.
- `arch-check` green (note: one persistent INFO on seedData drift from `arch-check-report.json`; document in handoff per house rule).

### Phase 1 smoke gate
- All Phase 0 gates.
- `test_permissions_orm.py` (new, D1) passes.
- `test_canonical_session2_block3` (extended for D2 seeds) passes.
- `test_chore_templates` scope-field round-trip via scout.task_templates (new after A1) passes.

### Phase 2 smoke gate
- Previous gates + `test_member_config_scout.py` (new, D3).
- Playwright `ai-personality.spec.ts` still green (member_config is read from ai_personality_service).

### Phase 3 smoke gate
- Previous gates + `test_v_household_today_surfaces_scope_fields` (new, A4) asserts non-null included/not_included/done_means_done for seed rows.
- Cardinality check on view (ensure LEFT JOIN did not row-multiply).

### Phase 4 smoke gate
- Previous gates + `test_canonical_backfill_chores.py` (new, A5) asserts 1:1 row equivalence.

### Phase 5 smoke gate (HIGH-risk phase)
- Previous gates + extended `test_nudge_rule_validator.py` attack suite (cross-tenant isolation, positive+negative cases for scout.task_occurrences, rejection of scout.nudge_dispatches and scout.permissions and pg_catalog).
- New `test_scan_missed_routines_reads_scout_task_occurrences_when_flag_on` + inverse fallback test.
- New smoke `smoke-tests/tests/nudges-phase-1-dual-read.spec.ts` toggles feature flag, asserts both source tables yield delivered dispatches.

### Phase 6 smoke gate
- Previous gates + `test_grocery` end-to-end (D5), new `smoke-tests/tests/canonical-grocery.spec.ts` (B3), extended `test_nudge_rule_validator` positive tests for scout.meal_weekly_plans (B4).
- `ai-roundtrip.spec.ts` must still green (daily_brief tool reads meals/grocery).

### Phase 7 smoke gate
- Previous gates + `test_parent_action_items_scout.py` (new, D4) covers 5 services + 2 routes + AI orchestrator path.
- Smoke `smoke-tests/tests/chore-ops.spec.ts` extended to assert chore_override action items surface in action inbox.

### Phase 8 smoke gate (HIGH-risk phase)
- Previous gates + `test_canonical_task_occurrences_shadow` (new, A6) asserts dual-write side effect matches per-member counts.
- Observability counter `canonical_task_occurrence_shadow_mismatch_total` must be ZERO across a 24-hour window before A7 proceeds.
- `test_canonical_dashboard_cutover` (new, A7) snapshots `/api/household/today` payload with flag ON vs OFF; payloads must be identical.
- Smoke `smoke-tests/tests/chores_today.spec.ts` (new) golden-path flow.

### Phase 9 smoke gate
- Previous gates + full `backend-tests` run (removing legacy generator in A8 will break tests that still reference it; this is the point of A8).
- Pre-B5: query traffic observability confirms zero reads on public.meals* / public.grocery_items / public.purchase_requests for 7 calendar days.
- Pre-Dc: grep `backend/` confirms zero refs to `scout.families` / `scout.family_members` / other shim views (validates the earlier finding).

### Per-PR runbook

Every PR follows this before merge (per `feedback_batch_cleanup_pattern.md`):

1. `npx tsc --noEmit` on `scout-ui/` (catches JSX parse errors before Vercel does).
2. `node scripts/architecture-check.js` clean.
3. Handoff doc at `docs/handoffs/YYYY-MM-DD_<pr-slug>.md`.
4. No em dashes anywhere (code, comments, commit message, handoff, PR body).
5. Wait for Railway `/health` + Vercel prod deploy green before the next serial PR.

---

## 6. Stop-conditions

### Pause-and-wait-for-Andrew signals

Any of these must halt execution and surface to Andrew:

1. **Sessions blast radius.** Any PR proposes touching `public.sessions` (including "harmless" index changes). **STOP.**
2. **Migration runner tamper.** Any PR touches `public._scout_migrations`. **STOP.**
3. **Auth foundation schema churn.** Any PR proposes column-level changes to `public.family_members`, `public.families`, `public.user_accounts`. **STOP.**
4. **Scheduler mutex move.** Any PR proposes moving `public.scout_scheduled_runs` to scout without an explicit scheduler-sprint plan. **STOP.**
5. **AI messages migration without override.** Any PR proposes migrating `public.ai_conversations` or `public.ai_messages` to scout.* despite the Slice C recommendation. **STOP and request Andrew override.**
6. **Out-of-order nudge gate.** A6 / A7 / A8 ready to merge but C2 or C3 not yet live. **STOP until C2+C3 are on main and Railway-green.**
7. **Grocery FK out of order.** Slice B touching `grocery_items.purchase_request_id` before D5 has landed. **STOP.**
8. **Permission seed collision.** Slice A or B planning raw-SQL `INSERT INTO scout.permissions` before D1 lands the ORM. **STOP.**
9. **Snapshot skipped.** A5, A6, B5, D4 about to execute without the pre-migration logical dump in place. **STOP.**
10. **Shadow-write mismatch counter non-zero.** A6 deployed, observability reports `canonical_task_occurrence_shadow_mismatch_total > 0`. **STOP A7. Investigate the drift.**
11. **Row-count surprise.** Pre-migration count query returns rows for tables the plan assumed empty (e.g., `public.weekly_meal_plans` has rows at B2 time). **STOP and upgrade migration to include backfill.**
12. **Row-count growth past threshold.** `public.grocery_items` grew from 2 to >1000 rows between plan date and execution date. **STOP and switch B3 to batched copy.**
13. **Nudge rule references moved table.** Production scout.nudge_rules has any rule whose canonical_sql references `public.task_instances` / `public.chore_templates` / `public.routines` when Phase 8 is about to run. **STOP. Edit rules or deactivate before proceeding.**

### Keep-going signals

- CI green, deploy green, smoke gate passed for phase → proceed to next phase.
- If "don't paper over" memory rule applies: a sub-item blocks, report and pause rather than force through. Every prior pause made the resulting PR cleaner (memory evidence).

---

## 7. Parallel-execution opportunities

Most PRs are serial per the feedback memory's deploy-gate rule, but some sets can legitimately parallelize:

**Fully parallel (no cross-dependency):**
- Phase 0 PRs 1-5. All docs/labels/shim. Can bundle into a single batch PR if preferred.
- Phase 1 PRs 8, 9, 10, 11 (A1, A2, A3, B2). All additive DDL on empty tables. Can share a single Railway deploy cycle. After D1 merges, fan out.

**Parallel-authorable, serial-mergeable:**
- C2 + C3 (Phase 5). Can be developed in parallel branches, but merge order is C2 then C3 so the validator is in place before the scanner dual-read.
- A6 + A7 authoring. Write both but merge A6 first; require observability-clean window before A7.

**Strictly serial (do not parallelize):**
- D1 → D2 → D3 → D4 → D5 chain within D.
- A4 → A5 → A6 → A7 → A8 chain within A.
- C2 → C3 chain.
- D5 → B3 → B4 chain.

**Batch-able without loss (single PR, multiple items):**
- Phase 9 could bundle A8 + B5 + Dc into one final cleanup PR. Not recommended - destructive operations (B5 drops, Dc drops) benefit from individual rollback points.

---

## 8. Wall-clock estimate

Assumptions:
- 1 operator (Andrew + Claude Code).
- PR prep + review + merge: 30 min (docs-light PRs) to 90 min (live-data migrations).
- Deploy + health-check cycle: ~8 min Railway + ~3 min Vercel = ~11 min.
- Smoke test run (backend-tests + frontend-types + arch-check on branch): ~8 min.
- Handoff doc: ~15 min.
- Post-merge Railway/Vercel green verification: ~11 min (next PR cannot start until this clears).

**Per-PR median wall-clock:** ~60-75 min including gates.

**Serial chain length:** 15 PRs must be strictly serial (D1, D2, D3, A4, A5, C2, C3, D5, B3, B4, D4, A6, A7, A8, B5). At ~75 min each = ~19 hours of pure execution.

**Parallel slots:** Phase 0 (5 PRs) + Phase 1 additive (4 PRs) + Dc (can run last parallel with B5) = ~10 PRs in 4-5 parallel slots, shaving ~4 hours.

**Net pure execution:** ~14-16 hours.

**Realistic calendar:** 4-6 days at Scout's established cadence (batch pattern averages 3-5 PRs/day for this complexity of work, per recent sprint-05 history - phases 1-5 shipped over 2 days each).

---

## 9. Railway deploy-fail handling

If Railway or Vercel deploy fails mid-sprint:

### Immediate response (within 5 minutes)

1. **Identify which PR.** Check the last merge commit on main.
2. **Check the error class:**
   - Migration error (`/health` returns 500, Railway logs show SQL fail): revert the migration file in a follow-up PR, hot-deploy.
   - Code error (build fails, tsc error, import error): revert the PR, hot-deploy.
   - Config error (missing env var, secret misnamed): check per `feedback_batch_cleanup_pattern.md` rule #3 (trust-but-verify via `gh api`); fix and re-deploy.
3. **Pause the sprint.** Per the concurrent-sessions memory, halt all downstream PRs. Do not try to "push through" a failure.

### Recovery per phase

- **Phases 0-2 fail:** simple revert. No data state to restore.
- **Phase 3 (A4 view) fails:** revert view DDL to migration 022 body. No data.
- **Phase 4 (A5 backfill) fails:** TRUNCATE scoped on `template_key LIKE 'legacy_%'` etc. Origin rows safe in public.
- **Phase 5 (C2/C3) fails:** revert validator code or flip feature flag. No data state.
- **Phase 6 (D5/B3/B4) fails:** See per-PR rollback in §3. Grocery FK drop is the coupling hazard; if D5 deployed but B3 failed, grocery FK is in a partial state - follow D5 rollback (re-add FK pointing at scout.purchase_requests using ALTER).
- **Phase 7 (D4) fails:** drop scout.parent_action_items + rename legacy back. 30-day retention window catches delayed failures.
- **Phase 8 (A6/A7) fails:** pre-migration snapshot is the insurance. Restore from snapshot if shadow-write produced bad data. A7 has feature flag for instant rollback.
- **Phase 9 (A8/B5/Dc) fails:** B5 is the destructive one - snapshot restore is the only path. A8 is reversible-ish (code delete + DB comment). Dc is reversible by replaying 022 view bodies.

### What's irrecoverable without manual action

- Any B5 drop executed without a fresh snapshot.
- Any A6 shadow-write producing bad data that gets committed + persisted past the snapshot window.
- Any session-touching PR (explicitly prohibited but listed for completeness).

### Handoff protocol on failure

Per `feedback_batch_cleanup_pattern.md` rule #1, "Don't paper over." If deploy fails and the root cause is ambiguous, STOP and write a `docs/handoffs/YYYY-MM-DD_pr_NN_blocker.md` explaining the blocker with evidence. Do not force a fix.

---

## 10. Cross-slice dependency handshakes

Explicit coordination points. Each is a merge-order contract between slices.

### Handshake 1: D1 before any permission-seeding migration
**Who:** D1 (Slice D) → A5, B2, B4, D2 (all slices).
**What:** ORM model for scout.permissions + scout.role_tier_permissions must be in place before any PR seeds a new permission key, so seeds are declarative not raw SQL.
**Gate:** branch off D1 for all subsequent permission-seeding PRs.

### Handshake 2: C2 before A6/A7/A8
**Who:** C2 (Slice C) → A6, A7, A8 (Slice A).
**What:** nudge_rule_validator whitelist must permit scout.task_occurrences before any PR stops populating public.task_instances. Silent break risk documented in audit §4.
**Gate:** C2 merged + Railway-green + Vercel-green + test_nudge_rule_validator attack suite passed.

### Handshake 3: C3 before A6/A7/A8
**Who:** C3 (Slice C) → A6, A7, A8 (Slice A).
**What:** built-in scanner SQL must have a dual-read bridge before deprecation of public.task_instances. Scanner bypasses the validator; same silent-break risk via different code path.
**Gate:** C3 merged, feature flag `scout.task_occurrences.canonical` plumbed, smoke test for dual-read green.

### Handshake 4: D5 before B3
**Who:** D5 (Slice D) → B3 (Slice B).
**What:** scout.purchase_requests must exist before grocery_items.purchase_request_id FK re-points.
**Gate:** D5 merged + Railway-green; B3's migration can then safely re-add the FK pointing at scout.purchase_requests.

### Handshake 5: Slice A AI tool port inside C-coordinated PR
**Who:** Slice A A7 ↔ Slice C (AI tool port).
**What:** `app/ai/tools.py:203,234,272-287` calls legacy services. A7 cutover removes the legacy routes; AI tools must be ported to canonical services at the same time to avoid immediate tool-error regression in chat.
**Gate:** Either bundle in A7 or as a co-authored C-owned PR merged immediately before A7. Slice C subagent recommends the second option; Slice A subagent is flexible.

### Handshake 6: D4 timing vs Slice B grocery work
**Who:** D4 (Slice D) ↔ B3 (Slice B).
**What:** grocery_service.py writes parent_action_items (`_create_meal_plan_review_action`). If D4 flips the ORM schema and B3 is mid-merge, an in-flight grocery-service request can throw. Not a hard blocker but a timing hazard.
**Gate:** Merge D4 on a quiet window (no grocery traffic expected); or ensure B3 is either fully merged + stable or not yet started.

---

## 11. Open questions for Andrew (before execution)

Resolved-in-synthesis answers in *italics*; items still requiring Andrew sign-off are flagged with **[DECIDE]**.

1. **[DECIDE]** Ratify "CANONICAL-in-public" as an audit category? This is the load-bearing Slice C reframing. If rejected, the sprint adds ~5 high-risk PRs to migrate ai_conversations / ai_messages / ai_tool_audit / ai_daily_insights / ai_homework_sessions to scout.*.
2. **[DECIDE]** task_instances: CONSOLIDATE (Slice A's recommendation, this plan) vs KEEP+BRIDGE (audit's effort-S estimate). CONSOLIDATE is 8 PRs; KEEP+BRIDGE compresses Slice A to 4 PRs. The dispute-tracking fields (`in_scope_confirmed`, `scope_dispute_opened_at`) strand on the legacy table under KEEP+BRIDGE. Plan assumes CONSOLIDATE.
3. **[DECIDE]** `public.personal_tasks` (0 rows): DEPRECATE (audit implies) vs CONSOLIDATE (Slice A recommends). `app/ai/tools.py:939` has a write path. Plan assumes CONSOLIDATE + scout.personal_tasks mirror.
4. **[DECIDE]** `public.scout_scheduled_runs` (48 rows): KEEP in public (Slice D strongly recommends, citing scheduler mutex) vs migrate to scout.* (cleaner but risks duplicate AI jobs). Plan assumes KEEP.
5. **[DECIDE]** D4 cutover: atomic (1 PR, 33 rows, ~3 sec Railway restart) vs dual-write (3 PRs, 1 deploy cycle overlap). Slice D recommends atomic; depends on whether Railway deploys serve writes during pod restart. Plan assumes atomic.
6. **[DECIDE]** Photo column rename `photo_example_url` → `photo_example_path` in A1. Cosmetic but breaks the `scout-ui/lib/api.ts:1346` comment. Plan assumes rename + comment update; alternative is keep the `_url` name despite semantics.
7. **[DECIDE]** `scout.meal_transformations` (migration 044, 0 rows, no code references): drop in B5 vs re-FK to scout.meal_staples in B2. Plan assumes drop in B5.
8. **[DECIDE]** Bundle A8+B5+Dc into one final cleanup PR? Plan keeps them separate for rollback granularity, but if Andrew prefers velocity, one bundled PR is acceptable - accept the lower rollback granularity.

9. *Answered in synthesis:* permission keys seeded declaratively via D1 ORM (not raw SQL) - all slices adopt.
10. *Answered in synthesis:* session-touching PRs rejected at review; Slice D explicit stop-condition holds across the sprint.
11. *Answered in synthesis:* migration mirroring at `backend/migrations/` and `database/migrations/` is the canon pattern; every PR verifies both.
12. *Answered in synthesis:* shim views (`scout.families` etc.) drop in Dc once grep confirms zero readers.

---

## 12. Execution readiness checklist

Before starting Phase 0:

- [ ] Andrew signs off on open questions 1-8 above.
- [ ] Andrew confirms row counts in production match audit (quick query against Railway Postgres: `SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE schemaname IN ('public','scout') AND n_live_tup > 0 ORDER BY n_live_tup DESC`).
- [ ] Pre-sprint snapshot: `pg_dump --schema-only` of whole DB + `pg_dump` of the 4 live-data public tables that will move (parent_action_items, purchase_requests, grocery_items, member_config).
- [ ] Migration numbers reserved: 053-075 allocated; no concurrent sprint uses this range.
- [ ] Handoff doc template copied from recent batch-2 PRs.
- [ ] `feedback_batch_cleanup_pattern.md` rules re-read: serial, no em dashes, evidence-based, don't paper over, trust-but-verify secrets.
- [ ] Andrew confirms: this plan supersedes the sprint-05 plan for scheduling purposes (sprint-05 is merged; this is the next sprint).

Once execution starts, the first PR (D0 docs or a bundled Phase 0 batch) gets its own handoff doc at `docs/handoffs/2026-04-DD_canonical_rewrite_phase_0.md`.

---

## 13. What this plan does NOT do

- Does not guarantee the sprint finishes in one continuous session. Multi-day execution is expected.
- Does not propose moving `public.sessions`, `public.family_members`, `public.families`, `public.user_accounts`, or `public._scout_migrations`. These are foundation; moving them is a separate sprint at best.
- Does not audit `scout-ui/` for every schema dependency. Frontend breakage is surfaced by smoke gates (Playwright) rather than pre-identified.
- Does not handle finance / bills consolidation beyond the `scout.bills` shim view. Full finance canonicalization is a separate sprint.
- Does not plan `scout.user_family_memberships` activation. It stays as a designed-but-unwired table until a future identity sprint.
- Does not re-validate ARCHITECTURE.md. Assumes Layer 1 (member_config) / Layer 2 / Layer 3 (household_rules) charter is correct.
- Does not pre-solve every permission-key name collision. Slice A/B/C add their keys via D1's ORM; name collisions are caught at that PR's test gate.

---

## 14. Sources

- `docs/plans/_drafts/2026-04-22_canonical_rewrite_subagent_A.md` (8 PRs, chores/tasks/routines)
- `docs/plans/_drafts/2026-04-22_canonical_rewrite_subagent_B.md` (5 PRs, meals/grocery/home)
- `docs/plans/_drafts/2026-04-22_canonical_rewrite_subagent_C.md` (5 PRs, ai-chat/nudges/affirmations/push)
- `docs/plans/_drafts/2026-04-22_canonical_rewrite_subagent_D.md` (7 PRs, identity/permissions/connectors/framework)
- `docs/plans/2026-04-22_schema_canonical_audit.md` (baseline audit)
- `docs/architecture/ARCHITECTURE.md`, `docs/architecture/interaction_contract.md`
- `backend/migrations/001-052*.sql` + `database/migrations/*.sql` mirror
- `docs/plans/2026-04-21-sprint-05-plan.md` (reference for nudges engine shape)
- User memory: `feedback_batch_cleanup_pattern.md`, `feedback_verify_deploys.md`, `reference_andrew_open_items.md`, `user_concurrent_sessions.md`

Plan prepared: 2026-04-22
Author: Claude (main agent)
For Andrew's morning review. Execution waits for sign-off.
