-- Migration 002: Life Management
-- Source of truth: family_chore_system.md + locked product decisions
-- Generated: 2026-04-08
--
-- 7 tables: routines, routine_steps, chore_templates, task_instances,
-- task_instance_step_completions, daily_wins, allowance_ledger
--
-- Depends on: 001_foundation_connectors.sql

BEGIN;

-- ============================================================================
-- routines (recurring block templates)
-- ============================================================================
-- One routine per kid per block (e.g., "Sadie Morning Routine").
-- Generates one task_instance per applicable day.

CREATE TABLE IF NOT EXISTS routines (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id        uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    family_member_id uuid        NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    name             text        NOT NULL,
    block            text        NOT NULL,
    recurrence       text        NOT NULL DEFAULT 'daily',
    due_time_weekday time        NOT NULL,
    due_time_weekend time,
    is_active        boolean     NOT NULL DEFAULT true,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_routines_block CHECK (block IN ('morning', 'after_school', 'evening')),
    CONSTRAINT chk_routines_recurrence CHECK (recurrence IN ('daily', 'weekdays', 'weekends'))
);

CREATE INDEX idx_routines_family_id ON routines (family_id);
CREATE INDEX idx_routines_family_member_id ON routines (family_member_id);

-- one active routine per kid per block; deactivated routines do not block new ones
CREATE UNIQUE INDEX uq_routines_member_block
    ON routines (family_member_id, block)
    WHERE is_active = true;

CREATE TRIGGER trg_routines_updated_at
    BEFORE UPDATE ON routines
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- routine_steps (ordered checklist items within a routine)
-- ============================================================================

CREATE TABLE IF NOT EXISTS routine_steps (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    routine_id  uuid        NOT NULL REFERENCES routines (id) ON DELETE CASCADE,
    name        text        NOT NULL,
    sort_order  integer     NOT NULL,
    is_active   boolean     NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),

    -- unique constraint's leading column covers routine_id lookups
    CONSTRAINT uq_routine_steps_order UNIQUE (routine_id, sort_order)
);

CREATE TRIGGER trg_routine_steps_updated_at
    BEFORE UPDATE ON routine_steps
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- chore_templates (recurring chore definitions)
-- ============================================================================
-- Assignment rules (rotation logic, day parity, rotation intervals)
-- are stored in assignment_rule jsonb and interpreted by the application.

CREATE TABLE IF NOT EXISTS chore_templates (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    name            text        NOT NULL,
    description     text,
    recurrence      text        NOT NULL DEFAULT 'daily',
    due_time        time        NOT NULL,
    assignment_type text        NOT NULL,
    assignment_rule jsonb       NOT NULL DEFAULT '{}',
    is_active       boolean     NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_chore_templates_recurrence
        CHECK (recurrence IN ('daily', 'weekdays', 'weekends', 'weekly')),

    CONSTRAINT chk_chore_templates_assignment_type
        CHECK (assignment_type IN ('fixed', 'rotating_daily', 'rotating_weekly'))
);

CREATE INDEX idx_chore_templates_family_id ON chore_templates (family_id);

CREATE TRIGGER trg_chore_templates_updated_at
    BEFORE UPDATE ON chore_templates
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- task_instances (concrete execution records)
-- ============================================================================
-- One row per kid per routine-block or chore per applicable day.
-- Exactly one of routine_id or chore_template_id must be set.
-- family_id is denormalized for tenant-scoped query performance;
-- write-path must validate family_id matches family_members.family_id.
--
-- Uniqueness note: uq_task_instances_routine and uq_task_instances_chore
-- both contain a nullable column. PostgreSQL treats NULLs as distinct in
-- UNIQUE constraints, so each constraint only enforces uniqueness for rows
-- where its source FK is non-null. This is the intended behavior.

CREATE TABLE IF NOT EXISTS task_instances (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id           uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    family_member_id    uuid        NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    routine_id          uuid        REFERENCES routines (id) ON DELETE RESTRICT,
    chore_template_id   uuid        REFERENCES chore_templates (id) ON DELETE RESTRICT,
    instance_date       date        NOT NULL,
    due_at              timestamptz NOT NULL,
    is_completed        boolean     NOT NULL DEFAULT false,
    completed_at        timestamptz,
    override_completed  boolean,
    override_by         uuid        REFERENCES family_members (id) ON DELETE RESTRICT,
    override_note       text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),

    -- exactly one source must be set
    CONSTRAINT chk_task_instances_source
        CHECK (
            (routine_id IS NOT NULL AND chore_template_id IS NULL) OR
            (routine_id IS NULL AND chore_template_id IS NOT NULL)
        ),

    -- override fields: all-NULL or override_completed + override_by both set
    -- override_note is optional within a valid override
    CONSTRAINT chk_task_instances_override
        CHECK (
            (override_completed IS NULL AND override_by IS NULL AND override_note IS NULL) OR
            (override_completed IS NOT NULL AND override_by IS NOT NULL)
        ),

    -- one routine instance per kid per day
    CONSTRAINT uq_task_instances_routine
        UNIQUE (family_member_id, routine_id, instance_date),

    -- one chore instance per kid per day
    CONSTRAINT uq_task_instances_chore
        UNIQUE (family_member_id, chore_template_id, instance_date)
);

-- query: all instances for a given routine or chore template
CREATE INDEX idx_task_instances_routine_id ON task_instances (routine_id);
CREATE INDEX idx_task_instances_chore_template_id ON task_instances (chore_template_id);

-- primary query path: all tasks for a family on a given day
CREATE INDEX idx_task_instances_family_date
    ON task_instances (family_id, instance_date);

-- daily win calculation: all tasks for a kid on a given day
CREATE INDEX idx_task_instances_member_date
    ON task_instances (family_member_id, instance_date);

-- FK index for override_by; partial because most rows are NULL
CREATE INDEX idx_task_instances_override_by
    ON task_instances (override_by)
    WHERE override_by IS NOT NULL;

CREATE TRIGGER trg_task_instances_updated_at
    BEFORE UPDATE ON task_instances
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- task_instance_step_completions (routine step tracking)
-- ============================================================================
-- Only for routine-sourced task_instances.
-- One row per routine_step per task_instance.
-- DB cannot enforce routine-only constraint without a trigger;
-- application must not create rows for chore-sourced task_instances.

CREATE TABLE IF NOT EXISTS task_instance_step_completions (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    task_instance_id uuid        NOT NULL REFERENCES task_instances (id) ON DELETE CASCADE,
    routine_step_id  uuid        NOT NULL REFERENCES routine_steps (id) ON DELETE RESTRICT,
    is_completed     boolean     NOT NULL DEFAULT false,
    completed_at     timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),

    -- unique constraint's leading column covers task_instance_id lookups
    CONSTRAINT uq_step_completions_instance_step
        UNIQUE (task_instance_id, routine_step_id)
);

CREATE INDEX idx_step_completions_routine_step_id
    ON task_instance_step_completions (routine_step_id);

-- ============================================================================
-- daily_wins (materialized daily scoring)
-- ============================================================================
-- One row per kid per calendar date. Mon-Fri only for scoring.
-- Application computes is_win from task_instances; DB enforces uniqueness.
-- family_id is denormalized for tenant-scoped query performance;
-- write-path must validate family_id matches family_members.family_id.

CREATE TABLE IF NOT EXISTS daily_wins (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id        uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    family_member_id uuid        NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    win_date         date        NOT NULL,
    is_win           boolean     NOT NULL,
    task_count       integer     NOT NULL,
    completed_count  integer     NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),

    -- one win record per kid per date
    CONSTRAINT uq_daily_wins_member_date UNIQUE (family_member_id, win_date),

    CONSTRAINT chk_daily_wins_counts
        CHECK (completed_count >= 0 AND completed_count <= task_count AND task_count >= 0),

    -- Mon-Fri only: isodow 1=Monday through 5=Friday
    CONSTRAINT chk_daily_wins_weekday
        CHECK (EXTRACT(isodow FROM win_date) BETWEEN 1 AND 5)
);

CREATE INDEX idx_daily_wins_family_id ON daily_wins (family_id);

CREATE TRIGGER trg_daily_wins_updated_at
    BEFORE UPDATE ON daily_wins
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- allowance_ledger (financial records)
-- ============================================================================
-- One weekly payout row per kid per week. School rewards and adjustments
-- as separate rows. week_start is always a Monday (Mon-Fri scoring window).
-- family_id is denormalized for tenant-scoped query performance;
-- write-path must validate family_id matches family_members.family_id.

CREATE TABLE IF NOT EXISTS allowance_ledger (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id        uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    family_member_id uuid        NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    entry_type       text        NOT NULL,
    amount_cents     integer     NOT NULL,
    week_start       date,
    note             text,
    created_at       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_allowance_ledger_entry_type
        CHECK (entry_type IN ('weekly_payout', 'school_reward', 'extra', 'adjustment')),

    -- weekly payouts must have a week_start
    CONSTRAINT chk_allowance_ledger_weekly_payout
        CHECK (entry_type != 'weekly_payout' OR week_start IS NOT NULL),

    -- week_start must be a Monday when set
    CONSTRAINT chk_allowance_ledger_week_start_monday
        CHECK (week_start IS NULL OR EXTRACT(isodow FROM week_start) = 1)
);

CREATE INDEX idx_allowance_ledger_family_id ON allowance_ledger (family_id);

-- prevent duplicate weekly payouts per kid per week
CREATE UNIQUE INDEX uq_allowance_ledger_weekly_payout
    ON allowance_ledger (family_member_id, week_start)
    WHERE entry_type = 'weekly_payout';

-- balance queries: all entries for a kid, filterable by type
CREATE INDEX idx_allowance_ledger_member_type
    ON allowance_ledger (family_member_id, entry_type);

COMMIT;
