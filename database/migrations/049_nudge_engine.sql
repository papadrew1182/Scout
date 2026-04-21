-- Migration 049: Sprint 05 Phase 1 - Proactive Nudges Engine
--
-- Creates the parent-child dispatch schema for proactive nudges.
--   scout.nudge_dispatches      - one delivered artifact (Inbox row + at most one push)
--   scout.nudge_dispatch_items  - one source proposal attached to a dispatch,
--                                 where provenance and dedupe live
--
-- UNIQUE on nudge_dispatch_items.source_dedupe_key is the authoritative
-- dedupe boundary per revised Phase 1 plan section 4. Parent dispatch rows
-- are only written if at least one child source item inserts successfully.
--
-- occurrence_at_utc and occurrence_local_date capture the original source
-- event and never change when quiet hours delay delivery. deliver_after_utc
-- controls when a dispatch may actually be sent.
--
-- Permission keys:
--   nudges.view_own - all user tiers can view their own recent nudge dispatches.
--
-- DISPLAY_ONLY excluded by existing repo convention.

BEGIN;

-- ============================================================================
-- scout.nudge_dispatches (parent: one delivered artifact)
-- ============================================================================

CREATE TABLE IF NOT EXISTS scout.nudge_dispatches (
    id                      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_member_id        uuid        NOT NULL REFERENCES public.family_members (id) ON DELETE CASCADE,
    status                  text        NOT NULL DEFAULT 'pending',
    severity                text        NOT NULL DEFAULT 'normal',
    suppressed_reason       text,
    deliver_after_utc       timestamptz NOT NULL,
    delivered_at_utc        timestamptz,
    parent_action_item_id   uuid        REFERENCES public.parent_action_items (id) ON DELETE SET NULL,
    push_delivery_id        uuid REFERENCES scout.push_deliveries(id) ON DELETE SET NULL,
    delivered_channels      jsonb       NOT NULL DEFAULT '[]'::jsonb,
    source_count            integer     NOT NULL DEFAULT 1,
    body                    text,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_nudge_dispatches_status
        CHECK (status IN ('pending', 'delivered', 'suppressed')),
    CONSTRAINT chk_nudge_dispatches_severity
        CHECK (severity IN ('low', 'normal', 'high'))
);

CREATE INDEX IF NOT EXISTS idx_nudge_dispatches_member_created
    ON scout.nudge_dispatches (family_member_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_nudge_dispatches_pending
    ON scout.nudge_dispatches (deliver_after_utc)
    WHERE delivered_at_utc IS NULL;

DROP TRIGGER IF EXISTS trg_nudge_dispatches_updated_at ON scout.nudge_dispatches;
CREATE TRIGGER trg_nudge_dispatches_updated_at
    BEFORE UPDATE ON scout.nudge_dispatches
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- scout.nudge_dispatch_items (child: one source proposal, provenance + dedupe)
-- ============================================================================

CREATE TABLE IF NOT EXISTS scout.nudge_dispatch_items (
    id                       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    dispatch_id              uuid        NOT NULL REFERENCES scout.nudge_dispatches (id) ON DELETE CASCADE,
    family_member_id         uuid        NOT NULL REFERENCES public.family_members (id) ON DELETE CASCADE,
    trigger_kind             text        NOT NULL,
    trigger_entity_kind      text        NOT NULL,
    trigger_entity_id        uuid,
    occurrence_at_utc        timestamptz NOT NULL,
    occurrence_local_date    date        NOT NULL,
    source_dedupe_key        text        NOT NULL,
    source_metadata          jsonb       NOT NULL DEFAULT '{}'::jsonb,
    created_at               timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_nudge_dispatch_items_trigger_kind
        CHECK (trigger_kind IN ('overdue_task', 'upcoming_event', 'missed_routine', 'custom_rule', 'ai_suggested')),
    CONSTRAINT uq_nudge_dispatch_items_source_dedupe_key
        UNIQUE (source_dedupe_key)
);

CREATE INDEX IF NOT EXISTS idx_nudge_dispatch_items_member
    ON scout.nudge_dispatch_items (family_member_id, occurrence_at_utc DESC);

CREATE INDEX IF NOT EXISTS idx_nudge_dispatch_items_dispatch
    ON scout.nudge_dispatch_items (dispatch_id);

-- ============================================================================
-- Permission registration: nudges.view_own
-- ============================================================================

INSERT INTO scout.permissions (permission_key, description) VALUES
    ('nudges.view_own',
     'View own recent proactive nudge dispatches')
ON CONFLICT (permission_key) DO NOTHING;

-- nudges.view_own: all user tiers
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM public.role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('YOUNG_CHILD', 'CHILD', 'TEEN', 'PARENT', 'PRIMARY_PARENT')
  AND p.permission_key = 'nudges.view_own'
ON CONFLICT DO NOTHING;

COMMIT;
