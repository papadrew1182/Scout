-- Migration 010: AI Orchestration
-- Conversation state + tool audit logging
-- Depends on: 001_foundation_connectors.sql

BEGIN;

-- ============================================================================
-- ai_conversations (thread state per family member)
-- ============================================================================

CREATE TABLE IF NOT EXISTS ai_conversations (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id        uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    family_member_id uuid        NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    surface          text        NOT NULL DEFAULT 'personal',
    status           text        NOT NULL DEFAULT 'active',
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_ai_conversations_surface
        CHECK (surface IN ('personal', 'parent', 'child')),
    CONSTRAINT chk_ai_conversations_status
        CHECK (status IN ('active', 'archived'))
);

CREATE INDEX idx_ai_conversations_member
    ON ai_conversations (family_member_id, updated_at DESC);
CREATE INDEX idx_ai_conversations_family
    ON ai_conversations (family_id);

CREATE TRIGGER trg_ai_conversations_updated_at
    BEFORE UPDATE ON ai_conversations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- ai_messages (individual messages within a conversation)
-- ============================================================================

CREATE TABLE IF NOT EXISTS ai_messages (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  uuid        NOT NULL REFERENCES ai_conversations (id) ON DELETE CASCADE,
    role             text        NOT NULL,
    content          text,
    tool_calls       jsonb,
    tool_results     jsonb,
    model            text,
    token_usage      jsonb,
    created_at       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_ai_messages_role
        CHECK (role IN ('user', 'assistant', 'system', 'tool'))
);

CREATE INDEX idx_ai_messages_conversation
    ON ai_messages (conversation_id, created_at);

-- ============================================================================
-- ai_tool_audit (audit log for every tool execution)
-- ============================================================================

CREATE TABLE IF NOT EXISTS ai_tool_audit (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id        uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    actor_member_id  uuid        NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    conversation_id  uuid        REFERENCES ai_conversations (id) ON DELETE SET NULL,
    tool_name        text        NOT NULL,
    arguments        jsonb       NOT NULL DEFAULT '{}',
    result_summary   text,
    target_entity    text,
    target_id        uuid,
    status           text        NOT NULL DEFAULT 'success',
    error_message    text,
    duration_ms      integer,
    created_at       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_ai_tool_audit_status
        CHECK (status IN ('success', 'error', 'denied', 'confirmation_required'))
);

CREATE INDEX idx_ai_tool_audit_family
    ON ai_tool_audit (family_id, created_at DESC);
CREATE INDEX idx_ai_tool_audit_actor
    ON ai_tool_audit (actor_member_id, created_at DESC);
CREATE INDEX idx_ai_tool_audit_tool
    ON ai_tool_audit (tool_name, created_at DESC);

COMMIT;
