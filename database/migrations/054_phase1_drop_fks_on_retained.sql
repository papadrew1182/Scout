-- Migration 054: Phase 1 PR 1.1 - drop FKs on retained scout.* tables
-- that point at tables being dropped in PR 1.3 (public.*) or rebuilt
-- in Phase 2 (scout.*).
--
-- Plan: docs/plans/2026-04-22_canonical_rewrite_v5_1_merged.md
--       Phase 1 PR 1.1.
--
-- Pre-flight: docs/plans/2026-04-22_canonical_rewrite_v5_preflight.md
--             Part 1 (23 retained scout.* tables with FKs to rebuild
--             targets). Full scan during PR 1.1 execution surfaced
--             20 additional scout.* tables with FKs into PR 1.3 drop
--             targets that Part 1 did not cover; those are handled
--             in Section B below.
--
-- Why this exists:
--   PR 1.3 drops public.families, public.family_members,
--   public.user_accounts, public.role_tiers, and public.parent_action_items.
--   Migration 055 drops scout.task_templates and scout.task_occurrences.
--   Postgres DROP TABLE fails while any FK still references the target,
--   and the plan forbids CASCADE. This migration drops every such FK.
--   They will be recreated in Phase 2 PRs (2.1 / 2.2 / 2.5), with the
--   Phase 2 reconciliation gate (PR 2.6) enforcing completeness.
--
-- Structure:
--   Section A - 38 FK drops on the 24 retained tables whose matrix
--               rows in pre-flight Part 1 listed drop-worthy FKs.
--               Part 1's summary sentence said "23 of 26 retained
--               tables have FKs" and classified nudge_dispatch_items
--               as self-contained, but the row data for that table
--               did list family_member_id -> public.family_members
--               for drop. Counting by what the matrix actually
--               enumerated gives 24 tables / 38 individual FKs.
--   Section B - 27 FK drops on 20 additional retained scout.* tables
--               that Part 1 did not enumerate (finding during PR 1.1
--               execution). Recreate ownership for these is flagged
--               in the PR 1.1 handoff "Open items" section for Phase 2
--               planning.
--
-- FKs on retained scout.* tables that point ONLY at other retained
-- scout.* tables (e.g. nudge_dispatch_items.dispatch_id ->
-- scout.nudge_dispatches, push_deliveries.push_device_id ->
-- scout.push_devices, affirmation_feedback.affirmation_id ->
-- scout.affirmations) are intentionally preserved.
--
-- ALTER TABLE ... DROP CONSTRAINT IF EXISTS is idempotent. Safe to
-- re-run.

BEGIN;

-- ===========================================================================
-- SECTION A: 38 FKs on 24 retained scout.* tables whose Part 1 matrix
-- rows listed drop-worthy FKs (original v5.1 PR 1.1 scope).
-- ===========================================================================

-- A.1 Identity-target FKs (public.families, public.family_members,
-- public.user_accounts, public.role_tiers, public.parent_action_items -
-- all dropped in PR 1.3).

ALTER TABLE scout.affirmations
    DROP CONSTRAINT IF EXISTS affirmations_created_by_fkey,
    DROP CONSTRAINT IF EXISTS affirmations_updated_by_fkey;

ALTER TABLE scout.affirmation_feedback
    DROP CONSTRAINT IF EXISTS affirmation_feedback_family_member_id_fkey;

ALTER TABLE scout.affirmation_delivery_log
    DROP CONSTRAINT IF EXISTS affirmation_delivery_log_family_member_id_fkey;

ALTER TABLE scout.connector_accounts
    DROP CONSTRAINT IF EXISTS connector_accounts_family_id_fkey,
    DROP CONSTRAINT IF EXISTS connector_accounts_user_account_id_fkey;

ALTER TABLE scout.device_registrations
    DROP CONSTRAINT IF EXISTS device_registrations_user_account_id_fkey;

ALTER TABLE scout.home_assets
    DROP CONSTRAINT IF EXISTS home_assets_family_id_fkey;

ALTER TABLE scout.home_zones
    DROP CONSTRAINT IF EXISTS home_zones_family_id_fkey;

ALTER TABLE scout.household_rules
    DROP CONSTRAINT IF EXISTS household_rules_family_id_fkey;

ALTER TABLE scout.maintenance_instances
    DROP CONSTRAINT IF EXISTS maintenance_instances_family_id_fkey,
    DROP CONSTRAINT IF EXISTS maintenance_instances_owner_member_id_fkey,
    DROP CONSTRAINT IF EXISTS maintenance_instances_completed_by_member_id_fkey;

ALTER TABLE scout.maintenance_templates
    DROP CONSTRAINT IF EXISTS maintenance_templates_family_id_fkey,
    DROP CONSTRAINT IF EXISTS maintenance_templates_default_owner_member_id_fkey;

ALTER TABLE scout.nudge_dispatch_items
    DROP CONSTRAINT IF EXISTS nudge_dispatch_items_family_member_id_fkey;

ALTER TABLE scout.nudge_dispatches
    DROP CONSTRAINT IF EXISTS nudge_dispatches_family_member_id_fkey,
    DROP CONSTRAINT IF EXISTS nudge_dispatches_parent_action_item_id_fkey;

ALTER TABLE scout.nudge_rules
    DROP CONSTRAINT IF EXISTS nudge_rules_family_id_fkey,
    DROP CONSTRAINT IF EXISTS nudge_rules_created_by_family_member_id_fkey;

ALTER TABLE scout.push_deliveries
    DROP CONSTRAINT IF EXISTS push_deliveries_family_member_id_fkey;

ALTER TABLE scout.push_devices
    DROP CONSTRAINT IF EXISTS push_devices_family_member_id_fkey;

ALTER TABLE scout.quiet_hours_family
    DROP CONSTRAINT IF EXISTS quiet_hours_family_family_id_fkey;

ALTER TABLE scout.reward_policies
    DROP CONSTRAINT IF EXISTS reward_policies_family_id_fkey,
    DROP CONSTRAINT IF EXISTS reward_policies_family_member_id_fkey;

ALTER TABLE scout.role_tier_permissions
    DROP CONSTRAINT IF EXISTS role_tier_permissions_role_tier_id_fkey;

ALTER TABLE scout.user_family_memberships
    DROP CONSTRAINT IF EXISTS user_family_memberships_family_id_fkey,
    DROP CONSTRAINT IF EXISTS user_family_memberships_family_member_id_fkey,
    DROP CONSTRAINT IF EXISTS user_family_memberships_role_tier_id_fkey,
    DROP CONSTRAINT IF EXISTS user_family_memberships_user_account_id_fkey;

ALTER TABLE scout.user_preferences
    DROP CONSTRAINT IF EXISTS user_preferences_user_account_id_fkey;

-- A.2 Task-target FKs (scout.task_templates, scout.task_occurrences -
-- dropped in migration 055, rebuilt in Phase 2 PR 2.2). These four
-- source tables are retained per pre-flight Part 1; only the FKs
-- drop here.

ALTER TABLE scout.task_assignment_rules
    DROP CONSTRAINT IF EXISTS task_assignment_rules_task_template_id_fkey;

ALTER TABLE scout.task_completions
    DROP CONSTRAINT IF EXISTS task_completions_task_occurrence_id_fkey,
    DROP CONSTRAINT IF EXISTS task_completions_completed_by_fkey;

ALTER TABLE scout.task_notes
    DROP CONSTRAINT IF EXISTS task_notes_task_occurrence_id_fkey,
    DROP CONSTRAINT IF EXISTS task_notes_author_id_fkey;

ALTER TABLE scout.task_exceptions
    DROP CONSTRAINT IF EXISTS task_exceptions_task_occurrence_id_fkey,
    DROP CONSTRAINT IF EXISTS task_exceptions_created_by_fkey;

-- ===========================================================================
-- SECTION B: 27 FKs on 20 additional retained scout.* tables that
-- pre-flight Part 1 did not enumerate. Surfaced during PR 1.1
-- execution by full pg_dump scan of cross-schema FKs. Recreate
-- ownership is NOT yet assigned in Phase 2 plan text; see PR 1.1
-- handoff "Open items" for the list and the Phase 2 planning
-- follow-up.
--
-- Groupings match the handoff's Phase-2-ownership status:
--   B.1 Already in Phase 2 PR 2.5 "Build" list (owner exists, needs
--       explicit ALTER statements added to PR 2.5 or its follow-up).
--   B.2 In Phase 2 PR 2.2 "Build" list but table stays (additive DDL
--       is a no-op on existing tables; explicit ALTER needed).
--   B.3 Purely retained, no Phase 2 owner in current plan text.
-- ===========================================================================

-- B.1 Phase 2 PR 2.5 "Build" list.

ALTER TABLE scout.allowance_periods
    DROP CONSTRAINT IF EXISTS allowance_periods_family_id_fkey;

ALTER TABLE scout.allowance_results
    DROP CONSTRAINT IF EXISTS allowance_results_family_member_id_fkey;

ALTER TABLE scout.reward_extras_catalog
    DROP CONSTRAINT IF EXISTS reward_extras_catalog_family_id_fkey;

ALTER TABLE scout.reward_ledger_entries
    DROP CONSTRAINT IF EXISTS reward_ledger_entries_family_id_fkey,
    DROP CONSTRAINT IF EXISTS reward_ledger_entries_family_member_id_fkey;

ALTER TABLE scout.settlement_batches
    DROP CONSTRAINT IF EXISTS settlement_batches_family_id_fkey;

-- B.2 Phase 2 PR 2.2 "Build" list (table exists; CREATE IF NOT EXISTS
-- is a no-op; FKs need an explicit ALTER to re-add).

ALTER TABLE scout.standards_of_done
    DROP CONSTRAINT IF EXISTS standards_of_done_family_id_fkey;

ALTER TABLE scout.daily_win_results
    DROP CONSTRAINT IF EXISTS daily_win_results_family_id_fkey,
    DROP CONSTRAINT IF EXISTS daily_win_results_family_member_id_fkey;

-- B.3 Purely retained, no Phase 2 owner in current plan text.
-- Phase 2 reconciliation gate (PR 2.6) must be expanded to verify
-- these are re-added; see PR 1.1 handoff "Open items" for assignment.

ALTER TABLE scout.time_blocks
    DROP CONSTRAINT IF EXISTS time_blocks_family_id_fkey;

ALTER TABLE scout.calendar_exports
    DROP CONSTRAINT IF EXISTS calendar_exports_family_id_fkey;

ALTER TABLE scout.greenlight_exports
    DROP CONSTRAINT IF EXISTS greenlight_exports_family_member_id_fkey;

ALTER TABLE scout.activity_events
    DROP CONSTRAINT IF EXISTS activity_events_family_id_fkey,
    DROP CONSTRAINT IF EXISTS activity_events_family_member_id_fkey;

ALTER TABLE scout.external_calendar_events
    DROP CONSTRAINT IF EXISTS external_calendar_events_family_id_fkey;

ALTER TABLE scout.work_context_events
    DROP CONSTRAINT IF EXISTS work_context_events_family_id_fkey,
    DROP CONSTRAINT IF EXISTS work_context_events_user_account_id_fkey;

ALTER TABLE scout.budget_snapshots
    DROP CONSTRAINT IF EXISTS budget_snapshots_family_id_fkey;

ALTER TABLE scout.bill_snapshots
    DROP CONSTRAINT IF EXISTS bill_snapshots_family_id_fkey;

ALTER TABLE scout.travel_estimates
    DROP CONSTRAINT IF EXISTS travel_estimates_family_id_fkey;

ALTER TABLE scout.project_templates
    DROP CONSTRAINT IF EXISTS project_templates_family_id_fkey,
    DROP CONSTRAINT IF EXISTS project_templates_created_by_family_member_id_fkey;

ALTER TABLE scout.projects
    DROP CONSTRAINT IF EXISTS projects_family_id_fkey,
    DROP CONSTRAINT IF EXISTS projects_primary_owner_family_member_id_fkey,
    DROP CONSTRAINT IF EXISTS projects_created_by_family_member_id_fkey;

ALTER TABLE scout.project_tasks
    DROP CONSTRAINT IF EXISTS project_tasks_owner_family_member_id_fkey;

ALTER TABLE scout.project_budget_entries
    DROP CONSTRAINT IF EXISTS project_budget_entries_recorded_by_family_member_id_fkey;

COMMIT;
