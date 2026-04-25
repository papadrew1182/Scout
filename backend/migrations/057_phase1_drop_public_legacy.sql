-- Migration 057: Phase 1 PR 1.3 - drop public.* legacy tables.
--
-- Plan: docs/plans/2026-04-22_canonical_rewrite_v5_1_merged.md
--       Phase 1 PR 1.3.
--
-- Pre-flight: docs/plans/2026-04-22_canonical_rewrite_v5_preflight.md
--             Part 4.4 (RESTRICT FK chain), Part 5.1-5.5 (no
--             materialized views / sequences / enums / grants /
--             generated columns to worry about).
--
-- IMPORTANT - PLAN SUPERSESSION:
--   v5.1 Phase 1 PR 1.3 enumerates an 8-step drop order. Full
--   pg_dump scan during PR 1.3 scope review surfaced two ordering
--   bugs in that sequence:
--     (a) public.events has FK events_task_instance_id_fkey ->
--         public.task_instances, so events MUST drop before
--         task_instances. Plan put task_instances at step 2 and
--         events in step 8 ("any order"); step 2 would fail.
--     (b) public.ai_tool_audit, ai_homework_sessions,
--         family_memories, planner_bundle_applies all have SET NULL
--         FKs to public.ai_conversations, so all four MUST drop
--         before ai_conversations. Plan only flagged ai_messages
--         (CASCADE) as needing to precede ai_conversations.
--   Plan's step list is superseded by the 5-tier topological order
--   in Step B below. See PR 1.3 handoff for full discussion.
--
-- Scope:
--   - Drop 39 public.* tables (full drop set per v5.1 plan).
--   - Drop 4 explicit FKs that block the topology (3 on kept
--     public.* tables, 1 mutual breaker between grocery_items and
--     purchase_requests).
--   - Verify post-drop public.* BASE TABLE set equals exactly the
--     3 keepers: _scout_migrations, sessions, scout_scheduled_runs.
--
--   NOT touched:
--   - The 3 keepers above (per plan section 3).
--   - scout schema (PR 1.1 already cleared every cross-schema FK
--     from scout.* into the drop set; verified by full pg_dump
--     scan during PR 1.3 scope review).
--
-- No CASCADE anywhere. Per plan, every blocking dependency is
-- handled explicitly: FK drops in Step A, table drops in
-- topological order in Step B. DROP TABLE IF EXISTS for
-- idempotency.
--
-- Structure:
--   Step A - 4 explicit FK drops (3 on kept public.* tables for
--            the sessions / scout_scheduled_runs cross-FK problem
--            surfaced as O1 + O2' during PR 1.2 / 1.3 scope review;
--            1 mutual FK breaker on purchase_requests for the
--            grocery_items <-> purchase_requests circular
--            reference). The breaker side is the alphabetically-
--            later table in Tier 1; see Step A inline comment
--            for the rule.
--   Step B - 39 DROP TABLE IF EXISTS in 5-tier topological order:
--            Tier 1 (27 tables): no incoming FK from drop set
--                                after Step A.
--            Tier 2 (7 tables):  blocked only by Tier 1 tables.
--            Tier 3 (1 table):   task_instances (needs Tier 2's
--                                events to drop first).
--            Tier 4 (2 tables):  chore_templates, routines (need
--                                task_instances).
--            Tier 5 (2 tables):  families, family_members.
--   Step C - DO block asserting the public.* BASE TABLE set is
--            exactly {_scout_migrations, sessions,
--            scout_scheduled_runs}. Same pattern as 056's
--            set-match check.

BEGIN;

-- ===========================================================================
-- STEP A: explicit FK drops.
--
-- The 3 FKs on kept public.* tables (sessions + scout_scheduled_runs)
-- block dropping their respective targets. Pre-flight Part 1 missed
-- both because it scoped to scout.* sources only. Surfaced during
-- PR 1.2 (O1 - sessions) and PR 1.3 (O2' - scout_scheduled_runs)
-- scope reviews.
--
-- The 4th FK (purchase_requests_linked_grocery_item_id_fkey) breaks
-- the mutual FK pair grocery_items <-> purchase_requests. Rule for
-- breaking a mutual FK pair within an alphabetically-ordered tier:
-- drop the FK on the alphabetically-LATER table. Here that's
-- purchase_requests. After Step A: grocery_items still references
-- purchase_requests via fk_grocery_items_purchase_request (that FK
-- drops naturally with grocery_items at Tier 1 alphabetical
-- position 14), then purchase_requests drops at position 23 with
-- no remaining incoming refs. Dropping the other side instead
-- would leave purchase_requests still referencing grocery_items at
-- position 14, and DROP grocery_items would fail. Caught pre-push
-- by the intra-tier verification gate.
-- ===========================================================================

ALTER TABLE public.sessions
    DROP CONSTRAINT IF EXISTS sessions_user_account_id_fkey;

ALTER TABLE public.scout_scheduled_runs
    DROP CONSTRAINT IF EXISTS scout_scheduled_runs_family_id_fkey,
    DROP CONSTRAINT IF EXISTS scout_scheduled_runs_member_id_fkey;

ALTER TABLE public.purchase_requests
    DROP CONSTRAINT IF EXISTS purchase_requests_linked_grocery_item_id_fkey;

-- ===========================================================================
-- STEP B: 39 table drops in 5-tier topological order.
--
-- Each tier's tables can drop in any order WITHIN the tier (no
-- intra-tier blocking FKs). Tiers must drop in numerical order
-- because each later tier has incoming FKs from at least one
-- earlier-tier table.
--
-- No CASCADE. Per plan, blocking FKs handled in Step A and via
-- tier ordering.
-- ===========================================================================

-- ---- Tier 1: 27 tables with no incoming FK from any other
-- ----         drop-set table (after Step A). Drop in alphabetical
-- ----         order.

DROP TABLE IF EXISTS public.activity_records;
DROP TABLE IF EXISTS public.ai_daily_insights;
DROP TABLE IF EXISTS public.ai_homework_sessions;
DROP TABLE IF EXISTS public.ai_messages;
DROP TABLE IF EXISTS public.ai_tool_audit;
DROP TABLE IF EXISTS public.allowance_ledger;
DROP TABLE IF EXISTS public.bills;
DROP TABLE IF EXISTS public.connector_configs;
DROP TABLE IF EXISTS public.connector_mappings;
DROP TABLE IF EXISTS public.daily_wins;
DROP TABLE IF EXISTS public.dietary_preferences;
DROP TABLE IF EXISTS public.event_attendees;
DROP TABLE IF EXISTS public.family_memories;
DROP TABLE IF EXISTS public.grocery_items;
DROP TABLE IF EXISTS public.health_summaries;
DROP TABLE IF EXISTS public.meal_reviews;
DROP TABLE IF EXISTS public.meals;
DROP TABLE IF EXISTS public.member_config;
DROP TABLE IF EXISTS public.notes;
DROP TABLE IF EXISTS public.parent_action_items;
DROP TABLE IF EXISTS public.personal_tasks;
DROP TABLE IF EXISTS public.planner_bundle_applies;
DROP TABLE IF EXISTS public.purchase_requests;
DROP TABLE IF EXISTS public.role_tier_overrides;
DROP TABLE IF EXISTS public.scout_anomaly_suppressions;
DROP TABLE IF EXISTS public.scout_mcp_tokens;
DROP TABLE IF EXISTS public.task_instance_step_completions;

-- ---- Tier 2: 7 tables that lose their last incoming FK once
-- ----         Tier 1 drops. Drop in alphabetical order.

DROP TABLE IF EXISTS public.ai_conversations;
DROP TABLE IF EXISTS public.events;
DROP TABLE IF EXISTS public.meal_plans;
DROP TABLE IF EXISTS public.role_tiers;
DROP TABLE IF EXISTS public.routine_steps;
DROP TABLE IF EXISTS public.user_accounts;
DROP TABLE IF EXISTS public.weekly_meal_plans;

-- ---- Tier 3: task_instances. Blocked by events (Tier 2) due to
-- ----         events.task_instance_id FK; unblocked once Tier 2
-- ----         drops events.

DROP TABLE IF EXISTS public.task_instances;

-- ---- Tier 4: routines and chore_templates. Both blocked by
-- ----         task_instances (Tier 3).

DROP TABLE IF EXISTS public.chore_templates;
DROP TABLE IF EXISTS public.routines;

-- ---- Tier 5: families and family_members. The 2 high-fan-in
-- ----         identity tables. Once all earlier tiers drop, these
-- ----         have zero remaining incoming FKs (verified during
-- ----         scope review's Gate 1 check).

DROP TABLE IF EXISTS public.families;
DROP TABLE IF EXISTS public.family_members;

-- ===========================================================================
-- STEP C: post-drop set-match assertion. Asserts the public.* BASE
-- TABLE set equals exactly {_scout_migrations, sessions,
-- scout_scheduled_runs}. Raises EXCEPTION on either unexpected
-- presence (drop list missed something) or expected absence (drop
-- went too far). Same pattern as 056's set-match check.
-- ===========================================================================

DO $$
DECLARE
    expected_keepers text[] := ARRAY[
        '_scout_migrations',
        'scout_scheduled_runs',
        'sessions'
    ];
    actual_tables text[];
    unexpected text[];
    missing text[];
BEGIN
    SELECT COALESCE(array_agg(table_name ORDER BY table_name), ARRAY[]::text[])
    INTO actual_tables
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_type = 'BASE TABLE';

    SELECT COALESCE(array_agg(t ORDER BY t), ARRAY[]::text[])
    INTO unexpected
    FROM unnest(actual_tables) AS t
    WHERE t <> ALL(expected_keepers);

    SELECT COALESCE(array_agg(t ORDER BY t), ARRAY[]::text[])
    INTO missing
    FROM unnest(expected_keepers) AS t
    WHERE t <> ALL(actual_tables);

    IF array_length(unexpected, 1) IS NOT NULL THEN
        RAISE EXCEPTION
            'public.* BASE TABLE set after PR 1.3 drops contains unexpected tables: %. Drop list missed something or a new table was created during the migration window.',
            unexpected;
    END IF;

    IF array_length(missing, 1) IS NOT NULL THEN
        RAISE EXCEPTION
            'public.* BASE TABLE set after PR 1.3 drops is missing expected keepers: %. Drop went too far - one of _scout_migrations / sessions / scout_scheduled_runs was incorrectly dropped.',
            missing;
    END IF;
END $$;

COMMIT;
