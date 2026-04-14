-- Migration 019: Tier 3 schema
--
-- Adds:
--   1. family_members.personality_notes — parent-editable coaching layer
--      injected into the CHILD system prompt only. Separate from
--      learning_notes (which is academic/support context) so parents
--      can tune tone/encouragement without mixing the two signals.
--   2. parent_action_items.action_type widened to allow
--      'moderation_digest' (daily rollup created by the new scheduler
--      tick). Does not remove any prior allowed values.
--   3. Two lookup indexes used by the new Tier 3 code paths:
--        - ai_messages(created_at) — speeds up the cost rollup query
--          that scans by day across a family's conversations.
--        - ai_conversations(family_id, updated_at DESC) — backs the
--          conversation-resume query that picks the most recent safe
--          thread for a given member.

BEGIN;

-- ============================================================================
-- F9: family_members.personality_notes
-- ============================================================================
ALTER TABLE family_members
    ADD COLUMN IF NOT EXISTS personality_notes text;

-- ============================================================================
-- F12: ai_conversations.status — allow 'ended' so the "Start new chat"
-- affordance can mark a conversation closed without archiving it.
-- Archived and ended are semantically different: archived = user hid
-- it from the history list; ended = user explicitly closed this
-- thread and doesn't want auto-resume to pick it up.
-- ============================================================================
ALTER TABLE ai_conversations
    DROP CONSTRAINT IF EXISTS chk_ai_conversations_status;
ALTER TABLE ai_conversations
    ADD CONSTRAINT chk_ai_conversations_status
    CHECK (status IN ('active', 'archived', 'ended'));

-- ============================================================================
-- F10: parent_action_items — allow moderation_digest
-- ============================================================================
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
        'moderation_digest'
    ));

-- ============================================================================
-- F11 / F12: lookup indexes
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_ai_messages_created_at
    ON ai_messages (created_at);
CREATE INDEX IF NOT EXISTS idx_ai_conversations_family_updated
    ON ai_conversations (family_id, updated_at DESC);

COMMIT;
