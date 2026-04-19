-- Migration 039: Affirmations feature tables
--
-- Creates three tables in the scout schema:
--   scout.affirmations         — the curated affirmation library
--   scout.affirmation_feedback — per-member reactions (heart, thumbs_down, skip, reshow)
--   scout.affirmation_delivery_log — audit log of what was surfaced to whom and when

BEGIN;

-- ============================================================================
-- scout.affirmations
-- ============================================================================

CREATE TABLE IF NOT EXISTS scout.affirmations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    text            TEXT NOT NULL,
    category        TEXT,
    tags            JSONB NOT NULL DEFAULT '[]'::jsonb,
    tone            TEXT,
    philosophy      TEXT,
    audience_type   TEXT NOT NULL DEFAULT 'general',
    length_class    TEXT NOT NULL DEFAULT 'short',
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    source_type     TEXT NOT NULL DEFAULT 'curated',
    created_by      UUID REFERENCES public.family_members(id) ON DELETE SET NULL,
    updated_by      UUID REFERENCES public.family_members(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- scout.affirmation_feedback
-- ============================================================================

CREATE TABLE IF NOT EXISTS scout.affirmation_feedback (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_member_id  UUID NOT NULL REFERENCES public.family_members(id) ON DELETE CASCADE,
    affirmation_id    UUID NOT NULL REFERENCES scout.affirmations(id) ON DELETE CASCADE,
    reaction_type     TEXT NOT NULL,
    context           TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_affirmation_feedback_reaction_type
        CHECK (reaction_type IN ('heart', 'thumbs_down', 'skip', 'reshow'))
);

CREATE INDEX IF NOT EXISTS idx_affirmation_feedback_member
    ON scout.affirmation_feedback(family_member_id);

CREATE INDEX IF NOT EXISTS idx_affirmation_feedback_affirmation
    ON scout.affirmation_feedback(affirmation_id);

-- ============================================================================
-- scout.affirmation_delivery_log
-- ============================================================================

CREATE TABLE IF NOT EXISTS scout.affirmation_delivery_log (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_member_id  UUID NOT NULL REFERENCES public.family_members(id) ON DELETE CASCADE,
    affirmation_id    UUID NOT NULL REFERENCES scout.affirmations(id) ON DELETE CASCADE,
    surfaced_at       TIMESTAMPTZ NOT NULL,
    surfaced_in       TEXT NOT NULL,
    dismissed_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_affirmation_delivery_member
    ON scout.affirmation_delivery_log(family_member_id);

CREATE INDEX IF NOT EXISTS idx_affirmation_delivery_surfaced
    ON scout.affirmation_delivery_log(family_member_id, surfaced_at);

COMMIT;
