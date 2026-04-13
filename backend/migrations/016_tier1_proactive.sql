-- Migration 016: Tier 1 proactive features
--
-- Adds schema for:
--   1. Scheduled-job dedupe + timezone-aware cron runs
--   2. AI-generated household insights cached per family per day
--   3. Per-member read-aloud preference for the child surface
--   4. daily_brief + off_track_insight action types
--
-- All additive. No backfill required.

BEGIN;

-- ============================================================================
-- scout_scheduled_runs — dedupe + audit log for scheduled jobs
-- ============================================================================
-- Every scheduled job (morning brief, weekly retro, anomaly scan, etc.)
-- writes exactly one row per (job_name, family_id, run_date) before running,
-- using an INSERT ... ON CONFLICT DO NOTHING. The row doubles as a
-- mutex: re-runs of the same day are no-ops because the INSERT fails the
-- uniqueness check. Multi-instance safe via the unique index.

CREATE TABLE IF NOT EXISTS scout_scheduled_runs (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    job_name    text        NOT NULL,
    family_id   uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    member_id   uuid        REFERENCES family_members (id) ON DELETE CASCADE,
    run_date    date        NOT NULL,
    status      text        NOT NULL DEFAULT 'success',
    duration_ms integer,
    result      jsonb,
    error       text,
    created_at  timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_scout_scheduled_runs_status
        CHECK (status IN ('success', 'error', 'skipped'))
);

-- One row per (job, family, member-or-null, day) — this is the mutex.
CREATE UNIQUE INDEX IF NOT EXISTS uq_scout_scheduled_runs_dedupe
    ON scout_scheduled_runs (job_name, family_id, COALESCE(member_id, '00000000-0000-0000-0000-000000000000'::uuid), run_date);

CREATE INDEX IF NOT EXISTS idx_scout_scheduled_runs_family_date
    ON scout_scheduled_runs (family_id, run_date DESC);

-- ============================================================================
-- ai_daily_insights — cached AI reasoning per family per day
-- ============================================================================
-- Stores AI-generated explanations (e.g. "what's off track today")
-- keyed by (family_id, insight_type, as_of_date). The parent dashboard
-- reads the most recent row for the insight it wants. Regeneration
-- happens either on day rollover or on explicit invalidate.

CREATE TABLE IF NOT EXISTS ai_daily_insights (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id    uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    insight_type text        NOT NULL,
    as_of_date   date        NOT NULL,
    status       text        NOT NULL,
    content      text        NOT NULL,
    model        text,
    input_tokens integer,
    output_tokens integer,
    created_at   timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_ai_daily_insights_type
        CHECK (insight_type IN ('off_track'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_daily_insights_dedupe
    ON ai_daily_insights (family_id, insight_type, as_of_date);

-- ============================================================================
-- family_members.read_aloud_enabled — per-member read-aloud preference
-- ============================================================================
-- Default false. Only meaningful for child members; adults ignore it.
-- Frontend-only behavior: the ScoutPanel on the child surface calls
-- speechSynthesis.speak() on each incoming assistant message when this
-- flag is true.

ALTER TABLE family_members
    ADD COLUMN IF NOT EXISTS read_aloud_enabled BOOLEAN NOT NULL DEFAULT FALSE;

-- ============================================================================
-- parent_action_items — new action types for proactive items
-- ============================================================================
-- daily_brief: the morning brief Action Inbox item. Detail field holds
-- the full brief text; frontend renders it in a detail view on tap.

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
        'daily_brief'
    ));

COMMIT;
