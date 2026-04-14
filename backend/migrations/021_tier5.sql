-- Migration 021: Tier 5 schema — hardening, memory, remote MCP
--
-- Adds:
--   F16. planner_bundle_applies — idempotency ledger for the atomic
--        bundle apply. A single row per apply attempt, keyed on a
--        client-supplied bundle_apply_id so double-taps on the
--        confirm button don't double-write.
--   F18. scout_anomaly_suppressions — suppression ledger so the
--        anomaly scan doesn't emit the same signature every day.
--   F19. scout_mcp_tokens — bearer tokens for the remote MCP
--        transport, family-scoped with optional member scope.
--   F20. family_memories — persistent preferences + planning
--        defaults with proposed/active/archived status.

BEGIN;

-- ============================================================================
-- F16: planner bundle idempotency
-- ============================================================================
CREATE TABLE IF NOT EXISTS planner_bundle_applies (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    bundle_apply_id     text        NOT NULL,
    family_id           uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    actor_member_id     uuid        NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    conversation_id     uuid        REFERENCES ai_conversations (id) ON DELETE SET NULL,
    status              text        NOT NULL DEFAULT 'applied',
    tasks_created       integer     NOT NULL DEFAULT 0,
    events_created      integer     NOT NULL DEFAULT 0,
    grocery_items_created integer   NOT NULL DEFAULT 0,
    errors              jsonb,
    summary             text,
    created_at          timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT chk_planner_bundle_apply_status
        CHECK (status IN ('applied', 'failed'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_planner_bundle_applies_family_bundle
    ON planner_bundle_applies (family_id, bundle_apply_id);

-- ============================================================================
-- F18: anomaly suppression ledger
-- ============================================================================
CREATE TABLE IF NOT EXISTS scout_anomaly_suppressions (
    id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id      uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    anomaly_type   text        NOT NULL,
    signature      text        NOT NULL,
    first_seen_at  timestamptz NOT NULL DEFAULT clock_timestamp(),
    last_seen_at   timestamptz NOT NULL DEFAULT clock_timestamp(),
    suppress_until timestamptz NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_anomaly_suppressions_family_signature
    ON scout_anomaly_suppressions (family_id, anomaly_type, signature);
CREATE INDEX IF NOT EXISTS idx_anomaly_suppressions_family_until
    ON scout_anomaly_suppressions (family_id, suppress_until);

-- ============================================================================
-- F19: remote MCP bearer tokens
-- ============================================================================
CREATE TABLE IF NOT EXISTS scout_mcp_tokens (
    id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id      uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    -- Optional member scope. NULL means "adult access to the whole
    -- family" (the default). When set, the token is a child-scoped
    -- subset — used if we ever expose a kid-reading transport.
    member_id      uuid        REFERENCES family_members (id) ON DELETE CASCADE,
    token_hash     text        NOT NULL,
    label          text,
    -- Scope is one of 'parent' or 'child'. Parent tokens see the
    -- full parent surface of the MCP tools; child tokens are
    -- restricted to the child-safe subset (today: schedule, tasks,
    -- meals, grocery — no inbox / briefs / cost / homework rollup).
    scope          text        NOT NULL DEFAULT 'parent',
    is_active      boolean     NOT NULL DEFAULT TRUE,
    last_used_at   timestamptz,
    created_by_member_id uuid  REFERENCES family_members (id) ON DELETE SET NULL,
    created_at     timestamptz NOT NULL DEFAULT clock_timestamp(),
    revoked_at     timestamptz,

    CONSTRAINT chk_scout_mcp_token_scope CHECK (scope IN ('parent', 'child'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_scout_mcp_tokens_hash
    ON scout_mcp_tokens (token_hash);
CREATE INDEX IF NOT EXISTS idx_scout_mcp_tokens_family
    ON scout_mcp_tokens (family_id);

-- ============================================================================
-- F20: family memory layer
-- ============================================================================
CREATE TABLE IF NOT EXISTS family_memories (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id           uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    member_id           uuid        REFERENCES family_members (id) ON DELETE CASCADE,
    -- Coarse category so we can inject a subset into any given prompt.
    memory_type         text        NOT NULL,
    -- Surface scope: 'parent' (adult-only), 'family' (both surfaces),
    -- 'child' (scoped to one member). Used by the prompt injector.
    scope               text        NOT NULL DEFAULT 'family',
    content             text        NOT NULL,
    -- Freeform tags for dedupe / search, not used as primary keys.
    tags                jsonb       NOT NULL DEFAULT '[]'::jsonb,
    -- 'ai_proposed' when the orchestrator wrote a candidate row.
    -- 'auto_structured' when a structured flow (approved planner,
    -- approved meal plan) wrote a safe auto-memory. 'parent_edit'
    -- when a parent wrote/edited it directly.
    source_kind         text        NOT NULL DEFAULT 'parent_edit',
    source_conversation_id uuid     REFERENCES ai_conversations (id) ON DELETE SET NULL,
    created_by_kind     text        NOT NULL DEFAULT 'parent',
    status              text        NOT NULL DEFAULT 'active',
    confidence          real        NOT NULL DEFAULT 1.0,
    last_confirmed_at   timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_at          timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at          timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT chk_family_memory_status
        CHECK (status IN ('proposed', 'active', 'archived')),
    CONSTRAINT chk_family_memory_scope
        CHECK (scope IN ('parent', 'family', 'child')),
    CONSTRAINT chk_family_memory_source_kind
        CHECK (source_kind IN ('parent_edit', 'ai_proposed', 'auto_structured'))
);

CREATE INDEX IF NOT EXISTS idx_family_memories_family_status
    ON family_memories (family_id, status);
CREATE INDEX IF NOT EXISTS idx_family_memories_family_type_status
    ON family_memories (family_id, memory_type, status);
CREATE INDEX IF NOT EXISTS idx_family_memories_member_status
    ON family_memories (member_id, status);

-- Reuse the existing set_updated_at() trigger helper.
CREATE TRIGGER trg_family_memories_updated_at
    BEFORE UPDATE ON family_memories
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
