-- Migration 015: AI conversation kind + moderation alert action type
--
-- conversation_kind classifies each ai_conversations row by what
-- actually happened during its turns:
--   'chat'       — pure Q&A / homework / general knowledge, no tools
--   'tool'       — at least one tool was invoked
--   'mixed'      — conversation has both tool and chat turns across
--                  its history (a child asked homework AND also used
--                  add_grocery_item in the same conversation thread)
--   'moderation' — the first turn was blocked by the pre-LLM
--                  moderation gate; used so parents can filter audit
--
-- Default is 'chat' because that's the most common case and matches
-- existing rows (which were all pre-chat-mode family-ops turns —
-- technically they'd be 'tool', but we'll backfill them below).
--
-- Also widens parent_action_items.action_type to allow 'moderation_alert'
-- so the orchestrator can drop a row into the Parent Action Inbox when
-- a child message is blocked.

BEGIN;

ALTER TABLE ai_conversations
    ADD COLUMN IF NOT EXISTS conversation_kind TEXT NOT NULL DEFAULT 'chat';

ALTER TABLE ai_conversations
    DROP CONSTRAINT IF EXISTS chk_ai_conversations_kind;
ALTER TABLE ai_conversations
    ADD CONSTRAINT chk_ai_conversations_kind
    CHECK (conversation_kind IN ('chat', 'tool', 'mixed', 'moderation'));

-- Backfill: existing conversations that already have at least one
-- ai_tool_audit row are 'tool'; the rest stay 'chat'.
UPDATE ai_conversations c
   SET conversation_kind = 'tool'
 WHERE conversation_kind = 'chat'
   AND EXISTS (
       SELECT 1 FROM ai_tool_audit a
        WHERE a.conversation_id = c.id
          AND a.tool_name != 'moderation'
   );

CREATE INDEX IF NOT EXISTS idx_ai_conversations_kind
    ON ai_conversations (family_id, conversation_kind, updated_at DESC);

-- Widen parent_action_items.action_type to include moderation_alert.
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
        'moderation_alert'
    ));

COMMIT;
