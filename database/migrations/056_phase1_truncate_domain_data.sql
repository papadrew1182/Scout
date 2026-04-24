-- Migration 056: Phase 1 PR 1.2 - truncate all retained scout.* tables
-- plus the two kept public.* exceptions (public.sessions,
-- public.scout_scheduled_runs).
--
-- Plan: docs/plans/2026-04-22_canonical_rewrite_v5_1_merged.md
--       Phase 1 PR 1.2.
--
-- Pre-flight: docs/plans/2026-04-22_canonical_rewrite_v5_preflight.md
--             Part 7 (zero-row verification method; SELECT COUNT(*)
--             per table, not pg_stat_user_tables).
--
-- Scope:
--   - 53 retained scout.* tables (58 defined across migrations 001-052,
--     minus the 5 dropped in PR 1.1 migration 055: task_templates,
--     task_occurrences, routine_templates, routine_steps,
--     meal_transformations).
--   - public.sessions (truncate allowed per plan §3, schema preserved).
--   - public.scout_scheduled_runs (truncate allowed per plan §3 AFTER
--     Phase 0 quiesce confirms no jobs running; already verified).
--   = 55 targets total.
--
--   NOT truncated:
--   - public._scout_migrations (migration tracker; protected per §3).
--   - Any public.* table in PR 1.3's drop list (those tables get
--     dropped outright in PR 1.3; truncate before drop is redundant).
--
-- SEED_REFERENCE tables are truncated per plan ("Don't skip-truncate")
-- and will be explicitly repopulated in Phase 5 PR 5.1:
-- scout.permissions, scout.role_tier_permissions, scout.connectors,
-- scout.affirmations, scout.household_rules, scout.time_blocks.
--
-- Structure:
--   1. TRUNCATE TABLE <55 targets> CASCADE as a single statement.
--      CASCADE is a safety net; all known inter-table FKs are within
--      the enumerated set (verified by the set-match check below).
--   2. Set-match check: assert the actual scout.* BASE TABLE set in
--      information_schema matches the 53-table enumeration. If any
--      unlisted scout.* table exists, stop-condition fires - CASCADE
--      may have silently truncated it, or our enumeration is stale.
--      Added at Andrew's request during PR 1.2 scope review.
--   3. Zero-row verification: DO block loops over all 55 truncated
--      targets, runs SELECT COUNT(*), RAISE EXCEPTION on any non-zero.
--      This honors plan's "SELECT COUNT(*) per truncated table within
--      same transaction. No pg_stat_user_tables."
--
-- All three steps run inside one transaction (BEGIN/COMMIT). Any
-- RAISE EXCEPTION rolls back the whole migration; migrate.py's
-- subsequent passes see the same state (idempotent TRUNCATE on
-- already-empty tables is a no-op).

BEGIN;

-- ===========================================================================
-- STEP 1: TRUNCATE all 55 targets.
-- ===========================================================================

TRUNCATE TABLE
    scout.activity_events,
    scout.affirmation_delivery_log,
    scout.affirmation_feedback,
    scout.affirmations,
    scout.allowance_periods,
    scout.allowance_results,
    scout.bill_snapshots,
    scout.budget_snapshots,
    scout.calendar_exports,
    scout.connector_accounts,
    scout.connector_event_log,
    scout.connectors,
    scout.daily_win_results,
    scout.device_registrations,
    scout.external_calendar_events,
    scout.greenlight_exports,
    scout.home_assets,
    scout.home_zones,
    scout.household_rules,
    scout.maintenance_instances,
    scout.maintenance_templates,
    scout.nudge_dispatch_items,
    scout.nudge_dispatches,
    scout.nudge_rules,
    scout.permissions,
    scout.project_budget_entries,
    scout.project_milestones,
    scout.project_tasks,
    scout.project_template_tasks,
    scout.project_templates,
    scout.projects,
    scout.push_deliveries,
    scout.push_devices,
    scout.quiet_hours_family,
    scout.reward_extras_catalog,
    scout.reward_ledger_entries,
    scout.reward_policies,
    scout.role_tier_permissions,
    scout.settlement_batches,
    scout.stale_data_alerts,
    scout.standards_of_done,
    scout.sync_cursors,
    scout.sync_jobs,
    scout.sync_runs,
    scout.task_assignment_rules,
    scout.task_completions,
    scout.task_exceptions,
    scout.task_notes,
    scout.time_blocks,
    scout.travel_estimates,
    scout.user_family_memberships,
    scout.user_preferences,
    scout.work_context_events,
    public.sessions,
    public.scout_scheduled_runs
    CASCADE;

-- ===========================================================================
-- STEP 2: Set-match check. Assert the scout.* BASE TABLE set in
-- information_schema matches the 53-table enumeration above. Stops
-- the migration (rollback) if any unlisted scout.* table exists,
-- which would mean either (a) CASCADE silently truncated an
-- unenumerated table, or (b) a scout.* table exists that this
-- migration is not aware of.
-- ===========================================================================

DO $$
DECLARE
    expected_tables text[] := ARRAY[
        'activity_events',
        'affirmation_delivery_log',
        'affirmation_feedback',
        'affirmations',
        'allowance_periods',
        'allowance_results',
        'bill_snapshots',
        'budget_snapshots',
        'calendar_exports',
        'connector_accounts',
        'connector_event_log',
        'connectors',
        'daily_win_results',
        'device_registrations',
        'external_calendar_events',
        'greenlight_exports',
        'home_assets',
        'home_zones',
        'household_rules',
        'maintenance_instances',
        'maintenance_templates',
        'nudge_dispatch_items',
        'nudge_dispatches',
        'nudge_rules',
        'permissions',
        'project_budget_entries',
        'project_milestones',
        'project_tasks',
        'project_template_tasks',
        'project_templates',
        'projects',
        'push_deliveries',
        'push_devices',
        'quiet_hours_family',
        'reward_extras_catalog',
        'reward_ledger_entries',
        'reward_policies',
        'role_tier_permissions',
        'settlement_batches',
        'stale_data_alerts',
        'standards_of_done',
        'sync_cursors',
        'sync_jobs',
        'sync_runs',
        'task_assignment_rules',
        'task_completions',
        'task_exceptions',
        'task_notes',
        'time_blocks',
        'travel_estimates',
        'user_family_memberships',
        'user_preferences',
        'work_context_events'
    ];
    actual_tables text[];
    unexpected text[];
    missing text[];
BEGIN
    SELECT COALESCE(array_agg(table_name ORDER BY table_name), ARRAY[]::text[])
    INTO actual_tables
    FROM information_schema.tables
    WHERE table_schema = 'scout'
      AND table_type = 'BASE TABLE';

    SELECT COALESCE(array_agg(t ORDER BY t), ARRAY[]::text[])
    INTO unexpected
    FROM unnest(actual_tables) AS t
    WHERE t <> ALL(expected_tables);

    SELECT COALESCE(array_agg(t ORDER BY t), ARRAY[]::text[])
    INTO missing
    FROM unnest(expected_tables) AS t
    WHERE t <> ALL(actual_tables);

    IF array_length(unexpected, 1) IS NOT NULL THEN
        RAISE EXCEPTION
            'scout.* table set mismatch: tables present in DB not in migration enumeration: %. CASCADE may have truncated these, or enumeration is stale.',
            unexpected;
    END IF;

    IF array_length(missing, 1) IS NOT NULL THEN
        RAISE EXCEPTION
            'scout.* table set mismatch: enumerated tables missing from DB: %. PR 1.1 drop may have removed unexpected tables, or enumeration is stale.',
            missing;
    END IF;
END $$;

-- ===========================================================================
-- STEP 3: Zero-row verification. Loops over all 55 truncated targets
-- and RAISE EXCEPTION on any non-zero count. Honors plan's "SELECT
-- COUNT(*) per truncated table within same transaction. No
-- pg_stat_user_tables."
-- ===========================================================================

DO $$
DECLARE
    targets text[] := ARRAY[
        'scout.activity_events',
        'scout.affirmation_delivery_log',
        'scout.affirmation_feedback',
        'scout.affirmations',
        'scout.allowance_periods',
        'scout.allowance_results',
        'scout.bill_snapshots',
        'scout.budget_snapshots',
        'scout.calendar_exports',
        'scout.connector_accounts',
        'scout.connector_event_log',
        'scout.connectors',
        'scout.daily_win_results',
        'scout.device_registrations',
        'scout.external_calendar_events',
        'scout.greenlight_exports',
        'scout.home_assets',
        'scout.home_zones',
        'scout.household_rules',
        'scout.maintenance_instances',
        'scout.maintenance_templates',
        'scout.nudge_dispatch_items',
        'scout.nudge_dispatches',
        'scout.nudge_rules',
        'scout.permissions',
        'scout.project_budget_entries',
        'scout.project_milestones',
        'scout.project_tasks',
        'scout.project_template_tasks',
        'scout.project_templates',
        'scout.projects',
        'scout.push_deliveries',
        'scout.push_devices',
        'scout.quiet_hours_family',
        'scout.reward_extras_catalog',
        'scout.reward_ledger_entries',
        'scout.reward_policies',
        'scout.role_tier_permissions',
        'scout.settlement_batches',
        'scout.stale_data_alerts',
        'scout.standards_of_done',
        'scout.sync_cursors',
        'scout.sync_jobs',
        'scout.sync_runs',
        'scout.task_assignment_rules',
        'scout.task_completions',
        'scout.task_exceptions',
        'scout.task_notes',
        'scout.time_blocks',
        'scout.travel_estimates',
        'scout.user_family_memberships',
        'scout.user_preferences',
        'scout.work_context_events',
        'public.sessions',
        'public.scout_scheduled_runs'
    ];
    t text;
    n bigint;
BEGIN
    FOREACH t IN ARRAY targets
    LOOP
        EXECUTE format('SELECT COUNT(*) FROM %s', t) INTO n;
        IF n > 0 THEN
            RAISE EXCEPTION 'TRUNCATE did not clear %: COUNT(*) = %', t, n;
        END IF;
    END LOOP;
END $$;

COMMIT;
