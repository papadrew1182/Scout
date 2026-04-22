-- Migration 050: Sprint 05 Phase 2 - Quiet hours, batching, and
-- action_type widening for the proactive nudge engine.
--
-- Three deliverables per Sprint 05 revised plan Section 7 Phase 2:
--   1. scout.quiet_hours_family: family-wide quiet-hours window, one row per
--      family. Defaults to 22:00-07:00 local (1320..420). Per-member overrides
--      live in member_config (no schema change required).
--   2. Permission quiet_hours.manage for PARENT + PRIMARY_PARENT so the
--      family-wide window can be edited from the parent surface.
--   3. Widen chk_parent_action_items_action_type to include the five nudge.*
--      action types dispatched by the Phase 2 engine. Phase 1 shipped with
--      action_type='general' as a workaround; this migration lets the Inbox
--      row carry accurate nudge.{trigger_kind} semantics.
--
-- start_local_minute / end_local_minute are stored as minute-of-day integers
-- so the window is always interpreted in the family's local timezone at
-- evaluation time. The window may wrap past midnight (start > end), which is
-- the default configuration (22:00 -> 07:00 next day).
--
-- A zero-length window (start == end) is rejected by
-- chk_quiet_hours_family_start_end since it would be ambiguous (always on
-- vs. always off).
--
-- DISPLAY_ONLY excluded by existing repo convention.

BEGIN;

-- ============================================================================
-- scout.quiet_hours_family (family-wide quiet-hours window)
-- ============================================================================

CREATE TABLE IF NOT EXISTS scout.quiet_hours_family (
    id                   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id            uuid        NOT NULL UNIQUE
                                     REFERENCES public.families (id) ON DELETE CASCADE,
    start_local_minute   integer     NOT NULL DEFAULT 1320,
    end_local_minute     integer     NOT NULL DEFAULT 420,
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_quiet_hours_family_start_range
        CHECK (start_local_minute >= 0 AND start_local_minute < 1440),
    CONSTRAINT chk_quiet_hours_family_end_range
        CHECK (end_local_minute >= 0 AND end_local_minute < 1440),
    CONSTRAINT chk_quiet_hours_family_start_end
        CHECK (start_local_minute <> end_local_minute)
);

DROP TRIGGER IF EXISTS trg_quiet_hours_family_updated_at ON scout.quiet_hours_family;
CREATE TRIGGER trg_quiet_hours_family_updated_at
    BEFORE UPDATE ON scout.quiet_hours_family
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- Permission registration: quiet_hours.manage
-- ============================================================================

INSERT INTO scout.permissions (permission_key, description) VALUES
    ('quiet_hours.manage',
     'Manage family-wide quiet-hours window for Scout nudges')
ON CONFLICT (permission_key) DO NOTHING;

-- quiet_hours.manage: PARENT + PRIMARY_PARENT only
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM public.role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('PARENT', 'PRIMARY_PARENT')
  AND p.permission_key = 'quiet_hours.manage'
ON CONFLICT DO NOTHING;

-- ============================================================================
-- Widen chk_parent_action_items_action_type for nudge.* values
--
-- Original allowed set from migration 020_tier4.sql is preserved verbatim;
-- this migration only adds the five nudge.* trigger_kind-derived action types
-- so the Phase 2 dispatch path (Task 5) can write accurate Inbox semantics.
-- ============================================================================

ALTER TABLE public.parent_action_items
    DROP CONSTRAINT IF EXISTS chk_parent_action_items_action_type;

ALTER TABLE public.parent_action_items
    ADD CONSTRAINT chk_parent_action_items_action_type
    CHECK (action_type IN (
        -- Preserved verbatim from migration 020_tier4.sql
        'grocery_review',
        'purchase_request',
        'chore_override',
        'general',
        'meal_plan_review',
        'moderation_alert',
        'daily_brief',
        'weekly_retro',
        'moderation_digest',
        'anomaly_alert',
        -- Phase 2 additions for the nudge engine
        'nudge.overdue_task',
        'nudge.upcoming_event',
        'nudge.missed_routine',
        'nudge.custom_rule',
        'nudge.ai_suggested'
    ));

COMMIT;
