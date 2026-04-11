-- Migration 007: Second Brain
-- Source of truth: BACKEND_ROADMAP.md + Scout conventions
-- Generated: 2026-04-09
--
-- 1 table: notes
--
-- Intentionally minimal. No tags, no inter-note links, no attachments,
-- no full-text index. Search is ILIKE-based for now.
--
-- Depends on: 001_foundation_connectors.sql

BEGIN;

-- ============================================================================
-- notes
-- ============================================================================
-- One row per second-brain entry. Family-scoped via denormalized family_id;
-- write-path must validate family_id matches family_member.family_id.

CREATE TABLE IF NOT EXISTS notes (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id    uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    family_member_id uuid    NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    title        text        NOT NULL,
    body         text        NOT NULL DEFAULT '',
    category     text,
    is_archived  boolean     NOT NULL DEFAULT false,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),

    -- title cannot be empty/whitespace-only
    CONSTRAINT chk_notes_title_not_blank
        CHECK (length(btrim(title)) > 0)
);

-- Primary read paths
CREATE INDEX idx_notes_family_member_updated
    ON notes (family_member_id, updated_at DESC);

CREATE INDEX idx_notes_family_updated
    ON notes (family_id, updated_at DESC);

-- Optional category filter (small cardinality, no big win, but cheap)
CREATE INDEX idx_notes_category
    ON notes (category)
    WHERE category IS NOT NULL;

CREATE TRIGGER trg_notes_updated_at
    BEFORE UPDATE ON notes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
