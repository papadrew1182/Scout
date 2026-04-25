# Scout canonical rewrite manifest v1.1.2

**Date:** 2026-04-25
**Repo state:** commit `c7cc13a`, post PR 1.5 merge
**Purpose:** SSOT for PR 1.5, PR 2.0, Phase 2, Phase 3, and Phase 5 gates after the Phase 1 stuck-state review.
**Filename note:** the document file is intentionally retained at `docs/plans/2026-04-25_canonical_rewrite_manifest_v1_1.md` despite the version bumps. Renaming would require updating `scripts/manifest_check.py`, `scripts/old_reference_grep.py`, and any downstream references in the same commit; for v1.1.x point releases the cost is not worth the rename. A future v2 may rename.

## Version history

- **v1.1.2** (2026-04-25, this revision) — ChatGPT pre-draft tertiary review of PR 2.1 (two passes) added: §0.2 fifth sprint-wide rule (rebuilt-table contract parity); §6 PR 2.1 gate criteria 6-9 (rebuilt-table contract parity, migration qualification, §2 FK restore parity, /ready maintenance semantic gate); §5 PR 2.1 ownership scope expansion (the /ready maintenance semantic patch); §3 GET /ready consumer row owner update; §1.4 UUID determinism note; §4 /ready semantic note. All inline-tagged `(added v1.1.2)`.
- **v1.1.1** (2026-04-25) — PR 2.0 grep audit surfaced 5 §3 amendments tagged inline `(added v1.1.1)`: §3.1 `backend/app/database.py`, §3.2 `backend/app/scheduler.py`, §3.4 `backend/services/connectors/*` tree (5 explicit rows + 1 rolled-up), §3.5 `backend/scout_mcp/server.py`, §3.7 `scout-ui/lib/meal_plan_hooks.ts`.
- **v1.1** (2026-04-25) — secondary-review feedback before commit: role-tier names verified against the pre-rewrite snapshot, PR 3.4 owner typos corrected, PR 1.5 maintenance middleware made mandatory, orphan public-table product decisions moved to an explicit pre-PR-3.4 gate.
- **v1** (2026-04-25) — initial after Phase 1 stuck-state review (handoff `docs/handoffs/2026-04-25_phase_1_chatgpt_review_packet.md`). Replaces named-scope reviews with a generated dependency-surface manifest as SSOT.

## 0. Hard rule: this manifest replaces named-scope reviews

Do not review future PRs by asking whether they satisfy a named surface like "routes" or "boot path". A PR is mergeable only if every manifest edge it touches is marked `restored`, `rewired`, `disabled`, `deleted`, or `acceptable-as-is`, and the PR gate in section 6 passes.

The fourth dependency class this manifest exists to prevent is **intermediate-state search-path resurrection**: because `backend/app/database.py` sets `search_path TO public, scout`, an unqualified legacy reference that currently fails can begin resolving to a newly created same-name `scout.*` table during Phase 2 before Phase 3 has intentionally rewired it. That is not compatibility. It is an accidental resolver change and must be gated per section 4.

### 0.1 Required runtime assumptions

- `SCOUT_SCHEDULER_ENABLED=false`, `SCOUT_ENABLE_AI=false`, and `SCOUT_ENABLE_BOOTSTRAP=true` are assumed during PR 1.5 through Phase 3 unless an explicit gate changes them.
- No manual DB writes, no smoke-deployed manual dispatch, no Scout UI app launches, no MCP calls, and no local operator scripts except those named in this manifest.
- Main must be able to boot after PR 1.5. It may return controlled maintenance responses for broken domain routes, but the container must start and `/health` must be 200.
- PR 1.5 must install a canonical-rewrite maintenance guard in production. Until the relevant Phase 3 owner removes the guard or narrows it under a named gate, every non-health/non-ready route that can execute legacy DB code must return controlled HTTP 503 before handler logic runs. The guard is mandatory, not optional.

### 0.2 Sprint-wide rules running tally

(Section added v1.1.2; rules 1-4 surface lessons from prior PRs that previously lived only in handoff docs and the §0 narrative; rule 5 surfaced by ChatGPT pre-draft tertiary review of PR 2.1.)

Each rule below was generalized after a specific failure or near-miss. The list is the running tally of "what category did the previous round not think to check"; each new rule is a strict superset of the gating discipline available before it.

1. **Intra-tier independence check applies to every multi-table tier in any destructive PR.** Single-table tiers are trivially clean; multi-table tiers require explicit FK enumeration before push, not after. Surfaced in PR 1.4 postmortem (Tier 5 alphabetical drop order put `families` before `family_members` while the FK still pointed at `families`).

2. **Poller queries against Railway should target the latest deployment ID explicitly** (`railway logs <id>`), not the default `--deployment` flag. Railway's default scopes to "last successful," which becomes invisible to a deploy-failure poller. Surfaced in PR 1.4 monitoring.

3. **Consumer audits for destructive PRs cover the full container boot path** (`start.sh`, `migrate.py`, `seed.py`, app startup events, scheduler bootstrap), not just request handlers. Surfaced when post-PR-1.4 deploy crashed in `seed.py` despite all request-handler audits passing.

4. **Intermediate-state search-path resurrection must be checked at every phase boundary.** Because `backend/app/database.py` sets `search_path TO public, scout`, an unqualified legacy reference that currently fails can begin resolving to a newly created same-name `scout.*` table during Phase 2 before Phase 3 has intentionally rewired it. Every unqualified legacy reference must be checked at every phase boundary against what the scout schema now has. Surfaced in v1 manifest §0 + §4 (the intermediate-state resolver).

5. **Rebuild PRs must prove full object-contract parity, not just table existence and externally-dropped FK restoration.** For every table rebuilt from a dropped source table, the PR must include a snapshot-derived contract checklist covering columns, types, nullability, defaults, CHECKs, PKs, UNIQUEs, partial indexes, ordinary indexes, outgoing FKs that died with the dropped source table, triggers and the functions they invoke, required reference rows, and fully qualified migration DDL. Surfaced by ChatGPT pre-draft tertiary review of PR 2.1. (added v1.1.2)

## 1. Table inventory

Contract rule for every row below: if the Phase 2 or Phase 3 owner rebuilds or rewires the object, the owner must preserve the exact pre-rewrite column/default/CHECK/unique/index contract from `docs/plans/_snapshots/2026-04-22_pre_rewrite_full.sql`, unless the row below names an intentional delta. Phase 2 migrations must not ship skeletal placeholders.

### 1.1 Public schema objects
| Table | Pre-rewrite state | Phase 1 disposition | Phase 2 disposition | Phase 3+ disposition | Reference rows | Contract / preserve rule |
| --- | --- | --- | --- | --- | --- | --- |
| public._scout_migrations | public base table | retained; never truncated or dropped | kept; no Phase 2 work | kept permanently | none | protected migration tracker; PR touching this is rejected |
| public.activity_records | public base table | dropped in 057 | no direct same-name Phase 2 target; owner must delete, disable, or introduce canonical target with Andrew approval | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.ai_conversations | public base table | dropped in 057 | PR 2.3 builds/restores target `scout.ai_conversations` | PR 3.3 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.ai_daily_insights | public base table | dropped in 057 | PR 2.3 builds/restores target `scout.ai_daily_insights` | PR 3.3 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.ai_homework_sessions | public base table | dropped in 057 | PR 2.3 builds/restores target `scout.ai_homework_sessions` | PR 3.3 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.ai_messages | public base table | dropped in 057 | PR 2.3 builds/restores target `scout.ai_messages` | PR 3.3 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.ai_tool_audit | public base table | dropped in 057 | PR 2.3 builds/restores target `scout.ai_tool_audit` | PR 3.3 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.allowance_ledger | public base table | dropped in 057 | PR 2.5 builds/restores target `scout.reward_ledger_entries` | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.bills | public base table | dropped in 057 | no direct same-name Phase 2 target; owner must delete, disable, or introduce canonical target with Andrew approval | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.chore_templates | public base table | dropped in 057 | PR 2.2 builds/restores target `scout.task_templates` | PR 3.2 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.connector_configs | public base table | dropped in 057 | no direct same-name Phase 2 target; owner must delete, disable, or introduce canonical target with Andrew approval | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.connector_mappings | public base table | dropped in 057 | no direct same-name Phase 2 target; owner must delete, disable, or introduce canonical target with Andrew approval | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.daily_wins | public base table | dropped in 057 | PR 2.2 builds/restores target `scout.daily_win_results` | PR 3.2 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.dietary_preferences | public base table | dropped in 057 | PR 2.4 builds/restores target `scout.member_dietary_preferences` | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.event_attendees | public base table | dropped in 057 | no direct same-name Phase 2 target; owner must delete, disable, or introduce canonical target with Andrew approval | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.events | public base table | dropped in 057 | no direct same-name Phase 2 target; owner must delete, disable, or introduce canonical target with Andrew approval | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.families | public base table | dropped in 057 | PR 2.1 builds/restores target `scout.families` | PR 3.1 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.family_members | public base table | dropped in 057 | PR 2.1 builds/restores target `scout.family_members` | PR 3.1 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.family_memories | public base table | dropped in 057 | no direct same-name Phase 2 target; owner must delete, disable, or introduce canonical target with Andrew approval | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.grocery_items | public base table | dropped in 057 | PR 2.4 builds/restores target `scout.grocery_items` | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.health_summaries | public base table | dropped in 057 | no direct same-name Phase 2 target; owner must delete, disable, or introduce canonical target with Andrew approval | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.meal_plans | public base table | dropped in 057 | PR 2.4 builds/restores target `scout.meal_plan_entries` | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.meal_reviews | public base table | dropped in 057 | PR 2.4 builds/restores target `scout.meal_reviews` | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.meals | public base table | dropped in 057 | PR 2.4 builds/restores target `scout.meal_staples` | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.member_config | public base table | dropped in 057 | PR 2.1 builds/restores target `scout.member_config` | PR 3.1 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.notes | public base table | dropped in 057 | no direct same-name Phase 2 target; owner must delete, disable, or introduce canonical target with Andrew approval | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.parent_action_items | public base table | dropped in 057 | PR 2.5 builds/restores target `scout.parent_action_items` | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.personal_tasks | public base table | dropped in 057 | PR 2.2 builds/restores target `scout.personal_tasks` | PR 3.2 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.planner_bundle_applies | public base table | dropped in 057 | no direct same-name Phase 2 target; owner must delete, disable, or introduce canonical target with Andrew approval | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.purchase_requests | public base table | dropped in 057 | PR 2.4 builds/restores target `scout.purchase_requests` | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.role_tier_overrides | public base table | dropped in 057 | PR 2.1 builds/restores target `scout.role_tier_overrides` | PR 3.1 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.role_tiers | public base table | dropped in 057 | PR 2.1 builds/restores target `scout.role_tiers` | PR 3.1 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.routine_steps | public base table | dropped in 057 | PR 2.2 builds/restores target `scout.routine_steps` | PR 3.2 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.routines | public base table | dropped in 057 | PR 2.2 builds/restores target `scout.routine_templates` | PR 3.2 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.scout_anomaly_suppressions | public base table | dropped in 057 | no direct same-name Phase 2 target; owner must delete, disable, or introduce canonical target with Andrew approval | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.scout_mcp_tokens | public base table | dropped in 057 | no direct same-name Phase 2 target; owner must delete, disable, or introduce canonical target with Andrew approval | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.scout_scheduled_runs | public base table | truncated in 056; retained in 057; FK(s) dropped in 057; PR 2.1 recreates against scout identity | kept in public; PR 2.1 restores FK(s) | kept in public; code may remain unqualified because public is first in search_path | none | schema preserved except FK target schema changes to scout |
| public.sessions | public base table | truncated in 056; retained in 057; FK(s) dropped in 057; PR 2.1 recreates against scout identity | kept in public; PR 2.1 restores FK(s) | kept in public; code may remain unqualified because public is first in search_path | none | schema preserved except FK target schema changes to scout |
| public.task_instance_step_completions | public base table | dropped in 057 | PR 2.2 builds/restores target `scout.task_occurrence_step_completions` | PR 3.2 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.task_instances | public base table | dropped in 057 | PR 2.2 builds/restores target `scout.task_occurrences` | PR 3.2 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.user_accounts | public base table | dropped in 057 | PR 2.1 builds/restores target `scout.user_accounts` | PR 3.1 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |
| public.weekly_meal_plans | public base table | dropped in 057 | PR 2.4 builds/restores target `scout.meal_weekly_plans` | PR 3.4/3.6 rewires/deletes every consumer; no public table resurrection | none | do not recreate in public |

### 1.1.1 Orphan public-table product-decision gate

The following dropped `public.*` tables have no direct same-name Phase 2 canonical target in this manifest. They must not be silently deleted by implementation drift and they must not be recreated in `public`. Before PR 3.4 starts, Andrew must approve one disposition for each row: `rebuild canonical target`, `delete feature and remove consumers`, `disable feature behind maintenance/feature flag`, or `defer with explicit non-executable proof`.

| Dropped table | Required pre-PR-3.4 decision | Default if no approval exists |
| --- | --- | --- |
| public.activity_records | keep/rebuild vs delete health/activity feature | block PR 3.4 |
| public.bills | keep/rebuild vs delete bills/finance feature | block PR 3.4 |
| public.connector_configs | keep/rebuild vs delete connector-config feature | block PR 3.4 |
| public.connector_mappings | keep/rebuild vs delete connector-mapping/integration feature | block PR 3.4 |
| public.event_attendees | keep/rebuild vs delete event-attendee feature | block PR 3.4 |
| public.events | keep/rebuild vs delete events/calendar feature | block PR 3.4 |
| public.family_memories | keep/rebuild vs delete family-memory feature | block PR 3.4 |
| public.health_summaries | keep/rebuild vs delete health-summary feature | block PR 3.4 |
| public.notes | keep/rebuild vs delete notes feature | block PR 3.4 |
| public.planner_bundle_applies | keep/rebuild vs delete planner-bundle feature | block PR 3.4 |
| public.scout_anomaly_suppressions | keep/rebuild vs delete anomaly-suppression feature | block PR 3.4 |
| public.scout_mcp_tokens | keep/rebuild vs delete MCP-token feature | block PR 3.4 |

Gate rule: PR 3.4 cannot use "remaining domains" language to cover these rows. The PR 3.4.0 decision artifact must name one disposition per table and then PR 3.4/3.6 must execute that disposition.

### 1.2 Scout schema objects that existed before Phase 1
| Table | Pre-rewrite state | Phase 1 disposition | Phase 2 disposition | Phase 3+ disposition | Reference rows | Contract / preserve rule |
| --- | --- | --- | --- | --- | --- | --- |
| scout.activity_events | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.affirmation_delivery_log | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.affirmation_feedback | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.affirmations | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | 25 curated starter affirmations | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.allowance_periods | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1; listed in PR 2.5 but table already exists, so owner must use ALTER not CREATE-only | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.allowance_results | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1; listed in PR 2.5 but table already exists, so owner must use ALTER not CREATE-only | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.bill_snapshots | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.budget_snapshots | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.calendar_exports | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.connector_accounts | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.connector_event_log | scout base table | truncated in 056; retained | retained from Phase 1; no Phase 2 FK restore | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.connectors | scout base table | truncated in 056; retained | retained from Phase 1; no Phase 2 FK restore | kept unless PR 3 owner explicitly deletes feature | 9 connector_key rows: google_maps, ynab, exxir, google_calendar, rex, greenlight, apple_health, nike_run_club, manual | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.daily_win_results | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1; listed in PR 2.2 but table already exists, so owner must use ALTER not CREATE-only | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.device_registrations | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.external_calendar_events | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.greenlight_exports | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.home_assets | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.home_zones | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.household_rules | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | 16 family-scoped Roberts rules; after Andrew bootstrap family_id exists | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.maintenance_instances | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.maintenance_templates | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.meal_transformations | scout base table | dropped in 055 | not rebuilt | PR 3.4 deletes/rewires `routes/meals.py` reader; this table remains deleted | none | intentional permanent drop per v5.1 Q7 |
| scout.nudge_dispatch_items | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.nudge_dispatches | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1, PR 2.5 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.nudge_rules | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.permissions | scout base table | truncated in 056; retained | retained from Phase 1; no Phase 2 FK restore | kept unless PR 3 owner explicitly deletes feature | 64 permission_key rows from pre-rewrite snapshot; global seed before bootstrap checks | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.project_budget_entries | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.project_milestones | scout base table | truncated in 056; retained | retained from Phase 1; no Phase 2 FK restore | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.project_tasks | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.project_template_tasks | scout base table | truncated in 056; retained | retained from Phase 1; no Phase 2 FK restore | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.project_templates | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.projects | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.push_deliveries | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.push_devices | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.quiet_hours_family | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.reward_extras_catalog | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1; listed in PR 2.5 but table already exists, so owner must use ALTER not CREATE-only | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.reward_ledger_entries | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1; listed in PR 2.5 but table already exists, so owner must use ALTER not CREATE-only | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.reward_policies | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.role_tier_permissions | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | 187 natural-key role_tier x permission rows from pre-rewrite snapshot; requires scout.role_tiers rows first | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.routine_steps | scout base table | dropped in 055 | PR 2.2 rebuilds real table | PR 3.2 or PR 3.2 rewires consumers | none | rebuild from snapshot DDL plus v5.1 deltas; routine_steps must include both FKs |
| scout.routine_templates | scout base table | dropped in 055 | PR 2.2 rebuilds real table | PR 3.2 or PR 3.2 rewires consumers | none | rebuild from snapshot DDL plus v5.1 deltas; routine_steps must include both FKs |
| scout.settlement_batches | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1; listed in PR 2.5 but table already exists, so owner must use ALTER not CREATE-only | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.stale_data_alerts | scout base table | truncated in 056; retained | retained from Phase 1; no Phase 2 FK restore | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.standards_of_done | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1; listed in PR 2.2 but table already exists, so owner must use ALTER not CREATE-only | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.sync_cursors | scout base table | truncated in 056; retained | retained from Phase 1; no Phase 2 FK restore | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.sync_jobs | scout base table | truncated in 056; retained | retained from Phase 1; no Phase 2 FK restore | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.sync_runs | scout base table | truncated in 056; retained | retained from Phase 1; no Phase 2 FK restore | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.task_assignment_rules | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.2 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.task_completions | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1, PR 2.2 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.task_exceptions | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1, PR 2.2 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.task_notes | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1, PR 2.2 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.task_occurrences | scout base table | dropped in 055 | PR 2.2 rebuilds real table | PR 3.2 or PR 3.2 rewires consumers | none | rebuild from snapshot DDL plus v5.1 deltas; routine_steps must include both FKs |
| scout.task_templates | scout base table | dropped in 055 | PR 2.2 rebuilds real table | PR 3.2 or PR 3.2 rewires consumers | none | rebuild from snapshot DDL plus v5.1 deltas; routine_steps must include both FKs |
| scout.time_blocks | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | 4 Roberts time blocks; after Andrew bootstrap family_id exists | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.travel_estimates | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.user_family_memberships | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.user_preferences | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |
| scout.work_context_events | scout base table | truncated in 056; retained | retained from Phase 1; FK restore owner(s): PR 2.1 | kept unless PR 3 owner explicitly deletes feature | none | preserve exact existing scout table contract and existing retained scout-to-scout FKs |

### 1.3 Planned scout targets that did not exist as base tables pre-rewrite
| Table | Pre-rewrite state | Phase 1 disposition | Phase 2 disposition | Phase 3+ disposition | Reference rows | Contract / preserve rule |
| --- | --- | --- | --- | --- | --- | --- |
| scout.ai_conversations | missing pre-rewrite as scout base table | not a retained base table after Phase 1 | PR 2.3 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.ai_daily_insights | missing pre-rewrite as scout base table | not a retained base table after Phase 1 | PR 2.3 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.ai_homework_sessions | missing pre-rewrite as scout base table | not a retained base table after Phase 1 | PR 2.3 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.ai_messages | missing pre-rewrite as scout base table | not a retained base table after Phase 1 | PR 2.3 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.ai_tool_audit | missing pre-rewrite as scout base table | not a retained base table after Phase 1 | PR 2.3 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.families | scout shim view over public table; view dropped in 053 | not a retained base table after Phase 1 | PR 2.1 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.family_members | scout shim view over public table; view dropped in 053 | not a retained base table after Phase 1 | PR 2.1 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.grocery_items | missing pre-rewrite as scout base table | not a retained base table after Phase 1 | PR 2.4 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.meal_plan_entries | missing pre-rewrite as scout base table | not a retained base table after Phase 1 | PR 2.4 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.meal_reviews | missing pre-rewrite as scout base table | not a retained base table after Phase 1 | PR 2.4 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.meal_staples | missing pre-rewrite as scout base table | not a retained base table after Phase 1 | PR 2.4 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.meal_weekly_plans | missing pre-rewrite as scout base table | not a retained base table after Phase 1 | PR 2.4 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.member_config | missing pre-rewrite as scout base table | not a retained base table after Phase 1 | PR 2.1 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.member_dietary_preferences | missing pre-rewrite as scout base table | not a retained base table after Phase 1 | PR 2.4 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.parent_action_items | missing pre-rewrite as scout base table | not a retained base table after Phase 1 | PR 2.5 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.personal_tasks | missing pre-rewrite as scout base table | not a retained base table after Phase 1 | PR 2.2 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.purchase_requests | missing pre-rewrite as scout base table | not a retained base table after Phase 1 | PR 2.4 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.role_tier_overrides | scout shim view over public table; view dropped in 053 | not a retained base table after Phase 1 | PR 2.1 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.role_tiers | scout shim view over public table; view dropped in 053 | not a retained base table after Phase 1 | PR 2.1 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | seed in PR 2.1 | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.task_occurrence_step_completions | missing pre-rewrite as scout base table | not a retained base table after Phase 1 | PR 2.2 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |
| scout.user_accounts | scout shim view over public table; view dropped in 053 | not a retained base table after Phase 1 | PR 2.1 builds table and all contract columns/defaults/CHECKs/indexes/FKs | Phase 3 owner rewires all consumers to this qualified table or ORM schema | none | no skeletal table; if source public table exists, derive from source contract plus named v5.1 deltas |

### 1.4 Reference-row manifest

These rows are schema contracts, not optional data. PR 2.1 must create baseline `scout.role_tiers` rows before any role-tier FK or role-tier-permission natural-key insert can work. Global seed rows should move before Andrew bootstrap; family-scoped rows remain after bootstrap.

Role-tier source-of-truth: the pre-rewrite snapshot contains exactly six role tier names: `DISPLAY_ONLY`, `PRIMARY_PARENT`, `PARENT`, `TEEN`, `YOUNG_CHILD`, and `CHILD`. There is no canonical `ADULT` row in the snapshot. Roberts-family age/persona handling maps users onto these rows in application logic; it does not create a separate `ADULT` role tier. Any proposal to introduce `ADULT`, lowercase `admin`, lowercase `parent_peer`, or any other tier name is a product/schema change requiring Andrew approval before PR 2.1.

`scout.role_tiers` rows use non-deterministic UUIDs from `gen_random_uuid()`. Phase 5 PR 5.1's `role_tier_permissions` reseed joins on `role_tiers.name` (the natural key), not on `id`. Do not preserve old UUIDs from the dropped `public.role_tiers`. (added v1.1.2)

| Table | Owner | Scope | Rows required | Gate reason |
| --- | --- | --- | --- | --- |
| scout.role_tiers | PR 2.1 | global | DISPLAY_ONLY, PRIMARY_PARENT, PARENT, TEEN, YOUNG_CHILD, CHILD | Required before `role_tier_permissions` reseed and smoke provisioning |
| scout.permissions | Phase 5 global reseed before bootstrap acceptance gates | global | 64 permission_key rows; see Appendix 8.1 | Permission checks fail as unknown until present |
| scout.role_tier_permissions | Phase 5 global reseed after role_tiers + permissions | global | 187 role_tier x permission rows; see Appendix 8.2 | Natural-key insert only; no hard-coded UUIDs |
| scout.connectors | Phase 5 global reseed | global | google_maps, ynab, exxir, google_calendar, rex, apple_health, hearth_display, greenlight, nike_run_club | Required before connector_accounts are usable |
| scout.affirmations | Phase 5 global reseed | global | 25 curated rows; see Appendix 8.5 | Required for affirmation UI/content |
| scout.household_rules | Phase 5 family-scoped reseed after Andrew bootstrap | family-scoped | 16 Roberts rules by rule_key; see Appendix 8.3 | Requires Andrew family_id |
| scout.time_blocks | Phase 5 family-scoped reseed after Andrew bootstrap | family-scoped | morning, after_school, evening, power_60 | Requires Andrew family_id |

### 1.5 Named contract deltas that override snapshot-copy behavior

- `scout.task_templates` in PR 2.2 must include native scope-contract fields: `included`, `not_included`, `done_means_done`, `supplies`, `photo_example_path`, `estimated_duration_minutes`, `consequence_on_miss`. If any code still expects `photo_example_url`, PR 3.2 owns the rename to `photo_example_path`.
- `scout.routine_steps` in PR 2.2 must include both FKs: `routine_template_id -> scout.routine_templates(id) ON DELETE CASCADE` and `standard_of_done_id -> scout.standards_of_done(id) ON DELETE SET NULL`.
- `scout.ai_messages` in PR 2.3 must preserve column name `metadata`, not rename to `metadata_` or any ORM-only alias.
- `scout.ai_homework_sessions` in PR 2.3 must preserve the subject CHECK vocabulary: math, reading, writing, science, history, language, other.
- `scout.parent_action_items.action_type` in PR 2.5 must accept exactly: grocery_review, purchase_request, chore_override, general, meal_plan_review, moderation_alert, daily_brief, weekly_retro, anomaly_alert.
- Any retained table already present in `scout` but listed as "Build" in v5.1 must be modified with `ALTER TABLE`/`ADD CONSTRAINT`; `CREATE TABLE IF NOT EXISTS` alone is not evidence of completion.

## 2. FK manifest

PR 2.6 must verify this explicit expected set, not a generic query. The expected set is every FK dropped in 054 plus the three kept-public FKs dropped in 057. The one `public.purchase_requests` mutual-breaker FK is listed for audit but is not recreated because the source table was dropped.
| Constraint | Source table | Source column(s) | Original target | Target column(s) | ON DELETE | Drop migration | Recreate owner | Required state after owner PR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| affirmations_created_by_fkey | scout.affirmations | created_by | public.family_members | id | SET NULL | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.affirmations.created_by -> scout.family_members(id) |
| affirmations_updated_by_fkey | scout.affirmations | updated_by | public.family_members | id | SET NULL | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.affirmations.updated_by -> scout.family_members(id) |
| affirmation_feedback_family_member_id_fkey | scout.affirmation_feedback | family_member_id | public.family_members | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.affirmation_feedback.family_member_id -> scout.family_members(id) |
| affirmation_delivery_log_family_member_id_fkey | scout.affirmation_delivery_log | family_member_id | public.family_members | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.affirmation_delivery_log.family_member_id -> scout.family_members(id) |
| connector_accounts_family_id_fkey | scout.connector_accounts | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.connector_accounts.family_id -> scout.families(id) |
| connector_accounts_user_account_id_fkey | scout.connector_accounts | user_account_id | public.user_accounts | id | SET NULL | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.connector_accounts.user_account_id -> scout.user_accounts(id) |
| device_registrations_user_account_id_fkey | scout.device_registrations | user_account_id | public.user_accounts | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.device_registrations.user_account_id -> scout.user_accounts(id) |
| home_assets_family_id_fkey | scout.home_assets | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.home_assets.family_id -> scout.families(id) |
| home_zones_family_id_fkey | scout.home_zones | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.home_zones.family_id -> scout.families(id) |
| household_rules_family_id_fkey | scout.household_rules | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.household_rules.family_id -> scout.families(id) |
| maintenance_instances_family_id_fkey | scout.maintenance_instances | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.maintenance_instances.family_id -> scout.families(id) |
| maintenance_instances_owner_member_id_fkey | scout.maintenance_instances | owner_member_id | public.family_members | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.maintenance_instances.owner_member_id -> scout.family_members(id) |
| maintenance_instances_completed_by_member_id_fkey | scout.maintenance_instances | completed_by_member_id | public.family_members | id | SET NULL | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.maintenance_instances.completed_by_member_id -> scout.family_members(id) |
| maintenance_templates_family_id_fkey | scout.maintenance_templates | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.maintenance_templates.family_id -> scout.families(id) |
| maintenance_templates_default_owner_member_id_fkey | scout.maintenance_templates | default_owner_member_id | public.family_members | id | SET NULL | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.maintenance_templates.default_owner_member_id -> scout.family_members(id) |
| nudge_dispatch_items_family_member_id_fkey | scout.nudge_dispatch_items | family_member_id | public.family_members | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.nudge_dispatch_items.family_member_id -> scout.family_members(id) |
| nudge_dispatches_family_member_id_fkey | scout.nudge_dispatches | family_member_id | public.family_members | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.nudge_dispatches.family_member_id -> scout.family_members(id) |
| nudge_dispatches_parent_action_item_id_fkey | scout.nudge_dispatches | parent_action_item_id | public.parent_action_items | id | SET NULL | 054_phase1_drop_fks_on_retained.sql | PR 2.5 | scout.nudge_dispatches.parent_action_item_id -> scout.parent_action_items(id) |
| nudge_rules_family_id_fkey | scout.nudge_rules | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.nudge_rules.family_id -> scout.families(id) |
| nudge_rules_created_by_family_member_id_fkey | scout.nudge_rules | created_by_family_member_id | public.family_members | id | SET NULL | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.nudge_rules.created_by_family_member_id -> scout.family_members(id) |
| push_deliveries_family_member_id_fkey | scout.push_deliveries | family_member_id | public.family_members | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.push_deliveries.family_member_id -> scout.family_members(id) |
| push_devices_family_member_id_fkey | scout.push_devices | family_member_id | public.family_members | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.push_devices.family_member_id -> scout.family_members(id) |
| quiet_hours_family_family_id_fkey | scout.quiet_hours_family | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.quiet_hours_family.family_id -> scout.families(id) |
| reward_policies_family_id_fkey | scout.reward_policies | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.reward_policies.family_id -> scout.families(id) |
| reward_policies_family_member_id_fkey | scout.reward_policies | family_member_id | public.family_members | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.reward_policies.family_member_id -> scout.family_members(id) |
| role_tier_permissions_role_tier_id_fkey | scout.role_tier_permissions | role_tier_id | public.role_tiers | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.role_tier_permissions.role_tier_id -> scout.role_tiers(id) |
| user_family_memberships_family_id_fkey | scout.user_family_memberships | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.user_family_memberships.family_id -> scout.families(id) |
| user_family_memberships_family_member_id_fkey | scout.user_family_memberships | family_member_id | public.family_members | id | SET NULL | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.user_family_memberships.family_member_id -> scout.family_members(id) |
| user_family_memberships_role_tier_id_fkey | scout.user_family_memberships | role_tier_id | public.role_tiers | id | SET NULL | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.user_family_memberships.role_tier_id -> scout.role_tiers(id) |
| user_family_memberships_user_account_id_fkey | scout.user_family_memberships | user_account_id | public.user_accounts | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.user_family_memberships.user_account_id -> scout.user_accounts(id) |
| user_preferences_user_account_id_fkey | scout.user_preferences | user_account_id | public.user_accounts | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.user_preferences.user_account_id -> scout.user_accounts(id) |
| task_assignment_rules_task_template_id_fkey | scout.task_assignment_rules | task_template_id | scout.task_templates | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.2 | scout.task_assignment_rules.task_template_id -> scout.task_templates(id) |
| task_completions_task_occurrence_id_fkey | scout.task_completions | task_occurrence_id | scout.task_occurrences | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.2 | scout.task_completions.task_occurrence_id -> scout.task_occurrences(id) |
| task_completions_completed_by_fkey | scout.task_completions | completed_by | public.family_members | id | SET NULL | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.task_completions.completed_by -> scout.family_members(id) |
| task_notes_task_occurrence_id_fkey | scout.task_notes | task_occurrence_id | scout.task_occurrences | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.2 | scout.task_notes.task_occurrence_id -> scout.task_occurrences(id) |
| task_notes_author_id_fkey | scout.task_notes | author_id | public.family_members | id | SET NULL | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.task_notes.author_id -> scout.family_members(id) |
| task_exceptions_task_occurrence_id_fkey | scout.task_exceptions | task_occurrence_id | scout.task_occurrences | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.2 | scout.task_exceptions.task_occurrence_id -> scout.task_occurrences(id) |
| task_exceptions_created_by_fkey | scout.task_exceptions | created_by | public.family_members | id | SET NULL | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.task_exceptions.created_by -> scout.family_members(id) |
| allowance_periods_family_id_fkey | scout.allowance_periods | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.allowance_periods.family_id -> scout.families(id) |
| allowance_results_family_member_id_fkey | scout.allowance_results | family_member_id | public.family_members | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.allowance_results.family_member_id -> scout.family_members(id) |
| reward_extras_catalog_family_id_fkey | scout.reward_extras_catalog | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.reward_extras_catalog.family_id -> scout.families(id) |
| reward_ledger_entries_family_id_fkey | scout.reward_ledger_entries | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.reward_ledger_entries.family_id -> scout.families(id) |
| reward_ledger_entries_family_member_id_fkey | scout.reward_ledger_entries | family_member_id | public.family_members | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.reward_ledger_entries.family_member_id -> scout.family_members(id) |
| settlement_batches_family_id_fkey | scout.settlement_batches | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.settlement_batches.family_id -> scout.families(id) |
| standards_of_done_family_id_fkey | scout.standards_of_done | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.standards_of_done.family_id -> scout.families(id) |
| daily_win_results_family_id_fkey | scout.daily_win_results | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.daily_win_results.family_id -> scout.families(id) |
| daily_win_results_family_member_id_fkey | scout.daily_win_results | family_member_id | public.family_members | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.daily_win_results.family_member_id -> scout.family_members(id) |
| time_blocks_family_id_fkey | scout.time_blocks | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.time_blocks.family_id -> scout.families(id) |
| calendar_exports_family_id_fkey | scout.calendar_exports | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.calendar_exports.family_id -> scout.families(id) |
| greenlight_exports_family_member_id_fkey | scout.greenlight_exports | family_member_id | public.family_members | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.greenlight_exports.family_member_id -> scout.family_members(id) |
| activity_events_family_id_fkey | scout.activity_events | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.activity_events.family_id -> scout.families(id) |
| activity_events_family_member_id_fkey | scout.activity_events | family_member_id | public.family_members | id | SET NULL | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.activity_events.family_member_id -> scout.family_members(id) |
| external_calendar_events_family_id_fkey | scout.external_calendar_events | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.external_calendar_events.family_id -> scout.families(id) |
| work_context_events_family_id_fkey | scout.work_context_events | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.work_context_events.family_id -> scout.families(id) |
| work_context_events_user_account_id_fkey | scout.work_context_events | user_account_id | public.user_accounts | id | SET NULL | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.work_context_events.user_account_id -> scout.user_accounts(id) |
| budget_snapshots_family_id_fkey | scout.budget_snapshots | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.budget_snapshots.family_id -> scout.families(id) |
| bill_snapshots_family_id_fkey | scout.bill_snapshots | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.bill_snapshots.family_id -> scout.families(id) |
| travel_estimates_family_id_fkey | scout.travel_estimates | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.travel_estimates.family_id -> scout.families(id) |
| project_templates_family_id_fkey | scout.project_templates | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.project_templates.family_id -> scout.families(id) |
| project_templates_created_by_family_member_id_fkey | scout.project_templates | created_by_family_member_id | public.family_members | id | SET NULL | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.project_templates.created_by_family_member_id -> scout.family_members(id) |
| projects_family_id_fkey | scout.projects | family_id | public.families | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.projects.family_id -> scout.families(id) |
| projects_primary_owner_family_member_id_fkey | scout.projects | primary_owner_family_member_id | public.family_members | id | SET NULL | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.projects.primary_owner_family_member_id -> scout.family_members(id) |
| projects_created_by_family_member_id_fkey | scout.projects | created_by_family_member_id | public.family_members | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.projects.created_by_family_member_id -> scout.family_members(id) |
| project_tasks_owner_family_member_id_fkey | scout.project_tasks | owner_family_member_id | public.family_members | id | SET NULL | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.project_tasks.owner_family_member_id -> scout.family_members(id) |
| project_budget_entries_recorded_by_family_member_id_fkey | scout.project_budget_entries | recorded_by_family_member_id | public.family_members | id | CASCADE | 054_phase1_drop_fks_on_retained.sql | PR 2.1 | scout.project_budget_entries.recorded_by_family_member_id -> scout.family_members(id) |
| sessions_user_account_id_fkey | public.sessions | user_account_id | public.user_accounts | id | CASCADE | 057_phase1_drop_public_legacy.sql | PR 2.1 | public.sessions.user_account_id -> scout.user_accounts(id) |
| scout_scheduled_runs_family_id_fkey | public.scout_scheduled_runs | family_id | public.families | id | CASCADE | 057_phase1_drop_public_legacy.sql | PR 2.1 | public.scout_scheduled_runs.family_id -> scout.families(id) |
| scout_scheduled_runs_member_id_fkey | public.scout_scheduled_runs | member_id | public.family_members | id | CASCADE | 057_phase1_drop_public_legacy.sql | PR 2.1 | public.scout_scheduled_runs.member_id -> scout.family_members(id) |
| purchase_requests_linked_grocery_item_id_fkey | public.purchase_requests | linked_grocery_item_id | public.grocery_items | id | SET NULL | 057_phase1_drop_public_legacy.sql | NO_RECREATE | source public.purchase_requests is dropped; canonical mutual FK, if required, belongs inside PR 2.4 scout.grocery_items/scout.purchase_requests DDL |

### 2.1 PR 2.6 reconciliation query

```sql
SELECT conname, conrelid::regclass AS source_table, confrelid::regclass AS target_table, pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE contype = 'f'
  AND conname = ANY (ARRAY[
    'affirmations_created_by_fkey',
    'affirmations_updated_by_fkey',
    'affirmation_feedback_family_member_id_fkey',
    'affirmation_delivery_log_family_member_id_fkey',
    'connector_accounts_family_id_fkey',
    'connector_accounts_user_account_id_fkey',
    'device_registrations_user_account_id_fkey',
    'home_assets_family_id_fkey',
    'home_zones_family_id_fkey',
    'household_rules_family_id_fkey',
    'maintenance_instances_family_id_fkey',
    'maintenance_instances_owner_member_id_fkey',
    'maintenance_instances_completed_by_member_id_fkey',
    'maintenance_templates_family_id_fkey',
    'maintenance_templates_default_owner_member_id_fkey',
    'nudge_dispatch_items_family_member_id_fkey',
    'nudge_dispatches_family_member_id_fkey',
    'nudge_dispatches_parent_action_item_id_fkey',
    'nudge_rules_family_id_fkey',
    'nudge_rules_created_by_family_member_id_fkey',
    'push_deliveries_family_member_id_fkey',
    'push_devices_family_member_id_fkey',
    'quiet_hours_family_family_id_fkey',
    'reward_policies_family_id_fkey',
    'reward_policies_family_member_id_fkey',
    'role_tier_permissions_role_tier_id_fkey',
    'user_family_memberships_family_id_fkey',
    'user_family_memberships_family_member_id_fkey',
    'user_family_memberships_role_tier_id_fkey',
    'user_family_memberships_user_account_id_fkey',
    'user_preferences_user_account_id_fkey',
    'task_assignment_rules_task_template_id_fkey',
    'task_completions_task_occurrence_id_fkey',
    'task_completions_completed_by_fkey',
    'task_notes_task_occurrence_id_fkey',
    'task_notes_author_id_fkey',
    'task_exceptions_task_occurrence_id_fkey',
    'task_exceptions_created_by_fkey',
    'allowance_periods_family_id_fkey',
    'allowance_results_family_member_id_fkey',
    'reward_extras_catalog_family_id_fkey',
    'reward_ledger_entries_family_id_fkey',
    'reward_ledger_entries_family_member_id_fkey',
    'settlement_batches_family_id_fkey',
    'standards_of_done_family_id_fkey',
    'daily_win_results_family_id_fkey',
    'daily_win_results_family_member_id_fkey',
    'time_blocks_family_id_fkey',
    'calendar_exports_family_id_fkey',
    'greenlight_exports_family_member_id_fkey',
    'activity_events_family_id_fkey',
    'activity_events_family_member_id_fkey',
    'external_calendar_events_family_id_fkey',
    'work_context_events_family_id_fkey',
    'work_context_events_user_account_id_fkey',
    'budget_snapshots_family_id_fkey',
    'bill_snapshots_family_id_fkey',
    'travel_estimates_family_id_fkey',
    'project_templates_family_id_fkey',
    'project_templates_created_by_family_member_id_fkey',
    'projects_family_id_fkey',
    'projects_primary_owner_family_member_id_fkey',
    'projects_created_by_family_member_id_fkey',
    'project_tasks_owner_family_member_id_fkey',
    'project_budget_entries_recorded_by_family_member_id_fkey',
    'sessions_user_account_id_fkey',
    'scout_scheduled_runs_family_id_fkey',
    'scout_scheduled_runs_member_id_fkey',
  ]::text[])
ORDER BY conname;
```

Expected row count: **68**. `purchase_requests_linked_grocery_item_id_fkey` is excluded because its source public table is dropped; any canonical mutual FK is PR 2.4 DDL, not a recreation of the public FK.

## 3. Consumer manifest

Disposition meanings: `disable` means impossible to execute in the intermediate state; `rewire` means qualified canonical schema/table rewrite; `delete` means feature path removed; `acceptable-as-is` means current reference resolves to a kept table and is intentionally unchanged. A file with multiple owners cannot be marked complete until each owner has touched or explicitly dispositioned its portion.

### 3.1 Boot and health entrypoints
| Entrypoint | Context | DB contract touched | Current behavior | Intermediate-state behavior | Owner | Disposition |
| --- | --- | --- | --- | --- | --- | --- |
| backend/start.sh | boot | runs migrate.py, seed.py, uvicorn | seed.py currently aborts startup after 057 | End Phase 1: crashes; after PR 2.1 could accidentally seed scout.families if not guarded | PR 1.5 | disable or guard seed.py; `/health` 200 required |
| backend/migrate.py | boot | public._scout_migrations only | safe | safe if migration tree valid | PR 1.5/PR 2.0 | acceptable-as-is; add failure poller grep for ERROR applying |
| backend/seed.py | boot | Family, FamilyMember, RoleTier, RoleTierOverride unqualified | crashes on dropped public.families | high search-path resurrection risk after PR 2.1 | PR 1.5 immediate + PR 3.1 long-term | PR 1.5 disable/guard; PR 3.1 rewrite or retire |
| backend/app/main.py lifespan | boot | imports routes; starts scheduler only if env not false | safe with scheduler disabled | unsafe if scheduler enabled before Phase 3/5 | PR 1.5 + PR 5.3 | acceptable if env guard verified; scheduler cannot enable before Phase 5 |
| backend/app/database.py | DB engine + session module (added v1.1.1) | sets connection-time `SET search_path TO public, scout`; defines SessionLocal and Base | safe; engine boots whether or not domain tables exist | this file is the literal mechanism §4 describes — every unqualified name resolves through this search_path; once PR 2.1 creates `scout.families` etc., the same hook is what enables silent resurrection | PR 1.5 (verify) + Phase 3 sweep (consider scout-first or scout-only search_path once rewires complete) | acceptable-as-is for PR 1.5; tree was missing from manifest v1.1, surfaced during PR 2.0 grep audit |
| GET /health | boot/healthcheck | no DB | safe only after uvicorn starts | safe | PR 1.5 | must return 200 after PR 1.5 |
| GET /ready | readiness | UserAccount ORM unqualified in try/except | returns 200 not_ready until identity rebuilt/rewired | resolves to scout.user_accounts after PR 2.1 if unqualified | PR 2.1 semantic guard + PR 3.1 final rewire (updated v1.1.2) | PR 2.1 patches maintenance-mode readiness semantics so the DB probe's success does not flip status to "ready" while `SCOUT_CANONICAL_MAINTENANCE=true`; PR 3.1 later rewires or schema-qualifies the underlying identity query. (added v1.1.2) |

### 3.2 Scheduler entrypoints
| Entrypoint | Context | DB contract touched | Current behavior | Intermediate-state behavior | Owner | Disposition |
| --- | --- | --- | --- | --- | --- | --- |
| backend/app/scheduler.py | scheduler module file (added v1.1.1) | hosts every _tick function plus start_scheduler/stop_scheduler; imports ParentActionItem, Family, FamilyMember, ScheduledRun, AnomalySuppression, nudges_service at module top | not imported while SCOUT_SCHEDULER_ENABLED=false; module-level model imports remain inert | module-level import must remain inert; tick functions retain search-path resurrection risk after PR 2.1/2.5 (covered by per-function rows below) | PR 1.5 (gate verify) + PR 5.3 (re-enable) | acceptable if env guard verified; per-function rewires owned by rows below; tree was missing from manifest v1.1, surfaced during PR 2.0 grep audit |
| start_scheduler / _tick | scheduler | advisory lock; ScheduledRun; calls all jobs | not imported while SCOUT_SCHEDULER_ENABLED=false | must remain impossible until Phase 5 | PR 1.5 + PR 5.3 | disable via env; verify import guard |
| run_morning_brief_tick / for_member | scheduler | families, family_members, scout_scheduled_runs, parent_action_items, ai_daily_insights via orchestrator | would fail before PR 2.1/2.5/3.3 | search-path resurrection after PR 2.1/2.5 is not enough; code still needs PR 3 rewires | PR 3.1 + PR 3.3 + PR 3.4 | keep disabled until Phase 5 |
| run_weekly_retro_tick / for_family | scheduler | families plus AI/parent action paths | disabled | same | PR 3.1 + PR 3.3 + PR 3.4 | keep disabled until Phase 5 |
| run_moderation_digest_tick / for_family | scheduler | family/member/AI/moderation/action item paths | disabled | same | PR 3.1 + PR 3.3 + PR 3.4 | keep disabled until Phase 5 |
| run_anomaly_scan_tick / for_family | scheduler | family/member/anomaly/action item paths | disabled | same | PR 3.1 + PR 3.4 | keep disabled until Phase 5 |
| push receipt poll tick | scheduler | scout.push_deliveries, scout.push_devices | disabled | tables retained but truncated | PR 5.3 | keep disabled until Phase 5 |
| nudges_service.run_nudge_scan_tick | scheduler | families, family_members, member_config, tasks/routines/events/personal_tasks/nudges | disabled | same-name tables can resurrect before nudge SQL is correct | PR 3.1 + PR 3.2 | keep disabled until Phase 5 |
| nudge_ai_discovery_tick | scheduler/AI | families, events, health_summaries, personal_tasks, connector configs, ai_* | disabled and AI off | must remain impossible until AI paths rewired | PR 3.3 + PR 3.4 | keep disabled until Phase 5 |
| process_pending_dispatches_tick | scheduler/push | nudge_dispatches/items, push deliveries/devices, family members | disabled | identity FK restore not sufficient; code rewire required | PR 3.1 + PR 3.2 + PR 5.3 | keep disabled until Phase 5 |

### 3.3 Request handlers
| File / entrypoint | Context | DB table/view references found | Qualification note | Intermediate-state risk | Owner PR(s) | Disposition |
| --- | --- | --- | --- | --- | --- | --- |
| backend/app/routes/admin/__init__.py | request handler | permissions | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/admin/affirmations.py | request handler | affirmations | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.7 sweep | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/admin/chores.py | request handler | routine_templates, routines | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/admin/config.py | request handler | family_members, household_rules, member_config, permissions | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/admin/integrations.py | request handler | connector_accounts | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.7 sweep | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/admin/nudge_rules.py | request handler | nudge_rules | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.7 sweep | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/admin/permissions.py | request handler | permissions | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/admin/quiet_hours.py | request handler | quiet_hours_family | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.7 sweep | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/affirmations.py | request handler | affirmations, member_config | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/ai.py | request handler | ai_messages, family_members, meals | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.3 + PR 3.4 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/allowance.py | request handler | allowance_ledger, families | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/auth.py | request handler | sessions | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/calendar.py | request handler | events, families | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/canonical.py | request handler | allowance_periods, calendar_exports, connector_accounts, connectors, daily_win_results, daily_wins, families, family_members, household_rules, notes, reward_policies, sync_jobs, sync_runs, task_completions, task_occurrences, task_templates, time_blocks, user_family_memberships, v_calendar_publication, v_control_plane, v_household_today, v_rewards_current_week | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.4 + PR 3.5 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/chores.py | request handler | families | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/daily_wins.py | request handler | families | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/dashboard.py | request handler | families | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/families.py | request handler | families, user_accounts | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/finance.py | request handler | bills, families | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/grocery.py | request handler | families | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/health_fitness.py | request handler | families | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/home_maintenance.py | request handler | families, notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/mcp_http.py | request handler | ai_tool_audit, scout_mcp_tokens | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.3 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/meals.py | request handler | families, meal_transformations, meals, notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/memory.py | request handler | notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/notes.py | request handler | families, notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/personal_tasks.py | request handler | families, personal_tasks | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/project_templates.py | request handler | project_templates, projects | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.7 sweep | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/projects.py | request handler | notes, personal_tasks, project_tasks, projects | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/routines.py | request handler | families, routines | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/storage.py | request handler | chore_templates, notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/routes/task_instances.py | request handler | families | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |

### 3.4 Service/transitive consumers
| File / entrypoint | Context | DB table/view references found | Qualification note | Intermediate-state risk | Owner PR(s) | Disposition |
| --- | --- | --- | --- | --- | --- | --- |
| backend/app/services/affirmation_engine.py | service/transitive | affirmations | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.7 sweep | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/ai_personality_service.py | service/transitive | family_members, member_config, notes, permissions, role_tier_overrides, role_tiers | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/allowance_canonical.py | service/transitive | reward_policies | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/auth_service.py | service/transitive | sessions | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/calendar_service.py | service/transitive | event_attendees, events | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/canonical_household_service.py | service/transitive | daily_win_results, routine_templates, routines, task_assignment_rules, task_completions, task_occurrences, task_templates | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/chores_canonical.py | service/transitive | routine_templates | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.7 sweep | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/daily_win_service.py | service/transitive | daily_wins, task_instances | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/dashboard_service.py | service/transitive | bills, events, meals, notes, permissions, personal_tasks, routines | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/finance_service.py | service/transitive | bills, notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/grocery_service.py | service/transitive | grocery_items, notes, permissions | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/health_fitness_service.py | service/transitive | activity_records, health_summaries, notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/integrations/apple_health.py | service/transitive | activity_records, health_summaries | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/integrations/base.py | service/transitive | connector_mappings, connectors, events | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/integrations/google_calendar.py | service/transitive | connector_mappings, events | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/integrations/nike_run_club.py | service/transitive | activity_records, connector_mappings | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/integrations/ynab.py | service/transitive | bills, connector_mappings | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/integrations_canonical.py | service/transitive | connector_accounts | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.7 sweep | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/meals_service.py | service/transitive | meals, notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/notes_service.py | service/transitive | notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/nudge_ai_discovery.py | service/transitive | ai_messages, events, families, family_members, personal_tasks, routines, task_instances | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.3 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/nudge_rule_validator.py | service/transitive | bills, chore_templates, event_attendees, events, families, family_members, personal_tasks, routines, task_instances | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/nudges_service.py | service/transitive | event_attendees, events, families, family_members, member_config, nudge_dispatch_items, nudge_dispatches, nudge_rules, parent_action_items, personal_tasks, quiet_hours_family, routines, task_instances | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/payout_service.py | service/transitive | allowance_ledger, daily_wins | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 + PR 3.4 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/permissions.py | service/transitive | household_rules, member_config, permissions, role_tier_overrides, role_tier_permissions, role_tiers | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/personal_tasks_service.py | service/transitive | notes, personal_tasks, task_instances | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/project_aggregation.py | service/transitive | personal_tasks, project_tasks, projects | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/project_service.py | service/transitive | notes, personal_tasks, projects | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/task_generation_service.py | service/transitive | chore_templates, routines, task_instances | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 | rewire/disable/delete per owner; no unowned skip |
| backend/app/services/weekly_meal_plan_service.py | service/transitive | grocery_items, meals, notes, permissions | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/services/connectors/base.py | service/transitive (added v1.1.1) | connector ABC + status/freshness enums; no DB queries | comment-level only | none from this file directly | PR 3.4 (audit only) | acceptable-as-is; comment-only hits; tree was missing from manifest v1.1, surfaced during PR 2.0 grep audit |
| backend/services/connectors/registry.py | service/transitive (added v1.1.1) | adapter registry mapping connector_key string → adapter class; no DB queries | refs are string keys, not table names | adapter instantiation may transitively read scout.connector_accounts via SyncService | PR 3.4 (audit only) | acceptable-as-is; key strings are data not consumers |
| backend/services/connectors/sync_persistence.py | service/transitive (added v1.1.1) | DAL writing scout.sync_runs, scout.connector_accounts, scout.connector_event_log, scout.stale_data_alerts; raw SQL with qualified scout.* names | qualified scout.* throughout; no resurrection risk | none if qualification audit confirms | PR 3.4 (qualified-name audit) | acceptable-as-is provided audit confirms every reference is `scout.*` |
| backend/services/connectors/sync_service.py | service/transitive (added v1.1.1) | sync orchestration façade; calls sync_persistence DAL; references qualified scout.* tables in module docstring | safe pre-sync (façade only); real sync loop in follow-up packet | when sync activates, transitive risk through persistence layer | PR 3.4 + PR 5.3 (sync re-enable) | acceptable-as-is until sync packet lands; gate alongside scheduler re-enable |
| backend/services/connectors/google_calendar/adapter.py | service/transitive (added v1.1.1) | Block 3 quiet baseline; references scout.external_calendar_events, scout.calendar_exports in comments and shape; no live HTTP yet | qualified refs in comments; clientless no-op | when client wires in, writes flow through sync_persistence (qualified) | PR 3.4 + PR 5.3 | acceptable-as-is; canonical qualified refs already in place |
| backend/services/connectors/{apple_health,exxir,greenlight,hearth_display,nike_run_club,rex,ynab}/* (rolled-up, added v1.1.1) | service/transitive | seven peer connectors structurally identical to google_calendar; mostly Block 2 stubs raising NotImplementedError | currently no DB writes; same Block 3 trajectory as google_calendar | parallel resurrection risk to google_calendar once each client wires in | PR 3.4 + PR 5.3 | treat as a single rewire decision; do not split into seven; promotes from rolled-up to per-file rows only when an individual peer flags grep hits |

### 3.5 AI/tool/MCP consumers
| File / entrypoint | Context | DB table/view references found | Qualification note | Intermediate-state risk | Owner PR(s) | Disposition |
| --- | --- | --- | --- | --- | --- | --- |
| backend/app/ai/anomalies.py | AI/tool/transitive | ai_homework_sessions, meals, parent_action_items, routines, sessions | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.3 + PR 3.4 | rewire/disable/delete per owner; no unowned skip |
| backend/app/ai/context.py | AI/tool/transitive | events, families, meals, member_config, notes, permissions, routines | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/ai/homework.py | AI/tool/transitive | ai_homework_sessions, sessions | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.3 | rewire/disable/delete per owner; no unowned skip |
| backend/app/ai/insights.py | AI/tool/transitive | ai_daily_insights, bills | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.3 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/ai/memory.py | AI/tool/transitive | family_members, notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/ai/orchestrator.py | AI/tool/transitive | ai_conversations, ai_messages, events, meals, parent_action_items, routines | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 + PR 3.3 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/ai/personality_defaults.py | AI/tool/transitive | member_config | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/ai/pricing.py | AI/tool/transitive | ai_messages, family_members | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.3 | rewire/disable/delete per owner; no unowned skip |
| backend/app/ai/provider.py | AI/tool/transitive | events | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/ai/retro.py | AI/tool/transitive | daily_wins, meal_reviews, meals, notes, parent_action_items, sessions | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/ai/tools.py | AI/tool/transitive | bills, chore_templates, events, family_members, grocery_items, meal_plans, meals, notes, parent_action_items, personal_tasks, projects, routines | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/scout_mcp/server.py | AI/tool/MCP standalone server (added v1.1.1) | exposes 8 read-only tools (get_family_schedule, get_tasks_summary, get_current_meal_plan, get_grocery_list, get_action_inbox, get_recent_briefs, get_homework_summary, get_ai_usage); lazy-imports app.database.SessionLocal; tools transitively touch parent_action_items, ai_daily_insights, ai_homework_sessions, ai_messages, events, personal_tasks, routines/task_instances, weekly_meal_plans, grocery_items, meals via existing services | not imported by FastAPI app; runnable via `python -m scout_mcp` only when SCOUT_MCP_TOKEN + SCOUT_MCP_FAMILY_ID are set | inherits the resurrection risk of every service it calls; reachable only when operator explicitly launches the MCP subprocess | PR 3.3 + PR 3.4 + PR 3.5 | rewire each tool's underlying query when its §3.X owner rewires; backend/scout_mcp/__main__.py is the runnable entrypoint that imports server.main; tree was missing from manifest v1.1, surfaced during PR 2.0 grep audit |

### 3.6 ORM model contracts
| File / entrypoint | Context | DB table/view references found | Qualification note | Intermediate-state risk | Owner PR(s) | Disposition |
| --- | --- | --- | --- | --- | --- | --- |
| backend/app/models/__init__.py | ORM model contract | connectors, meals, notes, personal_tasks, projects | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/access.py | ORM model contract | families, family_members, household_rules, member_config, permissions, role_tier_overrides, role_tiers | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/action_items.py | ORM model contract | families, family_members, parent_action_items | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/affirmations.py | ORM model contract | affirmation_delivery_log, affirmation_feedback, affirmations, family_members | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/ai.py | ORM model contract | ai_conversations, ai_messages, ai_tool_audit, families, family_members | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.3 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/calendar.py | ORM model contract | event_attendees, events, families, family_members, task_instances | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/canonical.py | ORM model contract | connector_accounts, connectors, families, family_members, reward_policies, routine_templates, user_accounts | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/connectors.py | ORM model contract | connector_configs, connector_mappings, families, family_members | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/finance.py | ORM model contract | bills, families, family_members, notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/foundation.py | ORM model contract | families, family_members, sessions, user_accounts | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/grocery.py | ORM model contract | families, family_members, grocery_items, notes, purchase_requests, weekly_meal_plans | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/health_fitness.py | ORM model contract | activity_records, families, family_members, health_summaries, notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/home_maintenance.py | ORM model contract | families, family_members, home_assets, home_zones, maintenance_instances, maintenance_templates, notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/homework.py | ORM model contract | ai_conversations, ai_homework_sessions, families, family_members | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.3 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/life_management.py | ORM model contract | allowance_ledger, chore_templates, daily_wins, families, family_members, routine_steps, routines, task_instance_step_completions, task_instances | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.4 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/meals.py | ORM model contract | dietary_preferences, families, family_members, meal_plans, meal_reviews, meals, notes, weekly_meal_plans | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/notes.py | ORM model contract | families, family_members, notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/nudge_rules.py | ORM model contract | families, family_members, nudge_rules | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/nudges.py | ORM model contract | family_members, nudge_dispatch_items, nudge_dispatches, parent_action_items, push_deliveries | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/personal_tasks.py | ORM model contract | events, families, family_members, notes, personal_tasks, project_tasks | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/projects.py | ORM model contract | families, family_members, notes, personal_tasks, project_budget_entries, project_milestones, project_tasks, project_template_tasks, project_templates, projects | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/push.py | ORM model contract | family_members, push_deliveries, push_devices | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/quiet_hours.py | ORM model contract | families, member_config, quiet_hours_family | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/scheduled.py | ORM model contract | ai_daily_insights, families, family_members, scout_scheduled_runs | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.3 | rewire/disable/delete per owner; no unowned skip |
| backend/app/models/tier5.py | ORM model contract | ai_conversations, families, family_members, family_memories, meals, planner_bundle_applies, scout_anomaly_suppressions, scout_mcp_tokens | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.3 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |

### 3.7 Scripts, tests, frontend, CI, smoke
| File / entrypoint | Context | DB table/view references found | Qualification note | Intermediate-state risk | Owner PR(s) | Disposition |
| --- | --- | --- | --- | --- | --- | --- |
| backend/seed_smoke.py | operator smoke seed | home_assets, home_zones, meals, notes, permissions, role_tiers | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/conftest.py | backend test/fixture | routines | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_affirmations.py | backend test/fixture | affirmation_delivery_log, affirmation_feedback, affirmations | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_ai_context.py | backend test/fixture | families, permissions | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_ai_conversation_resume.py | backend test/fixture | meals | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_ai_discovery_service.py | backend test/fixture | ai_conversations, ai_messages, connector_configs, connectors, events, families, health_summaries, nudge_dispatches, personal_tasks, routines | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.3 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_ai_personality.py | backend test/fixture | member_config, notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_ai_provider_retry.py | backend test/fixture | events | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_ai_routes.py | backend test/fixture | ai_messages, events, parent_action_items | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.3 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_ai_tools.py | backend test/fixture | families, family_members, notes, permissions | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_auth.py | backend test/fixture | bills, events, families, meals, notes, sessions | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_calendar.py | backend test/fixture | events | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_canonical_session2.py | backend test/fixture | activity_events, allowance_periods, allowance_results, bill_snapshots, budget_snapshots, calendar_exports, connector_accounts, connector_configs, connector_event_log, connector_mappings, connectors, daily_win_results, device_registrations, events, external_calendar_events, families, family_members, greenlight_exports, household_rules, permissions, reward_extras_catalog, reward_ledger_entries, reward_policies, role_tier_overrides, role_tier_permissions, role_tiers, routine_steps, routine_templates, sessions, settlement_batches ... | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.4 + PR 3.5 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_canonical_session2_block2.py | backend test/fixture | calendar_exports, connectors, daily_win_results, families, family_members, household_rules, reward_policies, routine_steps, routine_templates, routines, standards_of_done, sync_jobs, task_assignment_rules, task_completions, task_occurrences, task_templates | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.4 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_canonical_session2_block3.py | backend test/fixture | calendar_exports, connector_accounts, connector_event_log, connectors, external_calendar_events, families, family_members, stale_data_alerts, sync_jobs, sync_runs, v_calendar_publication, v_control_plane | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_connector_ical.py | backend test/fixture | connector_configs, connector_mappings, connectors, events | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_family_projects.py | backend test/fixture | notes, personal_tasks, projects | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_health_fitness.py | backend test/fixture | notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_integrations.py | backend test/fixture | bills, connectors, events | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_meal_plan_dietary.py | backend test/fixture | meals, notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_meals.py | backend test/fixture | meals, notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_meals_routes.py | backend test/fixture | families, meals | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_member_maintenance.py | backend test/fixture | families | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_notes.py | backend test/fixture | notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_nudge_rule_validator.py | backend test/fixture | ai_messages, event_attendees, events, permissions, personal_tasks, task_instances | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.3 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_nudges.py | backend test/fixture | events, family_members, member_config, notes, nudge_dispatch_items, nudge_dispatches, nudge_rules, personal_tasks, push_deliveries, quiet_hours_family, task_instances | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_payout.py | backend test/fixture | daily_wins | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_personal_tasks.py | backend test/fixture | personal_tasks | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_qa.py | backend test/fixture | ai_conversations, events, grocery_items, planner_bundle_applies | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.3 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_r3_migrations.py | backend test/fixture | connector_accounts, household_rules, member_config, reward_policies, routine_templates, routines | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.4 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_scheduler_tier1.py | backend test/fixture | bills | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_storage.py | backend test/fixture | chore_templates | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_tenant_isolation.py | backend test/fixture | families, routines | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_tier2.py | backend test/fixture | daily_wins, meal_reviews, meals, sessions | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.4 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_tier3.py | backend test/fixture | events, families, meals, notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_tier4.py | backend test/fixture | events, grocery_items, meals, routines, sessions | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_tier5.py | backend test/fixture | events, grocery_items, meals, personal_tasks | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| backend/tests/test_weekly_meal_plans.py | backend test/fixture | meals, permissions | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| scout-ui/lib/allowance.ts | frontend auto-writer/API client | daily_wins, reward_policies | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 + PR 3.4 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| scout-ui/lib/api.ts | frontend auto-writer/API client | allowance_ledger, bills, chore_templates, connector_accounts, events, families, meals, member_config, notes, permissions, routines, sessions | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.2 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| scout-ui/lib/auth.tsx | frontend auto-writer/API client | meals | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| scout-ui/lib/chores.ts | frontend auto-writer/API client | routines | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| scout-ui/lib/config.ts | frontend auto-writer/API client | member_config | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| scout-ui/lib/constants.ts | frontend auto-writer/API client | meals | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| scout-ui/lib/errorReporter.ts | frontend auto-writer/API client | notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| scout-ui/lib/format.ts | frontend auto-writer/API client | events | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| scout-ui/lib/meal_plan_hooks.ts | frontend auto-writer/API client (added v1.1.1) | shared loaders for Meals pages; calls fetchCurrentWeeklyPlan from ./api; references `meals` only in module docstring | docstring-only mention; no direct DB | inherits api.ts risk via `./api` import | PR 3.4 + PR 3.6 | acceptable-as-is; consumes api.ts not DB; tree was missing from manifest v1.1, surfaced during PR 2.0 grep audit |
| scout-ui/lib/meals.ts | frontend auto-writer/API client | meals | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| scout-ui/lib/mockScout.ts | frontend auto-writer/API client | meals | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| scout-ui/lib/permissions.ts | frontend auto-writer/API client | permissions | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| scout-ui/lib/projects.ts | frontend auto-writer/API client | notes, project_templates, projects | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| scout-ui/lib/seedData.ts | frontend auto-writer/API client | notes, projects, sessions | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| scout-ui/lib/types.ts | frontend auto-writer/API client | notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| scripts/ai_cost_report.py | operator script | bills | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| scripts/provision_smoke_child.py | operator script | families, family_members, role_tier_overrides, role_tiers, user_accounts | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| scripts/quiesce_prod.py | operator script | scout_scheduled_runs | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| scripts/unquiesce_prod.py | operator script | scout_scheduled_runs | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| smoke-tests/tests/affirmations.spec.ts | deployed smoke/front-end E2E | affirmations | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| smoke-tests/tests/ai-personality.spec.ts | deployed smoke/front-end E2E | member_config | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| smoke-tests/tests/ai-streaming-depth.spec.ts | deployed smoke/front-end E2E | events, families | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| smoke-tests/tests/allowance-adjustments.spec.ts | deployed smoke/front-end E2E | families | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| smoke-tests/tests/data-entry.spec.ts | deployed smoke/front-end E2E | events, meals | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| smoke-tests/tests/interaction-audit.spec.ts | deployed smoke/front-end E2E | meals | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| smoke-tests/tests/interaction-contract.spec.ts | deployed smoke/front-end E2E | meals, notes | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 or PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| smoke-tests/tests/meal-base-cooks.spec.ts | deployed smoke/front-end E2E | meals | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| smoke-tests/tests/meals-subpages.spec.ts | deployed smoke/front-end E2E | meals | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| smoke-tests/tests/nudges-phase-4.spec.ts | deployed smoke/front-end E2E | personal_tasks | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.2 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| smoke-tests/tests/projects.spec.ts | deployed smoke/front-end E2E | projects | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| smoke-tests/tests/responsive.spec.ts | deployed smoke/front-end E2E | meals | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| smoke-tests/tests/surfaces.spec.ts | deployed smoke/front-end E2E | meals | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.4 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |
| smoke-tests/tests/write-paths.spec.ts | deployed smoke/front-end E2E | families, meals | unqualified unless file explicitly contains scout.*; raw grep only | see section 4 if any same-name Phase 2 table exists | PR 3.1 + PR 3.4 + PR 3.6 | rewire/disable/delete per owner; no unowned skip |

## 4. Intermediate-state resolver table

Because connections set `search_path TO public, scout`, these unqualified names can change behavior as Phase 2 creates same-name scout tables. Every row marked `RESURRECTION` must be disabled or rewritten before the phase boundary where resolution changes.
| Unqualified name | End Phase 1 | End PR 2.1 | End PR 2.2 | End PR 2.3 | End PR 2.4 | End PR 2.5 | End Phase 2 | Owner | Flag |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| activity_records | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| ai_conversations | MISSING | MISSING | MISSING | scout.ai_conversations | scout.ai_conversations | scout.ai_conversations | scout.ai_conversations | PR 3.3 | RESURRECTION at PR 2.3 |
| ai_daily_insights | MISSING | MISSING | MISSING | scout.ai_daily_insights | scout.ai_daily_insights | scout.ai_daily_insights | scout.ai_daily_insights | PR 3.3 | RESURRECTION at PR 2.3 |
| ai_homework_sessions | MISSING | MISSING | MISSING | scout.ai_homework_sessions | scout.ai_homework_sessions | scout.ai_homework_sessions | scout.ai_homework_sessions | PR 3.3 | RESURRECTION at PR 2.3 |
| ai_messages | MISSING | MISSING | MISSING | scout.ai_messages | scout.ai_messages | scout.ai_messages | scout.ai_messages | PR 3.3 | RESURRECTION at PR 2.3 |
| ai_tool_audit | MISSING | MISSING | MISSING | scout.ai_tool_audit | scout.ai_tool_audit | scout.ai_tool_audit | scout.ai_tool_audit | PR 3.3 | RESURRECTION at PR 2.3 |
| allowance_ledger | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| bills | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| chore_templates | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.2 | no same-name resurrection; remains missing until rewired/deleted |
| connector_configs | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| connector_mappings | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| daily_wins | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.2 | no same-name resurrection; remains missing until rewired/deleted |
| dietary_preferences | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| event_attendees | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| events | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| families | MISSING | scout.families | scout.families | scout.families | scout.families | scout.families | scout.families | PR 3.1 | RESURRECTION at PR 2.1 |
| family_members | MISSING | scout.family_members | scout.family_members | scout.family_members | scout.family_members | scout.family_members | scout.family_members | PR 3.1 | RESURRECTION at PR 2.1 |
| family_memories | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| grocery_items | MISSING | MISSING | MISSING | MISSING | scout.grocery_items | scout.grocery_items | scout.grocery_items | PR 3.4/3.6 | RESURRECTION at PR 2.4 |
| health_summaries | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| meal_plan_entries | public/scout retained | public/scout retained | public/scout retained | public/scout retained | scout.meal_plan_entries | scout.meal_plan_entries | scout.meal_plan_entries | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| meal_plans | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| meal_reviews | MISSING | MISSING | MISSING | MISSING | scout.meal_reviews | scout.meal_reviews | scout.meal_reviews | PR 3.4/3.6 | RESURRECTION at PR 2.4 |
| meal_staples | public/scout retained | public/scout retained | public/scout retained | public/scout retained | scout.meal_staples | scout.meal_staples | scout.meal_staples | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| meal_transformations | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| meal_weekly_plans | public/scout retained | public/scout retained | public/scout retained | public/scout retained | scout.meal_weekly_plans | scout.meal_weekly_plans | scout.meal_weekly_plans | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| meals | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| member_config | MISSING | scout.member_config | scout.member_config | scout.member_config | scout.member_config | scout.member_config | scout.member_config | PR 3.1 | RESURRECTION at PR 2.1 |
| member_dietary_preferences | public/scout retained | public/scout retained | public/scout retained | public/scout retained | scout.member_dietary_preferences | scout.member_dietary_preferences | scout.member_dietary_preferences | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| notes | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| parent_action_items | MISSING | MISSING | MISSING | MISSING | MISSING | scout.parent_action_items | scout.parent_action_items | PR 3.4/3.6 | RESURRECTION at PR 2.5 |
| personal_tasks | MISSING | MISSING | scout.personal_tasks | scout.personal_tasks | scout.personal_tasks | scout.personal_tasks | scout.personal_tasks | PR 3.2 | RESURRECTION at PR 2.2 |
| planner_bundle_applies | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| purchase_requests | MISSING | MISSING | MISSING | MISSING | scout.purchase_requests | scout.purchase_requests | scout.purchase_requests | PR 3.4/3.6 | RESURRECTION at PR 2.4 |
| role_tier_overrides | MISSING | scout.role_tier_overrides | scout.role_tier_overrides | scout.role_tier_overrides | scout.role_tier_overrides | scout.role_tier_overrides | scout.role_tier_overrides | PR 3.1 | RESURRECTION at PR 2.1 |
| role_tiers | MISSING | scout.role_tiers | scout.role_tiers | scout.role_tiers | scout.role_tiers | scout.role_tiers | scout.role_tiers | PR 3.1 | RESURRECTION at PR 2.1 |
| routine_steps | MISSING | MISSING | scout.routine_steps | scout.routine_steps | scout.routine_steps | scout.routine_steps | scout.routine_steps | PR 3.2 | RESURRECTION at PR 2.2 |
| routine_templates | MISSING | MISSING | scout.routine_templates | scout.routine_templates | scout.routine_templates | scout.routine_templates | scout.routine_templates | PR 3.4/3.6 | RESURRECTION at PR 2.2 |
| routines | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.2 | no same-name resurrection; remains missing until rewired/deleted |
| scout_anomaly_suppressions | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| scout_mcp_tokens | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |
| task_instance_step_completions | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.2 | no same-name resurrection; remains missing until rewired/deleted |
| task_instances | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.2 | no same-name resurrection; remains missing until rewired/deleted |
| task_occurrence_step_completions | public/scout retained | public/scout retained | scout.task_occurrence_step_completions | scout.task_occurrence_step_completions | scout.task_occurrence_step_completions | scout.task_occurrence_step_completions | scout.task_occurrence_step_completions | PR 3.2 | no same-name resurrection; remains missing until rewired/deleted |
| task_occurrences | MISSING | MISSING | scout.task_occurrences | scout.task_occurrences | scout.task_occurrences | scout.task_occurrences | scout.task_occurrences | PR 3.2 | RESURRECTION at PR 2.2 |
| task_templates | MISSING | MISSING | scout.task_templates | scout.task_templates | scout.task_templates | scout.task_templates | scout.task_templates | PR 3.2 | RESURRECTION at PR 2.2 |
| user_accounts | MISSING | scout.user_accounts | scout.user_accounts | scout.user_accounts | scout.user_accounts | scout.user_accounts | scout.user_accounts | PR 3.1 | RESURRECTION at PR 2.1 |
| weekly_meal_plans | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | PR 3.4/3.6 | no same-name resurrection; remains missing until rewired/deleted |

At end Phase 3, every row above must be one of: qualified canonical reference, deleted feature path, disabled until future sprint, or acceptable kept-public table. At end Phase 5, scheduler, AI, smoke, and frontend auto-writers may only run after their rows are in the qualified/deleted/disabled/acceptable state.

**Note on /ready observability (added v1.1.2):** the `user_accounts` resurrection at end of PR 2.1 is partially observable via `/ready`'s DB probe — the unqualified `UserAccount` query that currently fails (because `public.user_accounts` is dropped and `scout.user_accounts` does not yet exist) will start succeeding after PR 2.1 creates `scout.user_accounts`. PR 2.1 gate criterion 9 (§6) requires patching `/ready` so the probe's success does not flip the status field to `"ready"` while `SCOUT_CANONICAL_MAINTENANCE=true`. The probe still executes for resurrection observability; only the status field is gated. PR 3.1 owns the final rewire of the underlying identity query.

## 5. PR ownership map

| PR / step | Scope | Owns | Cannot leave to later PR |
| --- | --- | --- | --- |
| PR 1.5 | Boot stabilization | Guard/disable `backend/seed.py`; add mandatory maintenance guard for every non-health/non-ready endpoint that can execute legacy DB code; prove app starts and `/health` returns 200; verify scheduler and AI env guards are off | Cannot create canonical identity tables before seed.py is guarded and request-time legacy DB execution is blocked |
| PR 2.0 | Manifest + verification tooling | Commit this manifest; add scripts to verify table inventory, FK manifest, old-reference grep, resolver state, migration mirror; capture live post-057 schema query output | Cannot change schema except tooling |
| PR 2.1 | Identity/member_config/role_tiers + 63 FK restores + /ready semantic patch | Build scout.families, family_members, user_accounts, role_tiers, role_tier_overrides, member_config; seed role_tiers; restore all identity-target FKs including sessions and scout_scheduled_runs. PR 2.1 also owns the /ready maintenance semantic patch in `backend/app/main.py`: while `SCOUT_CANONICAL_MAINTENANCE=true`, /ready must not report `"status": "ready"` regardless of DB probe outcome. PR 3.1 still owns the final canonical identity rewire of the underlying UserAccount query. (added v1.1.2) | Cannot leave unqualified legacy consumers enabled merely because scout.* now exists |
| PR 2.2 | Chores/tasks + 4 FK restores | Build/rebuild task/routine/task occurrence tables; add task_templates/task_occurrences FKs; preserve routine_steps second FK; ALTER existing standards_of_done/daily_win_results as needed | Cannot rely on CREATE IF NOT EXISTS against existing tables |
| PR 2.3 | AI schema | Build scout.ai_* tables preserving metadata and homework subject CHECK | Cannot re-enable AI |
| PR 2.4 | Meals/grocery/purchases schema | Build scout meal/grocery/purchase tables and define canonical mutual FK behavior | Cannot leave meals route old reader to scout.meal_transformations |
| PR 2.5 | Parent action items + rewards | Build scout.parent_action_items and rewards tables; restore nudge_dispatches.parent_action_item_id FK; enforce action_type CHECK | Cannot close Phase 2 with missing parent-action FK |
| PR 2.6 | FK reconciliation gate | Verify all 68 recreate FKs in section 2 present in pg_constraint with target schema scout where required; verify no NO_RECREATE FK present on public purchase_requests | Cannot start Phase 3 until exact expected set passes |
| PR 3.1 | Identity/auth/member_config/boot scripts | Rewire boot seed/provisioning identity paths, auth, family, permissions, member_config, role_tiers, routes/ai identity lookups, frontend identity/config types | Cannot leave seed.py as only disabled if long-term script still legacy |
| PR 3.2 | Chores/tasks/personal_tasks/nudges | Rewire chores, routines, task occurrences, personal_tasks, dashboard, canonical household, nudges_service task/event portions, AI task tools | Cannot rely on accidental PR 2.2 resolver changes |
| PR 3.3 | AI persistence/tools | Rewire orchestrator, AI conversation routes, tool audit logging, daily insights, homework sessions, MCP tool writes where AI persistence involved | Cannot re-enable AI until Phase 5 |
| PR 3.4.0 | Orphan public-table product decisions | Produce Andrew-approved disposition for each table in section 1.1.1 before implementation: rebuild canonical target, delete feature, disable feature, or defer with non-executable proof | Cannot start PR 3.4 with any orphan table undecided |
| PR 3.4 | Meals/grocery/purchases/parent-action/misc domains | Rewire meals/grocery/purchases/parent action; execute the PR 3.4.0 dispositions for notes, bills, health/activity, events/calendar, connector mappings/configs, memory, planner, anomaly, and MCP token legacy paths | Cannot use vague remaining-domains language |
| PR 3.5 | Views | Rebuild scout.v_household_today and scout.v_rewards_current_week against canonical scout tables only | Cannot close without v_rewards_current_week |
| PR 3.6 | Scripts/tests/smoke/frontend | Rewrite seed_smoke, smoke provisioning, backend tests/fixtures/factories, smoke-tests, scout-ui API/types/push writers | Cannot re-enable smoke-deployed or run provisioning before this passes |
| PR 3.7 | Final old-contract sweep | Zero unowned old public table/column refs; resolver table rows all dispositioned; backend tests pass per maintenance-window expectations | Cannot close Phase 3 with grep skips |
| Phase 5 global reseed | Global seed rows | Reseed role_tiers if not done, permissions, role_tier_permissions, connectors, affirmations before permission-gated acceptance checks | Cannot invite/configure family before permissions exist |
| Phase 5 family reseed/bootstrap | Andrew bootstrap and family rows | Bootstrap Andrew, then family-scoped household_rules/time_blocks, then invite/configure, then acceptance checklist | Cannot run scheduler/AI/smoke before acceptance gates |

## 6. Gate criteria per PR

### PR 1.5 gate

- `backend/start.sh` must not execute legacy `seed.py` against the post-057 schema unless `seed.py` is fully guarded for canonical-maintenance mode.
- PR 1.5 must add production maintenance middleware or an equivalent pre-handler guard. While canonical-rewrite maintenance mode is enabled, every non-health/non-ready endpoint that can reach legacy DB code must return controlled HTTP 503 before route/service logic executes.
- The guard allowlist is limited to `/health` and `/ready` unless the PR handoff names an additional endpoint and proves it does not touch dropped/recreated DB contracts. `/api/auth/bootstrap` is not automatically allowlisted in PR 1.5; it becomes eligible only after the Phase 3/Phase 5 bootstrap gate says so.
- `python backend/migrate.py` must skip already-applied migrations cleanly.
- Uvicorn must start; `GET /health` must return HTTP 200.
- Scheduler import must remain gated by `SCOUT_SCHEDULER_ENABLED=false`; AI writes remain gated by `SCOUT_ENABLE_AI=false`.
- PR handoff must state whether seed.py is `disabled`, `guarded no-op`, `rewritten`, or `deleted`, and must state the maintenance-guard env var/default.

### PR 2.0 gate

- This manifest is committed unchanged except for file path normalization.
- Add/run a manifest checker that verifies: public table set after 057 is exactly `_scout_migrations`, `sessions`, `scout_scheduled_runs`; scout table set equals retained 53; dropped views from 053 are absent; migrations 053-057 mirrored in `backend/` and `database/`.
- Add/run old-reference grep over backend, scripts, tests, scout-ui, smoke-tests, and workflows. The result must map every hit to section 3 owner.
- Capture live production schema output before PR 2.1. If it differs from the manifest, stop.

### PR 2.1 gate

(Criteria 1-5 unchanged from v1.1; criteria 6-9 added v1.1.2 per ChatGPT pre-draft tertiary review.)

1. `scout.families`, `scout.family_members`, `scout.user_accounts`, `scout.role_tiers`, `scout.role_tier_overrides`, and `scout.member_config` exist as base tables, not views.
2. `scout.role_tiers` contains exactly the six required natural-key rows before any role-tier-permission reseed: `DISPLAY_ONLY`, `PRIMARY_PARENT`, `PARENT`, `TEEN`, `YOUNG_CHILD`, `CHILD`. No `ADULT`/lowercase legacy tiers without Andrew approval.
3. Every section-2 FK owned by PR 2.1 is present with the same constraint name, same source column, same ON DELETE, and target schema rewritten to scout.
4. Resolver audit shows every PR 2.1 resurrection row is either disabled or has a Phase 3 owner. No unqualified legacy path may be newly executable unless explicitly accepted.
5. Backend still boots and `/health` still returns 200.
6. **Rebuilt-table contract parity gate** (added v1.1.2). PR 2.1 must prove the following objects are present after migration `058_*.sql` lands, in addition to the six base tables themselves:

    - **Internal FKs:** `family_members_family_id_fkey`, `user_accounts_family_member_id_fkey`, `role_tier_overrides_family_member_id_fkey`, `role_tier_overrides_role_tier_id_fkey`, `member_config_family_member_id_fkey`, `member_config_updated_by_fkey`.
    - **PKs:** `families_pkey`, `family_members_pkey`, `user_accounts_pkey`, `role_tiers_pkey`, `role_tier_overrides_pkey`, `member_config_pkey`.
    - **Unique and CHECK constraints:** `member_config_family_member_id_key_key`, `uq_role_tier_overrides_member`, `uq_role_tiers_name`, `chk_family_members_role` (lowercase `adult`/`child` only — preserve snapshot casing), `chk_user_accounts_auth_provider`, `chk_user_accounts_email_auth`.
    - **Indexes:** `idx_family_members_family_id`, `idx_user_accounts_family_member_id`, `uq_user_accounts_email` (partial, `WHERE email IS NOT NULL`), `idx_role_tier_overrides_role_tier_id`, `idx_member_config_member`.
    - **Triggers:** `trg_families_updated_at`, `trg_family_members_updated_at`, `trg_user_accounts_updated_at`, `trg_role_tiers_updated_at`, `trg_role_tier_overrides_updated_at`, `trg_member_config_updated_at`. All must invoke `public.set_updated_at()` — do not normalize to `clock_timestamp()` or any other function; preserve the snapshot contract.

    Per-table contract source-of-truth is `docs/plans/_snapshots/2026-04-22_pre_rewrite_full.sql`. Naive copy from `public.<table>` to `scout.<table>` is the correct base; subtleties to preserve verbatim from the snapshot include `now()` defaults (do not normalize to `clock_timestamp()`), partial unique on `user_accounts.email`, lowercase `adult`/`child` in `chk_family_members_role`.

7. **Migration qualification gate** (added v1.1.2). PR 2.1's mirrored migration SQL (`backend/migrations/058_*.sql` and `database/migrations/058_*.sql`) must contain:

    - Zero unqualified `CREATE TABLE`; every `CREATE TABLE` writes `scout.<table>` explicitly.
    - Zero unqualified `ALTER TABLE`; every `ALTER TABLE` writes `scout.<table>` or `public.<table>` explicitly.
    - Zero unqualified `REFERENCES`; every FK writes `scout.<target>(id)` or `public.<target>(id)` explicitly.
    - Zero unqualified `CREATE INDEX` or `CREATE UNIQUE INDEX ... ON`; every index target writes `scout.<table>` or `public.<table>` explicitly.
    - Zero unqualified `CREATE TRIGGER ... ON`; every trigger target writes `scout.<table>` explicitly.
    - Zero unqualified DML or query references inside seed/verification SQL; every `INSERT INTO`, `UPDATE`, `DELETE FROM`, `FROM`, and `JOIN` touching PR 2.1 tables must use `scout.<table>` or `public.<table>` explicitly.
    - Zero `CREATE TABLE IF NOT EXISTS`; the six identity/config tables must use plain `CREATE TABLE` and fail loudly on collision. Retained source tables must never be `CREATE`d in PR 2.1.
    - Zero `NOT VALID` constraints unless followed by `VALIDATE CONSTRAINT` in the same migration. Default expectation: all six internal rebuilt-table FKs and all 63 PR 2.1 §2 FKs land with `convalidated = true`.
    - Backend/database migration mirror must be byte-identical for `058_*.sql`.

    Rationale: `migrate.py` does not set `search_path` at migration time. PR 2.1 is the first canonical builder, so every table-bearing DDL and DML reference must be schema-qualified at draft time, not cleaned up during review.

8. **§2 FK restore parity gate** (added v1.1.2). PR 2.1 owns exactly 63 of the 68 expected post-Phase-2 §2 FKs. Per-target subset (per ChatGPT review):

    - 27 FKs targeting `scout.families(id)`.
    - 28 FKs targeting `scout.family_members(id)`.
    - 6 FKs targeting `scout.user_accounts(id)`.
    - 2 FKs targeting `scout.role_tiers(id)` (the `role_tier_permissions_role_tier_id_fkey` and `user_family_memberships_role_tier_id_fkey` rows).
    - 0 FKs targeting `scout.role_tier_overrides(id)` in PR 2.1's owned subset.

    Each FK must preserve the original constraint name, source column, and `ON DELETE` action from the §2 manifest, with target schema rewritten from `public.*` to `scout.*`. All must end with `convalidated = true`. PR 2.6 still owns the final 68-row post-Phase-2 reconciliation.

9. **/ready maintenance semantic gate** (added v1.1.2). PR 2.1 must patch `backend/app/main.py`'s `/ready` handler so that while `SCOUT_CANONICAL_MAINTENANCE=true`, the response body must not report `"status": "ready"` regardless of DB probe outcome. Required end state: HTTP 200 with a body containing at least `{"status": "not_ready", "reason": "canonical_maintenance", "database_reachable": <bool>}` when the maintenance flag is on. Extra diagnostic fields are allowed, but `status` must not be `"ready"` while maintenance is on. The DB probe should still execute (it is the live demonstration of §4 resurrection landing on the canonical path) but its success must not flip the status field while maintenance is on.

    Rationale: at end of PR 2.1, `scout.user_accounts` exists, so the unqualified `UserAccount` query in `/ready` will start succeeding. Without this patch, `/ready` would report `"ready"` while every product endpoint still returns 503. That is an observability semantic failure, even though it is not a DB safety failure. Smoke verification (per the PR 1.5 handoff): re-curl `/ready` after PR 2.1 deploy and confirm the body changes from current `{not_ready, relation user_accounts does not exist}` to `{not_ready, canonical_maintenance, database_reachable: true}`.

### PR 2.2 gate

- Rebuilt task/routine tables exist with full DDL contracts and v5.1 deltas.
- Both required `scout.routine_steps` FKs exist.
- Every section-2 FK owned by PR 2.2 is present.
- `CREATE TABLE IF NOT EXISTS` is not accepted as proof for tables that already existed; explicit ALTER/constraint verification required.
- Resolver audit covers `routine_steps` and `personal_tasks` resurrection.

### PR 2.3 gate
- All five scout.ai_* tables exist with required CHECK/default/index contracts; `ai_messages.metadata` preserved.
- Resolver audit covers all unqualified `ai_*` legacy references. AI remains disabled.

### PR 2.4 gate
- Meal/grocery/purchase canonical tables exist with explicit CHECK/default/index contracts.
- Mutual `grocery_items`/`purchase_requests` behavior is intentionally defined in scout schema; do not copy broken public mutual FK blindly.
- Resolver audit covers `grocery_items`, `purchase_requests`, `meal_reviews` same-name resurrection.

### PR 2.5 gate
- `scout.parent_action_items` exists and CHECK accepts exactly the 9 action_type values named in section 1.5.
- `scout.nudge_dispatches.parent_action_item_id_fkey` is restored to `scout.parent_action_items(id) ON DELETE SET NULL`.
- Rewards tables exist or are ALTERed as needed; existing retained tables must not be assumed created by no-op DDL.

### PR 2.6 gate
- Section 2 query returns exactly 68 rows.
- Every returned FK definition matches the manifest owner state.
- `purchase_requests_linked_grocery_item_id_fkey` is not present on `public.purchase_requests` because the source table is gone.
- Phase 3 may not start until this gate passes.

### PR 3.4.0 orphan-table product-decision gate

- Before PR 3.4 implementation starts, section 1.1.1 must have an Andrew-approved disposition for every orphan public table.
- The approved disposition document must be committed or linked from the PR handoff and must include: table, impacted backend files, impacted frontend/API surfaces, chosen action, owner PR, and acceptance test.
- If any orphan table is marked `rebuild canonical target`, the target table must be added to section 1 and any required FKs must be added to section 2 before implementation.
- If any orphan table is marked `delete feature`, all consumers in section 3 must be deleted or hard-disabled; leaving stale code for PR 3.7 sweep is not allowed unless the path is proven non-executable.
- PR 3.4 cannot merge if any section 1.1.1 row remains undecided.

### Phase 3 PR gates
- Each PR handoff includes: old table names searched, old column names searched, files touched, files intentionally skipped with reason, DB-native dependencies checked, and resolver rows closed.
- Skip without disposition is PR reject.
- PR 3.7 must prove every section-3 consumer has been touched by an owner PR or explicitly marked acceptable-as-is/deleted/disabled.
- Backend tests must pass or failures must be limited to explicitly disabled Phase 5 surfaces.

### Phase 5 gates
- Global seed rows before permission-gated flows: role_tiers, permissions, role_tier_permissions, connectors, affirmations. Role tiers are the exact six snapshot names; no `ADULT` row.
- Family-scoped rows after Andrew bootstrap: household_rules, time_blocks.
- `SCOUT_ENABLE_AI=true` only after AI write/read acceptance. `SCOUT_SCHEDULER_ENABLED=true` only after scheduler paths pass. Smoke-deployed auto-trigger only after smoke accounts are provisioned.

## 7. Sequencing constraints

| Ordering | Reason |
| --- | --- |
| PR 1.5 before PR 2.1 | Prevents legacy seed.py from running against newly created scout.families/family_members/role_tiers via search-path resurrection. |
| PR 2.0 before PR 2.1 | Execution must be manifest-driven; no more scope-by-plan-text. |
| PR 2.1 before any FK restore targeting identity | Identity tables must exist and role_tiers must be seeded before dependent FKs and natural-key role mappings. |
| PR 2.2 before PR 3.2 | Task/routine tables must exist before code rewires to them. |
| PR 2.3 before PR 3.3 | AI tables must exist before AI code rewires. |
| PR 2.4 before PR 3.4 meals/grocery | Canonical meal/grocery/purchase tables must exist before route/service rewires. |
| PR 2.5 before PR 3.4 parent action/nudges | parent_action_items must exist and nudge FK restored before scheduler/nudge paths can be re-enabled. |
| PR 3.4.0 before PR 3.4 | Orphan public-table feature decisions are product decisions; implementation cannot decide them implicitly. |
| PR 2.6 before any Phase 3 PR merge | The FK manifest must pass before consumers are rewired. |
| Global reseed before invite/configure | Permissions and role mappings must exist before Andrew invites family or runs permission-gated UI flows. |
| Family-scoped reseed after Andrew bootstrap | household_rules and time_blocks need a real family_id. |
| Main can boot after PR 1.5 | Maintenance window allows 500s; it does not allow failed deploys after PR 1.5. |

## 8. Seed appendices

### 8.1 Permission keys

```text
account.update_self
action_items.resolve
admin.manage_config
admin.manage_permissions
admin.view_config
admin.view_permissions
affirmations.manage_config
ai.clear_own_history
ai.edit_any_personality
ai.edit_own_personality
ai.manage
ai.manage_own_conversations
allowance.manage_config
allowance.run_payout
calendar.manage_self
calendar.publish
chore.complete_self
chores.manage_config
connectors.manage
connectors.view_health
dashboard.view_parent
display.view_only
family.manage_accounts
family.manage_learning_notes
family.manage_members
grocery.add_item
grocery.approve
grocery.manage_config
grocery.request_item
home.complete_instance
home.manage_assets
home.manage_templates
home.manage_zones
home.view
household.complete_any_task
household.complete_own_task
household.edit_rules
meal.review_self
meal_plan.approve
meal_plan.generate
meals.manage_config
meals.manage_staples
notes.manage_any
nudges.configure
nudges.view_own
project_tasks.update_assigned
project_templates.manage
project_templates.view
projects.create
projects.manage_any
projects.manage_own
projects.view
purchase_request.approve
purchase_request.submit
push.register_device
push.revoke_device
push.send_to_member
push.view_delivery_log
quiet_hours.manage
rewards.approve_payout
rewards.manage_config
rewards.view_own_payout
scout_ai.manage_toggles
tasks.manage_self
```

### 8.2 Role tier to permission mapping

**CHILD** (20 permissions)

```text
account.update_self
ai.clear_own_history
ai.edit_own_personality
ai.manage_own_conversations
chore.complete_self
grocery.request_item
home.complete_instance
home.view
household.complete_own_task
meal.review_self
nudges.view_own
project_tasks.update_assigned
project_templates.view
projects.manage_own
projects.view
purchase_request.submit
push.register_device
push.revoke_device
rewards.view_own_payout
tasks.manage_self
```

**DISPLAY_ONLY** (1 permissions)

```text
display.view_only
```

**PARENT** (63 permissions)

```text
account.update_self
action_items.resolve
admin.manage_config
admin.manage_permissions
admin.view_config
admin.view_permissions
ai.clear_own_history
ai.edit_any_personality
ai.edit_own_personality
ai.manage
ai.manage_own_conversations
allowance.manage_config
allowance.run_payout
calendar.manage_self
calendar.publish
chore.complete_self
chores.manage_config
connectors.manage
connectors.view_health
dashboard.view_parent
display.view_only
family.manage_accounts
family.manage_learning_notes
family.manage_members
grocery.add_item
grocery.approve
grocery.manage_config
grocery.request_item
home.complete_instance
home.manage_assets
home.manage_templates
home.manage_zones
home.view
household.complete_any_task
household.complete_own_task
household.edit_rules
meal.review_self
meal_plan.approve
meal_plan.generate
meals.manage_config
meals.manage_staples
notes.manage_any
nudges.configure
nudges.view_own
project_tasks.update_assigned
project_templates.manage
project_templates.view
projects.create
projects.manage_any
projects.manage_own
projects.view
purchase_request.approve
purchase_request.submit
push.register_device
push.revoke_device
push.send_to_member
push.view_delivery_log
quiet_hours.manage
rewards.approve_payout
rewards.manage_config
rewards.view_own_payout
scout_ai.manage_toggles
tasks.manage_self
```

**PRIMARY_PARENT** (64 permissions)

```text
account.update_self
action_items.resolve
admin.manage_config
admin.manage_permissions
admin.view_config
admin.view_permissions
affirmations.manage_config
ai.clear_own_history
ai.edit_any_personality
ai.edit_own_personality
ai.manage
ai.manage_own_conversations
allowance.manage_config
allowance.run_payout
calendar.manage_self
calendar.publish
chore.complete_self
chores.manage_config
connectors.manage
connectors.view_health
dashboard.view_parent
display.view_only
family.manage_accounts
family.manage_learning_notes
family.manage_members
grocery.add_item
grocery.approve
grocery.manage_config
grocery.request_item
home.complete_instance
home.manage_assets
home.manage_templates
home.manage_zones
home.view
household.complete_any_task
household.complete_own_task
household.edit_rules
meal.review_self
meal_plan.approve
meal_plan.generate
meals.manage_config
meals.manage_staples
notes.manage_any
nudges.configure
nudges.view_own
project_tasks.update_assigned
project_templates.manage
project_templates.view
projects.create
projects.manage_any
projects.manage_own
projects.view
purchase_request.approve
purchase_request.submit
push.register_device
push.revoke_device
push.send_to_member
push.view_delivery_log
quiet_hours.manage
rewards.approve_payout
rewards.manage_config
rewards.view_own_payout
scout_ai.manage_toggles
tasks.manage_self
```

**TEEN** (22 permissions)

```text
account.update_self
ai.clear_own_history
ai.edit_own_personality
ai.manage_own_conversations
calendar.manage_self
chore.complete_self
grocery.add_item
home.complete_instance
home.view
household.complete_own_task
meal.review_self
nudges.view_own
project_tasks.update_assigned
project_templates.view
projects.create
projects.manage_own
projects.view
purchase_request.submit
push.register_device
push.revoke_device
rewards.view_own_payout
tasks.manage_self
```

**YOUNG_CHILD** (17 permissions)

```text
ai.clear_own_history
ai.edit_own_personality
ai.manage_own_conversations
chore.complete_self
grocery.request_item
home.complete_instance
home.view
household.complete_own_task
nudges.view_own
project_tasks.update_assigned
project_templates.view
projects.manage_own
projects.view
push.register_device
push.revoke_device
rewards.view_own_payout
tasks.manage_self
```

### 8.3 Household rules
| rule_key | rule_value | description |
| --- | --- | --- |
| one_owner_per_task | true | If a task is shared, it is orphaned. Every task has exactly one owner. |
| finishable_lists | true | Routines doable in 15 to 25 minutes per block. |
| explicit_standards_of_done | true | No vague tasks. Every chore has a written standard of done. |
| quiet_enforcement | true | The checklist + deadline is the boss, not parent mood. |
| one_reminder_max | true | One reminder. After that: "Check Hearth." No nagging. |
| scout_ai.toggles | {"allow_general_chat": true, "push_notifications": true, "allow_homework_help": true, "proactive_suggestions": true} | None |
| allowance.rules | {"streak_bonus_days": 7, "streak_bonus_cents": 200, "max_weekly_bonus_cents": 500, "requires_approval_for_bonus": true} | None |
| chores.rules | {"max_daily_pts": 100, "streak_bonus_pts": 20, "streak_bonus_days": 7, "requires_check_off": true} | None |
| grocery.stores | {"stores": [{"id": "costco", "kind": "bulk", "name": "Costco"}, {"id": "tom_thumb", "kind": "local", "name": "Tom Thumb"}]} | None |
| grocery.categories | {"categories": ["Produce", "Protein", "Pantry", "Dairy", "Requested"]} | None |
| grocery.approval_rules | {"auto_approve_under_cents": 500, "require_approval_for_teens": false, "require_approval_for_children": true} | None |
| meals.plan_rules | {"batch_cook_day": "sunday", "week_starts_on": "monday", "dinners_per_week": 7, "generation_style": "balanced"} | None |
| meals.rating_scale | {"max_rating": 5, "repeat_options": ["repeat", "tweak", "retire"], "require_notes_for_retire": false} | None |
| meals.dietary_notes | {"categories": ["No restrictions", "Vegetarian-lean", "No onions", "Dairy-free", "Gluten-free", "Nut-free"]} | None |
| rewards.tiers | {"tiers": [{"id": "small", "label": "Small reward", "example": "30 min extra screen time", "cost_pts": 200}, {"id": "medium", "label": "Medium reward", "example": "Movie night pick", "cost_pts": 500}, {"id": "large", "label": "Large reward", "example": "Day trip pick", "cost_pts": 1000}]} | None |
| rewards.redemption_rules | {"require_approval": true, "allow_negative_balance": false, "max_redemptions_per_week": 2} | None |

### 8.4 Time blocks
| block_key | label | start | end | weekday | weekend | sort_order |
| --- | --- | --- | --- | --- | --- | --- |
| morning | Morning Routine | 06:30:00 | 07:30:00 | t | t | 10 |
| after_school | After School Routine | 15:00:00 | 17:30:00 | t | f | 20 |
| evening | Evening Routine | 20:00:00 | 21:30:00 | t | t | 30 |
| power_60 | Saturday Power 60 | 10:00:00 | 11:00:00 | f | t | 40 |

### 8.5 Affirmations
| text | category | tone | philosophy | audience | length | active |
| --- | --- | --- | --- | --- | --- | --- |
| You are building something that matters. | growth | encouraging | discipline | general | short | t |
| Every small step today adds up to something big tomorrow. | growth | encouraging | resilience | general | short | t |
| Your effort today is shaping who you become. | growth | encouraging | discipline | general | short | t |
| Progress is progress, no matter how small. | growth | encouraging | gratitude | general | short | t |
| There is always something to be thankful for. | gratitude | encouraging | gratitude | general | short | t |
| The people around you are a gift. Tell them. | gratitude | encouraging | family-first | parent | short | t |
| Gratitude turns what we have into enough. | gratitude | reflective | gratitude | general | short | t |
| Hard work compounds. Show up again today. | discipline | challenging | discipline | general | short | t |
| Comfort is the enemy of growth. Push a little further. | discipline | challenging | resilience | parent | short | t |
| What you do when no one is watching defines you. | discipline | challenging | discipline | general | short | t |
| Tough days build tough people. | resilience | reflective | resilience | general | short | t |
| You have survived every hard day so far. That is 100%% success. | resilience | reflective | resilience | general | short | t |
| Storms do not last forever. Neither does this. | resilience | reflective | resilience | general | short | t |
| A kind word at breakfast sets the tone for the whole day. | family | practical | family-first | parent | short | t |
| Ask your kids one real question today. Then listen. | family | practical | family-first | parent | short | t |
| Showing up is the most important thing you can do as a parent. | family | encouraging | family-first | parent | short | t |
| You can do hard things. | growth | encouraging | resilience | child | short | t |
| Being kind is always the right choice. | kindness | encouraging | gratitude | child | short | t |
| Mistakes help you learn. Keep trying. | growth | encouraging | resilience | child | short | t |
| Your family is proud of you. | family | encouraging | family-first | child | short | t |
| Doing your best is always enough. | growth | encouraging | discipline | child | short | t |
| You are fearfully and wonderfully made. | faith | encouraging | faith-based | general | short | t |
| Let your light shine before others. | faith | encouraging | faith-based | general | short | t |
| The way you handle today's small frustrations is practice for life's bigger challenges. Stay steady. | resilience | reflective | resilience | parent | medium | t |
| Your children are watching how you treat yourself. Model grace, patience, and persistence. | family | reflective | family-first | parent | medium | t |

## 9. Additional runtime artifacts required before execution, not for authorship

The repo zip is sufficient to author this v1 manifest. Before PR 2.1 executes, Andrew or Code must still paste these runtime outputs into the PR 2.0 handoff:

1. Current production `_scout_migrations` top rows after PR 1.5 deploy.
2. Current production base-table list for schemas `public` and `scout`.
3. Current production `pg_constraint` FK list before PR 2.1.
4. Redacted Railway env snapshot proving scheduler and AI are disabled and bootstrap is enabled during the maintenance state.

If any runtime output contradicts this manifest, stop and amend the manifest before continuing.
