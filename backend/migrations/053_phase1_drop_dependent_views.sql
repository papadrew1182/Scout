-- Migration 053: Phase 1 PR 1.1 - drop scout.* views that depend on
-- tables scheduled for drop or rebuild in Phase 1.
--
-- Plan: docs/plans/2026-04-22_canonical_rewrite_v5_1_merged.md
--       Phase 1 PR 1.1.
--
-- Two categories of view are dropped here:
--
-- 1. Eight shim views at 022_session2_canonical.sql:183-190 that
--    SELECT * FROM the matching public.* table. PR 1.3 drops those
--    underlying public.* tables. Postgres DROP TABLE fails if a view
--    still depends on it; the plan forbids CASCADE. Views are dropped
--    now so PR 1.3's drops run clean. These views are NOT rebuilt;
--    Phase 2 replaces them with real tables in the scout schema.
--
-- 2. Two named views defined later in migration 022:
--       - scout.v_household_today (022:761)
--       - scout.v_rewards_current_week (022:794)
--    Both join public.family_members and/or scout.* tables scheduled
--    for drop in PR 1.1 or PR 1.3. Per v5.1 §Phase 3 PR 3.5,
--    v_household_today is rebuilt against the canonical tables.
--    v_rewards_current_week has no explicit rebuild home in v5.1
--    yet; see PR 1.1 handoff "open items" for the Phase 3 planning
--    flag.
--
-- Two other named views at 022:820 (scout.v_calendar_publication) and
-- 022:839 (scout.v_control_plane) are intentionally NOT dropped. Both
-- reference only retained scout.* tables and have no dependency on
-- Phase 1 drop targets.

BEGIN;

-- Category 1: eight shim views over public.* tables.
DROP VIEW IF EXISTS scout.families;
DROP VIEW IF EXISTS scout.family_members;
DROP VIEW IF EXISTS scout.user_accounts;
DROP VIEW IF EXISTS scout.sessions;
DROP VIEW IF EXISTS scout.role_tiers;
DROP VIEW IF EXISTS scout.role_tier_overrides;
DROP VIEW IF EXISTS scout.connector_mappings;
DROP VIEW IF EXISTS scout.connector_configs;

-- Category 2: named views over rebuild targets.
DROP VIEW IF EXISTS scout.v_household_today;
DROP VIEW IF EXISTS scout.v_rewards_current_week;

COMMIT;
