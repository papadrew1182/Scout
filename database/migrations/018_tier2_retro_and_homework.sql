-- Migration 018: Tier 2 schema
--
-- Adds:
--   1. ai_homework_sessions — one row per detected kid homework turn
--      (or grouped session). Parent dashboard rollups read from here.
--   2. parent_action_items.action_type widened to allow 'weekly_retro'.
--
-- ai_daily_insights.insight_type is NOT widened — the weekly retro is
-- a parent_action_item (durable, readable in the inbox), not a
-- dashboard banner.

BEGIN;

-- ============================================================================
-- ai_homework_sessions — per-child homework activity log
-- ============================================================================
CREATE TABLE IF NOT EXISTS ai_homework_sessions (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id           uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    member_id           uuid        NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    conversation_id     uuid        REFERENCES ai_conversations (id) ON DELETE SET NULL,
    subject             text        NOT NULL DEFAULT 'other',
    summary             text,
    grade_level_at_time text,
    started_at          timestamptz NOT NULL DEFAULT clock_timestamp(),
    ended_at            timestamptz,
    turn_count          integer     NOT NULL DEFAULT 1,
    session_length_sec  integer,
    created_at          timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT chk_homework_subject
        CHECK (subject IN (
            'math',
            'reading',
            'writing',
            'science',
            'history',
            'language',
            'other'
        ))
);

CREATE INDEX IF NOT EXISTS idx_homework_sessions_family_started
    ON ai_homework_sessions (family_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_homework_sessions_member_started
    ON ai_homework_sessions (member_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_homework_sessions_conversation
    ON ai_homework_sessions (conversation_id);

-- ============================================================================
-- parent_action_items — allow weekly_retro
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
        'weekly_retro'
    ));

COMMIT;
