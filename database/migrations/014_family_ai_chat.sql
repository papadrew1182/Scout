-- Migration 014: Family AI chat settings + per-member learning context
--
-- Adds optional columns that broaden Scout AI beyond family ops:
--   families.allow_general_chat   — gate general Q&A / homework help
--   families.allow_homework_help  — separate switch for kids specifically
--   families.home_location        — free-text location used by get_weather
--                                   (e.g. "76126" or "Fort Worth, TX"),
--                                   resolved by Open-Meteo geocoding at
--                                   call time; no lat/lon stored.
--   family_members.grade_level    — short string ("K", "3rd", "8th", "college"),
--                                   used by the child prompt to tune tone
--   family_members.learning_notes — free-text parent-authored notes visible
--                                   only in the system prompt when the child
--                                   is speaking to Scout
--
-- All defaults are non-restrictive so the migration is a no-op for existing
-- installs: general chat + homework help default to ON, home_location is
-- NULL, grade_level + learning_notes are NULL.

BEGIN;

ALTER TABLE families
    ADD COLUMN IF NOT EXISTS allow_general_chat  BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS allow_homework_help BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS home_location       TEXT;

ALTER TABLE family_members
    ADD COLUMN IF NOT EXISTS grade_level    TEXT,
    ADD COLUMN IF NOT EXISTS learning_notes TEXT;

-- Widen ai_tool_audit.status CHECK to include 'moderation_blocked',
-- which the orchestrator now emits when the pre-LLM moderation gate
-- rejects a user message.
ALTER TABLE ai_tool_audit
    DROP CONSTRAINT IF EXISTS chk_ai_tool_audit_status;
ALTER TABLE ai_tool_audit
    ADD CONSTRAINT chk_ai_tool_audit_status
    CHECK (status IN ('success', 'error', 'denied', 'confirmation_required', 'moderation_blocked'));

COMMIT;
