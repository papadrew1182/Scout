-- Migration 020: Tier 4 schema
--
-- Adds:
--   1. parent_action_items.action_type widened to allow 'anomaly_alert'
--      (daily anomaly scan surfaces findings here).
--   2. Lookup index for anomaly/window queries — we frequently filter
--      parent_action_items by (family_id, action_type, created_at) to
--      power the inbox-buildup detector and dedupe logic.
--
-- No new tables. Feature 14 (MCP server) is a separate process with
-- no schema impact. Feature 15 (weekly planner) reuses the existing
-- ai_conversations + ai_messages persistence; the planner intent is
-- carried on the request, not on a new table.

BEGIN;

ALTER TABLE parent_action_items
    DROP CONSTRAINT IF EXISTS chk_parent_action_items_action_type;
ALTER TABLE parent_action_items
    ADD CONSTRAINT chk_parent_action_items_action_type
    CHECK (action_type IN (
        'grocery_review',
        'purchase_request',
        'chore_override',
        'general',
        'meal_plan_review',
        'moderation_alert',
        'daily_brief',
        'weekly_retro',
        'moderation_digest',
        'anomaly_alert'
    ));

CREATE INDEX IF NOT EXISTS idx_parent_action_items_family_type_created
    ON parent_action_items (family_id, action_type, created_at DESC);

COMMIT;
