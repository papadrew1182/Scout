-- Migration 046: Sprint 04 Phase 1 - AI conversation resume
--
-- Adds conversation list + resume metadata to ai_conversations:
--   title           for the recent-conversations drawer
--   last_active_at  resume ordering; bumps on user/assistant turns only
--   is_pinned       manual pinning
--
-- Archive state REUSES the existing `status` column from migration 010
-- (values 'active' | 'archived') rather than introducing a parallel
-- is_archived boolean. Two sources of truth is worse than one.
--
-- `last_active_at` and the existing `updated_at` differ intentionally:
-- `updated_at` (trigger trg_ai_conversations_updated_at) bumps on any row
-- mutation including rename/pin/archive; `last_active_at` bumps only on
-- user or assistant message turns. Resume ordering uses last_active_at.
--
-- Permissions added:
--   ai.manage_own_conversations - list/rename/archive/pin own conversations
--   ai.clear_own_history        - bulk archive-older-than (archive only)
-- Granted to YOUNG_CHILD, CHILD, TEEN, PARENT, PRIMARY_PARENT.
-- DISPLAY_ONLY excluded by convention.

BEGIN;

-- 1. Columns. Add last_active_at nullable first for safe idempotent backfill.
ALTER TABLE ai_conversations
    ADD COLUMN IF NOT EXISTS title text,
    ADD COLUMN IF NOT EXISTS last_active_at timestamptz,
    ADD COLUMN IF NOT EXISTS is_pinned boolean NOT NULL DEFAULT false;

-- 2. Backfill last_active_at from existing timestamps. IS NULL guard makes
-- this safe to run multiple times.
UPDATE ai_conversations
SET last_active_at = COALESCE(updated_at, created_at)
WHERE last_active_at IS NULL;

-- 3. Now that every row has a value, lock in default + NOT NULL.
ALTER TABLE ai_conversations
    ALTER COLUMN last_active_at SET DEFAULT now();
ALTER TABLE ai_conversations
    ALTER COLUMN last_active_at SET NOT NULL;

-- 4. Backfill title from the first user message. First 60 trimmed chars
-- after whitespace normalization. Idempotent via IS NULL guard.
UPDATE ai_conversations c
SET title = (
    SELECT TRIM(BOTH FROM SUBSTRING(
        REGEXP_REPLACE(m.content, '\s+', ' ', 'g'),
        1, 60
    ))
    FROM ai_messages m
    WHERE m.conversation_id = c.id
      AND m.role = 'user'
      AND m.content IS NOT NULL
      AND LENGTH(TRIM(m.content)) > 0
    ORDER BY m.created_at ASC
    LIMIT 1
)
WHERE c.title IS NULL;

-- 5. Indexes
-- Resume query: newest non-archived conversations per member.
CREATE INDEX IF NOT EXISTS idx_ai_conversations_resume
    ON ai_conversations (family_member_id, status, last_active_at DESC);

-- Pinned-first ordering for the recent-conversations drawer.
CREATE INDEX IF NOT EXISTS idx_ai_conversations_pinned
    ON ai_conversations (family_member_id, last_active_at DESC)
    WHERE is_pinned = true;

-- 6. Permission keys
INSERT INTO scout.permissions (permission_key, description) VALUES
    ('ai.manage_own_conversations',
     'List, rename, archive, and pin own AI conversations'),
    ('ai.clear_own_history',
     'Bulk archive own older AI conversations (archive-only, no delete)')
ON CONFLICT (permission_key) DO NOTHING;

-- 7. Grant to all user tiers (excludes DISPLAY_ONLY).
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('YOUNG_CHILD', 'CHILD', 'TEEN', 'PARENT', 'PRIMARY_PARENT')
  AND p.permission_key IN ('ai.manage_own_conversations',
                            'ai.clear_own_history')
ON CONFLICT DO NOTHING;

COMMIT;
