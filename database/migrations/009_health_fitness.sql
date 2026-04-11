-- Migration 009: Health / Fitness
-- Source of truth: BACKEND_ROADMAP.md + Scout conventions
-- Generated: 2026-04-09
--
-- 2 tables: health_summaries, activity_records
--
-- Intentionally minimal. No workout programs, no nutrition tracking,
-- no goals/streaks, no rollup aggregations. External IDs live in
-- connector_mappings per Scout convention.
--
-- Depends on: 001_foundation_connectors.sql

BEGIN;

-- ============================================================================
-- health_summaries (one per member per day)
-- ============================================================================
-- All metric columns are nullable so partial data from a single source
-- (e.g., Apple Health steps only, no weight) is supported.
--
-- family_id is denormalized for tenant-scoped query performance;
-- write-path must validate family_id matches family_member.family_id.

CREATE TABLE IF NOT EXISTS health_summaries (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id           uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    family_member_id    uuid        NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    summary_date        date        NOT NULL,
    steps               integer,
    active_minutes      integer,
    resting_heart_rate  integer,
    sleep_minutes       integer,
    weight_grams        integer,
    source              text        NOT NULL DEFAULT 'scout',
    notes               text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_health_summaries_source
        CHECK (source IN ('scout', 'apple_health', 'nike_run_club')),

    -- numeric metrics must be non-negative when present
    CONSTRAINT chk_health_summaries_steps_nonneg
        CHECK (steps IS NULL OR steps >= 0),
    CONSTRAINT chk_health_summaries_active_minutes_nonneg
        CHECK (active_minutes IS NULL OR active_minutes >= 0),
    CONSTRAINT chk_health_summaries_resting_hr_nonneg
        CHECK (resting_heart_rate IS NULL OR resting_heart_rate >= 0),
    CONSTRAINT chk_health_summaries_sleep_minutes_nonneg
        CHECK (sleep_minutes IS NULL OR sleep_minutes >= 0),
    CONSTRAINT chk_health_summaries_weight_grams_nonneg
        CHECK (weight_grams IS NULL OR weight_grams >= 0),

    -- one summary per member per date
    CONSTRAINT uq_health_summaries_member_date
        UNIQUE (family_member_id, summary_date)
);

-- Primary read paths
CREATE INDEX idx_health_summaries_family_date
    ON health_summaries (family_id, summary_date);

CREATE TRIGGER trg_health_summaries_updated_at
    BEFORE UPDATE ON health_summaries
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- activity_records (one per discrete activity event)
-- ============================================================================
-- A run, a yoga session, a bike ride. Optional ended_at allows ongoing or
-- duration-only entries.

CREATE TABLE IF NOT EXISTS activity_records (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id        uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    family_member_id uuid        NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    activity_type    text        NOT NULL,
    title            text,
    started_at       timestamptz NOT NULL,
    ended_at         timestamptz,
    duration_seconds integer,
    distance_meters  integer,
    calories         integer,
    source           text        NOT NULL DEFAULT 'scout',
    notes            text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_activity_records_activity_type
        CHECK (activity_type IN ('run', 'walk', 'bike', 'swim', 'strength', 'yoga', 'other')),

    CONSTRAINT chk_activity_records_source
        CHECK (source IN ('scout', 'apple_health', 'nike_run_club')),

    -- ended_at must be >= started_at when set
    CONSTRAINT chk_activity_records_time_order
        CHECK (ended_at IS NULL OR ended_at >= started_at),

    -- numerics non-negative when present
    CONSTRAINT chk_activity_records_duration_nonneg
        CHECK (duration_seconds IS NULL OR duration_seconds >= 0),
    CONSTRAINT chk_activity_records_distance_nonneg
        CHECK (distance_meters IS NULL OR distance_meters >= 0),
    CONSTRAINT chk_activity_records_calories_nonneg
        CHECK (calories IS NULL OR calories >= 0)
);

-- Primary read paths
CREATE INDEX idx_activity_records_member_started
    ON activity_records (family_member_id, started_at DESC);

CREATE INDEX idx_activity_records_family_started
    ON activity_records (family_id, started_at DESC);

CREATE TRIGGER trg_activity_records_updated_at
    BEFORE UPDATE ON activity_records
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
