# Scout canonical rewrite sprint - v5.1 merged (execution plan)

**Supersedes:** v5 (`2026-04-22_canonical_rewrite_v5_plan.md`) and the separate v5.1 surgical-edits doc (`2026-04-22_canonical_rewrite_v5_1_plan.md`).
**Prepared:** 2026-04-22
**Status:** ChatGPT round-4 greenlit. Ready for Code execution.
**Iteration loop:** Chat v1 → ChatGPT → Chat v2 → ChatGPT → Chat v3 → Code reality-check → Chat v4 → ChatGPT → Code pre-flight → Chat v5 → ChatGPT round-4 → Chat v5.1 merged (this doc)

**Erratum (applied on repo import 2026-04-23 as part of PR 0.2):** two mechanical corrections were applied to the original Chat v5.1 merged artifact when committing to this repo. (1) All `SCOUT_AI_ENABLED` references were corrected to `SCOUT_ENABLE_AI` (6 hits). The actual env var name feeds `settings.enable_ai` at `backend/app/config.py:93`; `SCOUT_AI_ENABLED` is not a real env var and setting it has no effect. (2) Em dashes were replaced with hyphens to comply with the repo house rule. No semantic content was changed. The original Chat v5.1 text is preserved in the external planning clone.

This is a single-source-of-truth execution document. The surgical-edits doc is preserved separately for history and audit.

---

## 1. What changed across v4 → v5 → v5.1

**From v4 (Code's reality-check + ChatGPT round-3 feedback):**

1. FK drop-and-recreate is a first-class workstream. 23 of 26 retained scout.* tables have FKs pointing at rebuilt tables.
2. Seed/reference reseeding is a named Phase 5 step. Six tables MUST be reseeded: `scout.permissions`, `scout.role_tier_permissions`, `scout.connectors`, `scout.affirmations`, `scout.household_rules`, `scout.time_blocks`.
3. Phase 1 view-drop ordering fixed. Views MUST drop before tables.
4. `scout.member_config` build fresh + rewire. Table doesn't exist today.
5. Phase 5 checklist split: subsystem-independent (Part A) gates partial re-enable; subsystem-dependent (Parts B, C) gate full re-enable.
6. Two external writers added to Phase 0 quiesce plan: smoke-deployed `workflow_dispatch` path, scout-ui push-device registration on launch.
7. Acceptance checklist expanded: permission gate, dashboard render, task occurrence generation, purchase-request path, photo_example_path round-trip, scheduler health, push device registration.
8. DB-object audit scope expanded to cover materialized views, sequences, enums, schema grants, generated columns, custom functions, triggers.
9. Exact zero-row verification: `SELECT COUNT(*)` per table, not `pg_stat_user_tables.n_live_tup`.

**From v5.1 (ChatGPT round-4):**

10. Phase 5 reorder: bootstrap Andrew → PR 5.1 reseed → invite family → configure settings → Part A checks. v5 had invite/configure running while permissions table was empty.
11. `unquiesce_prod.py` takes `--ai-only` and `--full` flags. Each PR runs exactly one flag.
12. Phase 1 PR 1.1 scope explicitly covers ALL DB objects depending on legacy public.* tables (not just the 8 shim views). Includes `v_household_today` and anything else from pre-flight Part 5.
13. Reseed migration uses natural-key lookups (never hardcoded IDs) and requires pre-flight to verify no source seed rows were UPDATE/DELETE'd in later migrations.
14. End-of-Phase-2 FK reconciliation gate: compare Phase 1 dropped-FK matrix against `pg_constraint` current state before Phase 3 starts.
15. "No manual DB writes during window" explicit in Phase 0.
16. Scheduler quiesce poll extended from 60 seconds to 5 minutes (full interval).
17. Child task completion writeback test restored to Part A (was in v4, dropped in v5 by accident).
18. Parent action item test split: CHECK vocabulary (constraint test) + real writer path (service-layer test).
19. PR 5.3 sequencing pinned: env flips and smoke-account reprovision happen BEFORE the merge that re-enables the smoke auto-trigger.

---

## 2. Decisions locked

1. **Q1:** Drop `public.ai_*`. Build `scout.ai_*` per original architecture.
2. **Q2:** CONSOLIDATE `task_instances` → `scout.task_occurrences`.
3. **Q3:** CONSOLIDATE `personal_tasks`. Exercise writer during bootstrap (prove-or-drop).
4. **Q4:** `scout_scheduled_runs` keeps schema in public, truncates rows (AFTER quiesce).
5. **Q5:** N/A for data. Runtime coordination via Phase 0 quiesce.
6. **Q6:** Rename `photo_example_url` → `photo_example_path`.
7. **Q7:** Drop `scout.meal_transformations` (CASCADE from public.meals is the mechanism).
8. **Q8:** N/A.
9. **member_config:** Build `scout.member_config` fresh in Phase 2 PR 2.1. Rewire all writers in Phase 3 PR 3.1.

---

## 3. Protected public.* tables - exactly 3

| Table | Rule | Notes |
|-------|------|-------|
| `public._scout_migrations` | NEVER touched | Migration tracker. Truncate breaks the runner. |
| `public.sessions` | Truncate allowed (AFTER quiesce). Schema preserved. | In-house auth. |
| `public.scout_scheduled_runs` | Truncate allowed (AFTER quiesce confirms no jobs running). Schema preserved. | Scheduler mutex. |

All other `public.*` tables get dropped in Phase 1, including `public.member_config` (writers rewired to `scout.member_config`).

---

## 4. Maintenance window declaration

Main is broken between end of Phase 1 and end of Phase 3. Expected symptoms:
- Backend 500s for any route reading from dropped tables
- Frontend errors on affected paths
- Stored session tokens 401 against `/api/auth/me` after Phase 1 truncates sessions
- Scheduler disabled
- Smoke-deployed disabled

Acceptable because no live users.

Window closes at end of Phase 3. Verification: `/api/auth/me` resolves cleanly with a bootstrap-issued token, backend-tests pass without legacy references.

---

## 5. Sprint shape

**Estimated 15-22 PRs across 7 phases, 3-4 calendar days.**

### Phase 0 - Pre-sprint setup (2 PRs + manual ops)

**PR 0.1 - Snapshot + smoke-disable:**
- Full schema + data dump to `docs/plans/_snapshots/2026-04-22_pre_rewrite_full.sql`
- Document what's dropped + decision rationale
- Edit `.github/workflows/ci.yml`: remove `push:` trigger from `smoke-deployed` job, leaving only `workflow_dispatch:`. Document the exact edit in the PR body so Phase 5 PR 5.3 can reverse it.
- Commit re-enable checklist

**PR 0.2 - Quiesce / unquiesce scripts:**

Add `scripts/quiesce_prod.py` and `scripts/unquiesce_prod.py` to the repo. Both idempotent.

`quiesce_prod.py` must:
- Verify `SCOUT_SCHEDULER_ENABLED=false` on Railway
- Verify scheduler is actually idle: **poll `public.scout_scheduled_runs` for 5 minutes (full scheduler interval)**, confirm no new rows AND no in-flight `run_started_at` without corresponding `run_ended_at`
- Verify `SCOUT_ENABLE_BOOTSTRAP=true` set
- Verify `SCOUT_ENABLE_AI=false` set (belt-and-suspenders)
- Call Supabase Storage REST API: list and DELETE all objects in the attachments bucket
- Print confirmation of each step

`unquiesce_prod.py` is phase-aware with flags:
- `--ai-only` flips `SCOUT_ENABLE_AI=true` only. Used in PR 5.2.
- `--full` flips `SCOUT_SCHEDULER_ENABLED=true` and `SCOUT_ENABLE_BOOTSTRAP=false`. Used in PR 5.3.

Exactly one flag per invocation. Script rejects calls without a flag.

**Manual ops (Andrew, after PR 0.2 merges):**
- Set env vars on Railway:
  - `SCOUT_SCHEDULER_ENABLED=false`
  - `SCOUT_ENABLE_BOOTSTRAP=true`
  - `SCOUT_ENABLE_AI=false`
- Wait for deploy green
- Run `python scripts/quiesce_prod.py` locally (or on Railway shell) to verify + purge Supabase Storage
- **Close scout-ui / Claude in Chrome / any open Scout client tabs.** App launches write `scout.push_devices` via `scout-ui/lib/push.ts:321`.
- **No manual DB writes during the window.** No psql sessions, no Supabase SQL editor, no Supabase table editor clicks, no ad-hoc scripts beyond the named `quiesce_prod.py` / `unquiesce_prod.py`. If checking DB state, read-only queries only.
- Confirm in writing (e.g., handoff doc update) before Phase 1 starts.

**Stop-conditions for Phase 0:**
- Scheduler keeps ticking after env var set (quiesce mechanism broken)
- Supabase Storage purge fails
- Quiesce script itself fails for any reason
- Any unplanned DB write detected during the window (via `scout_scheduled_runs` poll or other signal)

**Risk:** low.

### Phase 1 - Clean slate (3 PRs)

Main breaks at end of this phase.

**PR 1.1 - Drop all DB objects depending on legacy public.* tables:**

Scope covers ALL dependent DB objects, not just the 8 shim views. Pre-flight Part 5 is the authoritative list.

- **All 8 shim views** from `022_session2_canonical.sql:183-190`:
  - `scout.families`, `scout.family_members`, `scout.user_accounts`, `scout.sessions`, `scout.role_tiers`, `scout.role_tier_overrides`, `scout.connector_mappings`, `scout.connector_configs`
- **`v_household_today`** - drop now; rebuild in PR 3.5.
- **Any other views, materialized views, triggers, functions** discovered via pre-flight Part 5 that reference tables being dropped in PR 1.3.
- **Scout.* tables being rebuilt fresh in Phase 2:** `scout.task_templates`, `scout.task_occurrences`, `scout.routine_templates`, `scout.meal_transformations`.
- **FKs from retained scout.* tables pointing at rebuilt targets** (23 FKs per pre-flight Part 1). One migration file: `NNN_phase_1_drop_fks_on_retained.sql`. Drops FKs but not the tables themselves.

If Code discovers a DB object not in the pre-flight Part 5 list that depends on something being dropped, pause and escalate. Do NOT CASCADE.

**PR 1.2 - Truncate domain-data:**
- TRUNCATE all scout.* tables (full keep-list enumerated in PR 1.3 below). Cascade where needed.
- TRUNCATE `public.sessions` and `public.scout_scheduled_runs` (exceptions per §3).
- Verify zero-row state: `SELECT COUNT(*)` per truncated table within same transaction. No `pg_stat_user_tables`.
- **SEED_REFERENCE tables truncate too** - they get explicitly reseeded in Phase 5. Don't skip-truncate.

**PR 1.3 - Drop public.* legacy tables:**

Drop order respects FK RESTRICT blockers (from pre-flight Part 4.4):
1. `public.task_instance_step_completions`
2. `public.task_instances`
3. `public.routine_steps`
4. `public.routines`
5. `public.chore_templates`
6. `public.ai_messages` (before ai_conversations - CASCADE)
7. `public.ai_conversations`
8. All other independent tables: ai_tool_audit, ai_daily_insights, ai_homework_sessions, meals, meal_reviews, meal_plans, weekly_meal_plans, grocery_items, purchase_requests, personal_tasks, parent_action_items, member_config, family_memories, daily_wins, events, event_attendees, bills, allowance_ledger, activity_records, dietary_preferences, health_summaries, notes, planner_bundle_applies, scout_anomaly_suppressions, scout_mcp_tokens, role_tiers, role_tier_overrides, family_members, families, user_accounts, connector_mappings, connector_configs

NOT dropped: `public._scout_migrations`, `public.sessions`, `public.scout_scheduled_runs`.

`public.member_config` IS in the drop set (writers will rewire to `scout.member_config` in Phase 3).

**Migration mirror:** every migration file written to `backend/migrations/NNN_*.sql` AND `database/migrations/NNN_*.sql`.

**Stop-conditions:**
- Unexpected FK blocks a drop
- TRUNCATE fails
- Migration mirror check fails
- DB object found that depends on a dropped target and wasn't handled in PR 1.1

**Risk:** low-medium.

### Phase 2 - Build canonical schema (5 PRs + reconciliation gate)

Main still broken.

Each PR includes:
- New tables (additive DDL)
- Recreation of FKs FROM retained scout.* tables that were dropped in PR 1.1, scoped to the domain being rebuilt in this PR

**PR 2.1 - Identity + member_config (6 tables built):**
- Build: `scout.families`, `scout.family_members`, `scout.user_accounts`, `scout.role_tiers`, `scout.role_tier_overrides`, `scout.member_config`
- Build `scout.sessions`? NO - stays in public per §3.
- Recreate FKs from retained tables pointing at identity: nudge_rules, quiet_hours_family, push_devices, push_deliveries, home_zones, home_assets, maintenance_templates, maintenance_instances, affirmations, affirmation_feedback, affirmation_delivery_log, reward_policies, connector_accounts, user_family_memberships, user_preferences, device_registrations, role_tier_permissions, plus identity-FKs on task_assignment_rules / task_completions / task_notes / task_exceptions.
- Full list from pre-flight Part 1.

**PR 2.2 - Chores + tasks (8 tables built, 4 FK recreate):**
- Build: `scout.task_templates` with 7 native scope-contract fields (`included`, `not_included`, `done_means_done`, `supplies`, `photo_example_path`, `estimated_duration_minutes`, `consequence_on_miss`), `scout.routine_templates`, `scout.routine_steps`, `scout.standards_of_done` (fixes pre-existing silent FK bug), `scout.task_occurrences`, `scout.task_occurrence_step_completions`, `scout.personal_tasks`, `scout.daily_win_results`
- Recreate FKs on retained `scout.task_assignment_rules`, `scout.task_completions`, `scout.task_notes`, `scout.task_exceptions` pointing at `scout.task_templates` and `scout.task_occurrences`.

**PR 2.3 - AI domain (5 tables built):**
- Build: `scout.ai_conversations`, `scout.ai_messages` (preserve `metadata` column name for reserved-word reasons), `scout.ai_tool_audit`, `scout.ai_daily_insights`, `scout.ai_homework_sessions` (preserve subject CHECK from migration 018)
- Existing `scout.nudge_*` series unchanged
- No FK recreation needed for this PR (existing nudge tables FK identity, handled in 2.1)

**PR 2.4 - Meals + grocery + purchases (7 tables built):**
- Build: `scout.meal_weekly_plans`, `scout.meal_plan_entries`, `scout.meal_staples`, `scout.meal_reviews`, `scout.member_dietary_preferences`, `scout.grocery_items`, `scout.purchase_requests`

**PR 2.5 - Parent action items + rewards (remainder):**
- Build: `scout.parent_action_items` with full CHECK vocabulary per pre-flight Part 2: `grocery_review`, `purchase_request`, `chore_override`, `general`, `meal_plan_review`, `moderation_alert`, `daily_brief`, `weekly_retro`, `anomaly_alert`
- Build: `scout.allowance_periods`, `scout.allowance_results`, `scout.reward_extras_catalog`, `scout.reward_ledger_entries`, `scout.settlement_batches`
- Recreate FK from `scout.reward_policies.reward_policy_id`
- Recreate FK from `scout.nudge_dispatches.parent_action_item_id` (ON DELETE SET NULL)

**PR 2.6 - FK reconciliation gate (exit gate for Phase 2):**

Before Phase 3 can start, run an explicit reconciliation query against `pg_constraint`:

```sql
SELECT conname, conrelid::regclass, confrelid::regclass
FROM pg_constraint
WHERE contype = 'f'
  AND (conrelid::regclass::text LIKE 'scout.%'
       OR connamespace::regnamespace::text = 'scout');
```

Compare output to pre-flight Part 1's full list of 23 FKs on retained tables. Every FK dropped in PR 1.1 MUST be present again. Stop and escalate if any is missing.

This can ship as its own PR (PR 2.6) with a verification script in `scripts/verify_phase2_fks.py`, or as the closing verification of PR 2.5. Either way, Phase 3 does not start until the gate passes.

**NOT built in Phase 2 (confirmed as active retained tables per pre-flight Part 3):**
- `scout.calendar_exports`, `scout.greenlight_exports`, `scout.time_blocks`
- Projects domain (6 tables, all in `047_family_projects.sql`)
- `scout.connectors`, `scout.connector_accounts`
- Home maintenance domain (4 tables)
- Affirmations domain (3 tables)
- Nudge domain from Sprint 05
- Permissions + role_tier_permissions

All of those already exist. They're in the Phase 1 keep-list, got truncated (for SEED_REFERENCE ones), get FKs recreated in 2.1.

**Risk:** low. Additive DDL only. Reconciliation gate catches silent failures.

### Phase 3 - Rewire code to canonical (5-7 PRs)

Main unbreaks at end of this phase. Consumer audit discipline (§7) mandatory per PR.

**PR 3.1 - Auth + identity + member_config rewiring:**
- References to `public.families`, `public.user_accounts`, `public.family_members`, `public.role_tiers`, `public.role_tier_overrides` → scout.*
- References to `public.member_config` or unqualified `member_config` → `scout.member_config`
- Services: `auth_service.py`, `family_service.py`, `permissions`, `ai_personality_service.py`, `admin/config.py`, `affirmations.py` (for member_config reads)
- ORM models: `backend/app/models/access.py:56` `__tablename__ = "member_config"` → add `__table_args__ = {"schema": "scout"}`
- AI context: `backend/app/ai/context.py:338`, `backend/app/ai/personality_defaults.py:11,24`
- Frontend: `scout-ui/lib/api.ts`, `scout-ui/lib/types.ts`

**PR 3.2 - Chores + tasks rewiring:**
- References to `public.chore_templates`, `public.task_instances`, `public.routines`, `public.routine_steps`, `public.task_instance_step_completions`, `public.personal_tasks`, `public.daily_wins` → scout.*
- Services: `chore_service.py`, `task_generation_service.py`, `dashboard_service.py`
- Nudge rule validator whitelist: add `scout.task_occurrences`, `scout.task_completions`, `scout.task_templates`
- Nudge scanner SQL: update reads
- AI tools: `app/ai/tools.py` paths - `mark_chore_or_routine_complete` and any others

**PR 3.3 - AI domain rewiring:**
- References to `public.ai_*` → `scout.ai_*`
- Orchestrator writes: `app/ai/orchestrator.py`
- Tool audit logging
- Conversation resume endpoints
- Daily brief generation

**PR 3.4 - Remaining domains rewiring:**
- Meals, grocery, purchase_requests, parent_action_items (including action_type CHECK compliance)
- Services

**PR 3.5 - v_household_today rebuild:**
- Rebuild view against canonical tables only (it was dropped in PR 1.1)
- Scope-contract fields native (closes HIGH-severity bridge gap from original audit)
- No cross-schema joins

**PR 3.6-3.7 - Final sweep (as needed):**
- Any stragglers surfaced by earlier PR consumer audits
- Frontend types final pass
- Affirmations / home-maintenance surface cleanup if touched

**Stop-condition per Phase 3 PR:**
- Consumer audit grep returns a match not handled or explicitly skipped with reason

**Risk:** medium. Consumer audit is the correctness gate.

### Phase 4 - Legacy cleanup (1-2 PRs)

Main green.

**PR 4.1:** Drop any public.* tables that remained empty through rewiring (safety net; most handled in Phase 1).

**PR 4.2:** Architecture doc updates.
- ARCHITECTURE.md reflects clean state
- interaction_contract.md
- Drop / update plans referencing legacy tables

**Risk:** low.

### Phase 5 - Reseed + bootstrap (ordered sequence)

**Critical ordering:** the bootstrap → reseed → invite → configure → Part A sequence is non-negotiable. v5 had invite/configure running while `scout.permissions` was empty; that's fixed in v5.1.

**Step 1 - Andrew bootstrap (solo, provides family_id for subsequent seeds):**
- POST `/api/auth/bootstrap` with Andrew's credentials → returns session token, creates first admin account with `is_primary=true`. Uses existing endpoint at `backend/app/routes/auth.py:77`.
- Verify login works end-to-end against `scout.*` identity tables.

**Step 2 - PR 5.1: Reseed SEED_REFERENCE tables:**

These tables are empty post-Phase 1 and MUST be repopulated or auth/features silently break.

Tables + sources:
- `scout.permissions` - 45 INSERT statements from migrations 022, 034, 040, 043, 046a, 046b, 047, 048, 049, 050, 051
- `scout.role_tier_permissions` - same migration set
- `scout.connectors` - from `022_session2_canonical.sql:933-948`, 9 rows
- `scout.affirmations` - from `039_affirmations.sql:75-108`, 25 starter affirmations
- `scout.household_rules` - from `023_session2_roberts_seed.sql:97` + `035_consolidate_family_config.sql:17`, 16 rows (family-scoped; requires Andrew's family_id from Step 1)
- `scout.time_blocks` - from `023_session2_roberts_seed.sql:148`, Roberts-specific

**Reseed discipline (non-negotiable):**

**a) Natural-key lookups only. Never hardcoded IDs.**

Wrong:
```sql
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
VALUES (3, 47);
```

Right:
```sql
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM scout.role_tiers rt, scout.permissions p
WHERE rt.name = 'parent' AND p.key = 'nudges.manage'
ON CONFLICT DO NOTHING;
```

**b) Family-scoped seeds use stable identity lookup:**

```sql
INSERT INTO scout.household_rules (family_id, rule_name, rule_value)
SELECT f.id, 'breakfast_time', '07:00'
FROM scout.families f
WHERE f.primary_parent_email = 'andrew@exxir.com'
ON CONFLICT DO NOTHING;
```

**c) Pre-flight seed content before writing the reseed migration.**

For each source migration (022, 023, 034, 035, 039, 040, 043, 046a, 046b, 047, 048, 049, 050, 051), Code must verify:
- Are there later migrations that UPDATE or DELETE rows from the seeded tables?
- If yes, the reseed migration must reflect final state, not historical INSERT.
- If any mutation found, pause and report. Do not guess final state.

**Mechanism:** single reseed migration file `NNN_reseed_seed_reference.sql` with natural-key INSERTs + `ON CONFLICT DO NOTHING`. Idempotent.

Do NOT attempt to re-run original migration files - `public._scout_migrations` already records them as applied.

**Step 3 - Invite family members (Andrew manual):**
- Through UI, invite Sally, Tyler, Sadie, Townes, River via normal family_members flow
- This step writes to `scout.family_members` and requires permissions table populated (Step 2)

**Step 4 - Configure family settings (Andrew manual):**
- Configure family settings via UI
- Populate grocery items, create initial chores via admin UI (`/admin/chores/new`, NOT Scout AI - that tool doesn't exist)
- Populate remaining settings to minimum viable state

**Step 5 - Acceptance checklist Part A (subsystem-independent, gates partial re-enable):**

- [ ] Adult login (Andrew, Sally) round-trips via bootstrap endpoint + subsequent normal auth
- [ ] Child login (any child account) round-trips
- [ ] Permission gate: adult-only admin action succeeds for adult, is denied for child
- [ ] Dashboard / `v_household_today` renders without 500s (confirms PR 3.5 rebuild and scope-contract fields surfacing)
- [ ] Chore creation via admin UI (`/admin/chores/new`) produces `scout.task_templates` row with scope-contract fields populated
- [ ] Task occurrence generation - creating a chore produces `scout.task_occurrences` rows on the expected schedule
- [ ] **Task completion writeback** - as the child, mark a task complete through the child UI. Verify `scout.task_completions` row created. Confirms FK drop-recreate on `scout.task_completions.task_occurrence_id` and `completed_by` worked.
- [ ] Grocery path - add item, see it in `scout.grocery_items`
- [ ] Purchase-request path - create a request, see it in `scout.purchase_requests`
- [ ] Photo upload round-trip - upload a chore photo, verify `photo_example_path` (not `_url`) stores a path, retrieval round-trips through the signed-URL resolver
- [ ] Parent action item CHECK vocabulary - insert test rows with each of the 9 action_type values directly against the DB. All accepted.
- [ ] Parent action item via real writer - trigger at least one parent action item creation through the actual service path. Verify row lands with correct action_type and full field population.

**Step 6 - PR 5.2: Partial re-enable (AI only):**
- Run `python scripts/unquiesce_prod.py --ai-only` (flips `SCOUT_ENABLE_AI=true`)
- Deploy, wait green
- Verify AI orchestrator writes land in `scout.ai_*` tables (not public.ai_*)

**Step 7 - Acceptance checklist Part B (AI-dependent, gates full re-enable):**

- [ ] AI conversation resume works across sessions (`scout.ai_conversations`, `scout.ai_messages`)
- [ ] Meal PDF parse via Scout AI produces `scout.meal_*` rows
- [ ] `personal_tasks` writer exercised - trigger `app/ai/tools.py:939` write path through AI. If unreachable after genuine attempt, file a drop follow-up PR for `scout.personal_tasks` (prove-or-drop).

**Step 8 - PR 5.3: Full re-enable (strict ordering):**

The following sequence is non-negotiable. Each step completes before the next starts.

1. Run `python scripts/unquiesce_prod.py --full` (flips `SCOUT_SCHEDULER_ENABLED=true` + `SCOUT_ENABLE_BOOTSTRAP=false`). Wait for deploy green.
2. Verify first scheduler tick clean: wait 5+ minutes, check `public.scout_scheduled_runs` shows one expected row, no duplicate-run or crash signatures.
3. Run `scripts/provision_smoke_child.py` + `scripts/provision_smoke_adult.py` (adult mirror still a Batch 1 pickup - create it here if not done). Verify both smoke accounts login.
4. ONLY AFTER steps 1-3 complete: merge the PR that re-enables `smoke-deployed` auto-trigger in `.github/workflows/ci.yml` (reverses Phase 0 PR 0.1 edit).

This ordering guarantees the first auto-triggered smoke-deployed run on PR 5.3's merge commit has all dependencies in place before it fires.

**Step 9 - Acceptance checklist Part C (scheduler + smoke, gates sprint closure):**

- [ ] Scheduler health confirmed in step 8.2 above
- [ ] Nudge path end-to-end - create a chore with quiet-hours-appropriate settings, wait for scheduler tick, verify nudge fires or is suppressed per config
- [ ] Push device registration - relaunch scout-ui client, verify `scout.push_devices` row created cleanly (the app writes on launch per `scout-ui/lib/push.ts:321`)
- [ ] First auto-triggered smoke-deployed run on PR 5.3's merge commit passes

**PR 5.3's auto-smoke-run = the definitive rewrite validation signal.**

**Stop-condition for any Phase 5 step:** any checklist item fails → root-cause before advancing. Do NOT re-enable subsystems in advance of their checklist passing.

### Phase 6 - Post-sprint verification (no PRs unless issues)

- Smoke-deployed green = rewrite validated
- Sprint handoff doc summarizing shipped / reshaped / deferred / total PR count / calendar days / any surprises
- Close gap-analysis item #7 (ARCHITECTURE.md domain updates)

---

## 6. Quiesce plan (Phase 0 detail)

**Single env var for scheduler:** `SCOUT_SCHEDULER_ENABLED=false` disables all 8 jobs:
1. `nudge_scan`
2. `nudge_ai_discovery_tick`
3. `_run_morning_brief`
4. `_run_anomaly_scan`
5. `_run_weekly_retro`
6. `_run_moderation_digest`
7. `run_push_receipt_poll_tick`
8. `process_pending_dispatches_tick`

**AI writers:** `SCOUT_ENABLE_AI=false` belt-and-suspenders. Plus: don't chat with Scout during the window.

**External writers (from pre-flight Part 6):**
- Inbound webhooks: NONE. Confirmed.
- Third-party callbacks: NONE. Supabase Storage is unidirectional.
- GitHub Actions `workflow_dispatch` smoke path: allows custom test_files that could write. Mitigation: Andrew does NOT manually dispatch smoke during the window.
- scout-ui push device registration: writes `scout.push_devices` on app launch. Mitigation: close all clients before Phase 1.
- Local scripts in /scripts: only run if Andrew runs them manually. Mitigation: don't run any script except `quiesce_prod.py` / `unquiesce_prod.py`.
- **Manual DB console writes:** no psql, no Supabase SQL editor, no Supabase table editor clicks, no ad-hoc queries that write. Read-only queries only.

**Post-quiesce verification (run before Phase 1):**

Poll `public.scout_scheduled_runs` for 5 minutes (full scheduler interval). If any new row appears after env var flipped, OR any in-flight run lacks a corresponding end marker, quiesce failed - stop.

---

## 7. Consumer audit discipline (mandatory per Phase 3 PR)

Every Phase 3 PR's handoff doc MUST include:

```
## Consumers found

### Source code (repo-wide grep)
Searched for: <old_table_name>, <old_column_names>, <related symbols>
Scope: backend, frontend, smoke-tests, scripts, docs, SQL files
Matches: <N>
Updated: <list of files>
Intentionally skipped: <list with reason>

### Database-side dependencies (expanded per pre-flight)
- Views (including materialized views): <list>
- Triggers: <list>
- Functions / stored procedures: <list>
- Custom enum / domain types referencing old columns: <list>
- Schema-level grants: <list>
- Generated columns / default expressions: <list>
- Sequences / identity ownership: <list>
- FK references from retained scout.* tables: <list>
- Comments referencing dropped objects: <list>

### Handled / Skipped
<for each DB-side dependency: updated / dropped / intentionally left / n/a>
```

Cross-cutting files that likely appear in every Phase 3 PR audit:
- `backend/app/services/dashboard_service.py`
- `backend/app/services/nudges_service.py`
- `backend/app/ai/orchestrator.py`
- `backend/app/ai/tools.py`
- `scout-ui/lib/api.ts`
- `scout-ui/lib/types.ts`

**Skip = PR reject.**

---

## 8. Stop-conditions

**Pause-and-wait-for-Andrew:**

- Phase 0: scheduler keeps ticking after env var flipped; Supabase Storage purge fails; quiesce script fails; any unplanned DB write detected during window
- Phase 1: unexpected FK blocks a drop; TRUNCATE fails; migration mirror check fails; DB object found depending on dropped target that wasn't handled in PR 1.1
- Phase 2: additive DDL fails; FK recreate fails; FK reconciliation gate (PR 2.6) shows missing FK
- Phase 3: consumer audit grep returns a match not handleable in this PR
- Phase 5: any acceptance checklist item fails; reseed migration pre-flight reveals later UPDATE/DELETE on seed rows with ambiguous final state; scheduler re-enable shows duplicate runs, stuck runs, or crashes; smoke-disable mechanism affects more of CI than intended
- Any phase: arch-check emits new WARN; backend-tests or frontend-types go red outside expected window; PR proposes modifying `public._scout_migrations`; PR proposes schema changes to `public.sessions` or `public.scout_scheduled_runs`

**Keep-going:**
- All CI green (excluding disabled smoke-deployed)
- Arch-check clean
- Consumer audit section complete per §7
- Handoff doc committed

**Expected-but-not-stop (maintenance window):**
- Backend 500s for domain routes between Phase 1 and Phase 3
- Frontend errors on affected paths between Phase 1 and Phase 3
- Stored session tokens returning 401 from `/api/auth/me` after Phase 1
- CI jobs that touch live Railway Postgres app data (besides disabled smoke-deployed)

---

## 9. Wall-clock estimate

| Phase | Duration | Notes |
|-------|----------|-------|
| Phase 0 (snapshot, quiesce, disable smoke, Supabase purge) | 2-3 hours | |
| Phase 1 (views/FKs drop, truncate, tables drop - 3 PRs) | 3-4 hours | |
| Phase 2 (canonical schema build + FK recreate + reconciliation - 5-6 PRs) | 5-7 hours | |
| Phase 3 (rewiring + consumer audits - 5-7 PRs) | 8-12 hours | |
| Phase 4 (cleanup) | 1-2 hours | |
| Phase 5 (reseed + bootstrap + split re-enable - 3 PRs + manual steps) | 3-4 hours | |
| Phase 5 manual bootstrap (Andrew) | 60-90 minutes | |
| Phase 6 verification | 30 minutes | |

**Total: 3-4 calendar days execution + ~1-1.5 hours Andrew manual.**

---

## 10. What this plan does NOT do

- Does NOT migrate live data (clean slate; no live users)
- Does NOT create shim views (clean slate)
- Does NOT include dual-write or feature-flagged read sources
- Does NOT auto-materialize unbuilt canonical tables
- Does NOT include canned seed-data automation beyond the SEED_REFERENCE reseed migration
- Does NOT keep main green between Phase 1 and Phase 3 - declared maintenance window
- Does NOT touch Supabase Auth (no Supabase Auth integration exists)
- Does NOT preserve Supabase Storage blobs (attachments bucket purged in Phase 0)
- Does NOT re-enable subsystems in advance of their acceptance checklist passing
- Does NOT allow manual DB console writes during the window

---

## 11. Execution readiness checklist

- [ ] Andrew confirms v5.1 merged supersedes v5 and v4
- [ ] Pre-flight PR merged (docs/plans/2026-04-22_canonical_rewrite_v5_preflight.md is canonical fact source)
- [ ] Phase 0 PR 0.1 (snapshot + smoke-disable) drafted and ready
- [ ] Phase 0 PR 0.2 (quiesce/unquiesce scripts with `--ai-only` / `--full` flags) drafted and ready
- [ ] Railway env vars ready to set: `SCOUT_SCHEDULER_ENABLED=false`, `SCOUT_ENABLE_BOOTSTRAP=true`, `SCOUT_ENABLE_AI=false`
- [ ] Migration number range: 053 is next available per pre-flight Part 8
- [ ] Andrew has closed all open scout-ui / Claude in Chrome / iOS app clients before Phase 1 starts
- [ ] Andrew committed to no-manual-DB-writes-during-window rule

---

## 12. Iteration loop status

1. ✅ Chat v1
2. ✅ ChatGPT round-1
3. ✅ Chat v2 (clean-slate pivot)
4. ✅ ChatGPT round-2
5. ✅ Chat v3
6. ✅ Code reality-check (PR #69)
7. ✅ Chat v4
8. ✅ ChatGPT round-3
9. ✅ Code pre-flight
10. ✅ Chat v5
11. ✅ ChatGPT round-4 (greenlit with 9 in-line edits)
12. ✅ Chat v5.1 merged (this doc)
13. ⏳ Code execution

---

## 13. Key risks, honestly named

1. **FK drop/recreate complexity in Phase 2.** 23 retained tables with FKs pointing at rebuilt targets. Mitigated by pre-flight Part 1 matrix + end-of-Phase-2 reconciliation gate (PR 2.6).

2. **Reseed migration correctness.** Copying INSERTs from 10+ source migrations is mechanical but error-prone. Mitigated by natural-key lookups only, ON CONFLICT DO NOTHING idempotence, pre-flight verification for later mutations, and Part A permission gate test proving `scout.permissions` + `scout.role_tier_permissions` reseeded correctly.

3. **`scout.member_config` rewiring surface.** 6+ services + routes + AI context + ORM model. Consumer audit per PR 3.1 is the correctness gate.

4. **External writer slip-up.** Andrew accidentally leaves a client open, runs a script, or writes via DB console during the window. Mitigated by explicit Phase 0 close-all step + no-manual-writes rule + stop-condition monitoring.

5. **`personal_tasks` unreachable during bootstrap.** Acceptance checklist Part B explicitly requires exercising the writer. If unreachable after genuine attempt, drop follow-up PR is the remediation.

6. **Bootstrap flag left on.** `SCOUT_ENABLE_BOOTSTRAP=true` lets anyone hitting `/api/auth/bootstrap` create an admin if no accounts exist. Mitigated by PR 5.3 flipping it `false`. Config warns at startup.

7. **Frontend stale token after Phase 1.** Andrew's localStorage token returns 401 mid-sprint. Mitigated by force-refresh + re-login via bootstrap in Phase 5.

8. **Maintenance window stretches.** 3-4 day estimate assumes no surprises. Extends if consumer audits reveal unknowns or FK recreate fails. Andrew's exposure minimal.

9. **Seed mutation history.** If later migrations UPDATE/DELETE seed rows and the reseed migration copies original INSERTs, final state is wrong. Mitigated by mandatory pre-flight verification before writing the reseed migration.

---

Ready for Code execution. Phase 0 PR 0.1 begins after this doc merges to `docs/plans/` as the canonical sprint plan.
