# Snapshot directory

Pre-sprint database snapshots for the canonical rewrite sprint
(v5.1 merged execution plan, `docs/plans/2026-04-22_canonical_rewrite_v5_1_merged.md`).

## Purpose

Schema + data dumps taken before destructive operations (Phase 1 drops).
Stored for forensic value: if anything goes sideways, a human can diff
against pre-sprint state. Per v5.1 §Phase 0 PR 0.1, the `pre_rewrite_full.sql`
dump is mandatory before Phase 1 begins.

## Who commits what

Claude Code produced the directory structure and this README. Claude Code
does NOT have Railway production credentials and cannot run `pg_dump`
against prod. Andrew runs the dump command below and commits the output.

## Filename convention

`YYYY-MM-DD_<purpose>.sql`

Current expected files:

| File | When | Who |
|------|------|-----|
| `2026-04-22_pre_rewrite_full.sql` | Before Phase 1 PR 1.1 | Andrew (manual pg_dump) |

## Dump command

Run from a machine with `SCOUT_DATABASE_URL` pointing at Railway production.

```bash
# From the repo root, after sourcing the Railway env var
pg_dump "$SCOUT_DATABASE_URL" \
  --format=plain \
  --no-owner \
  --no-privileges \
  --file=docs/plans/_snapshots/2026-04-22_pre_rewrite_full.sql
```

Options explained:
- `--format=plain` produces a readable SQL file (diffable by humans).
- `--no-owner` / `--no-privileges` strip ownership and grant metadata;
  keeps the dump portable across environments and reduces review noise.
- Output includes both schema (CREATE TABLE, CREATE VIEW, etc.) and data
  (INSERT or COPY statements). Data-and-schema is the forensic requirement
  from v5.1 §Phase 0 PR 0.1.

Expected size: small. Scout production has low hundreds of rows total
across all tables (see `2026-04-22_schema_canonical_audit.md` for exact
counts). Compressed or uncompressed is fine; plain is easier to review.

## What the dump will contain (decision rationale)

The dump is taken immediately before destructive work. It will capture:

**Tables being DROPPED in Phase 1 (per v5.1 §Phase 1 PR 1.3 drop list):**
- `public.ai_conversations`, `ai_messages`, `ai_tool_audit`, `ai_daily_insights`,
  `ai_homework_sessions`
- `public.chore_templates`, `routines`, `routine_steps`, `task_instances`,
  `task_instance_step_completions`, `personal_tasks`, `daily_wins`
- `public.meals`, `meal_plans`, `meal_reviews`, `weekly_meal_plans`,
  `dietary_preferences`
- `public.grocery_items`, `purchase_requests`
- `public.bills`, `parent_action_items`, `events`, `event_attendees`
- `public.member_config`, `activity_records`, `allowance_ledger`,
  `health_summaries`, `notes`, `planner_bundle_applies`, `family_memories`
- `public.families`, `family_members`, `user_accounts`, `role_tiers`,
  `role_tier_overrides` (rebuilt fresh in scout.*)
- `public.connector_configs`, `connector_mappings`
- Scout.* tables being rebuilt fresh: `scout.task_templates`,
  `scout.task_occurrences`, `scout.routine_templates`,
  `scout.meal_transformations`

**Tables being TRUNCATED (schema preserved) in Phase 1 (per v5.1 §3):**
- `public.sessions` (172 bearer tokens as of audit)
- `public.scout_scheduled_runs` (48 dedupe rows)
- SEED_REFERENCE scout tables: `scout.permissions`, `scout.role_tier_permissions`,
  `scout.connectors`, `scout.affirmations`, `scout.household_rules`,
  `scout.time_blocks` (per v5.1 §Phase 1 PR 1.2 note "SEED_REFERENCE tables
  truncate too"; they get explicitly reseeded in Phase 5 PR 5.1)

**Tables NOT touched (for completeness, dump still captures them):**
- `public._scout_migrations` (53 rows, migration tracker)
- All other `scout.*` tables that persist: nudge_*, push_*, home_*,
  affirmations sibling tables, connectors/connector_accounts, projects/*,
  reward_policies, etc.

## Security note

The dump will contain:
- bcrypt password hashes in `public.user_accounts.password_hash`
- bearer session tokens in `public.sessions.token` (currently 172 live tokens;
  these all invalidate when that table is truncated in Phase 1 anyway)
- user emails

The Scout repo is private (verified via `gh repo view` on 2026-04-23;
visibility=PRIVATE). Committing this dump to git is acceptable under that
constraint, and the forensic value outweighs the residual risk. Do not
mirror this directory to any public location.

## Retention

The dump stays in git history indefinitely. After Phase 6 closes the sprint,
it's evidence that the rewrite had a rollback path. Deleting later is
cheap if desired.

## After Phase 1 starts

Do NOT add any new dump files here mid-sprint. The pre-sprint dump is the
fixed reference. If a mid-sprint checkpoint dump is wanted, that's a
separate decision and separate PR.
