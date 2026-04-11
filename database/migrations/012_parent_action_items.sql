-- Migration 012: Parent Action Items
-- Lightweight notification/action queue for parent-facing review items.
-- Depends on: 001_foundation_connectors.sql

BEGIN;

CREATE TABLE IF NOT EXISTS parent_action_items (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id        uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    created_by_member_id uuid    NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    action_type      text        NOT NULL,
    title            text        NOT NULL,
    detail           text,
    entity_type      text,
    entity_id        uuid,
    status           text        NOT NULL DEFAULT 'pending',
    resolved_by      uuid        REFERENCES family_members (id) ON DELETE SET NULL,
    resolved_at      timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_parent_action_items_action_type
        CHECK (action_type IN ('grocery_review', 'purchase_request', 'chore_override', 'general')),
    CONSTRAINT chk_parent_action_items_status
        CHECK (status IN ('pending', 'resolved', 'dismissed'))
);

CREATE INDEX idx_parent_action_items_family_status
    ON parent_action_items (family_id, status);

CREATE TRIGGER trg_parent_action_items_updated_at
    BEFORE UPDATE ON parent_action_items
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
