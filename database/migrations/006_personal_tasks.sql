-- Migration 006: Personal Task Layer
-- Source of truth: BACKEND_ROADMAP.md + Scout conventions
-- Generated: 2026-04-09
--
-- 1 table: personal_tasks
--
-- Intentionally separate from task_instances (child routines/chores).
-- Personal tasks are adult/general-purpose: one-off, optionally due,
-- optionally linked to a calendar event.
--
-- Depends on: 001_foundation_connectors.sql, 003_calendar.sql

BEGIN;

-- ============================================================================
-- personal_tasks
-- ============================================================================
-- One row per personal task. Family-scoped via denormalized family_id for
-- query performance; write-path must validate family_id matches
-- assigned_to/created_by family memberships.

CREATE TABLE IF NOT EXISTS personal_tasks (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id    uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    assigned_to  uuid        NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    created_by   uuid        REFERENCES family_members (id) ON DELETE SET NULL,
    title        text        NOT NULL,
    description  text,
    notes        text,
    status       text        NOT NULL DEFAULT 'pending',
    priority     text        NOT NULL DEFAULT 'medium',
    due_at       timestamptz,
    completed_at timestamptz,
    event_id     uuid        REFERENCES events (id) ON DELETE SET NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_personal_tasks_status
        CHECK (status IN ('pending', 'in_progress', 'done', 'cancelled')),

    CONSTRAINT chk_personal_tasks_priority
        CHECK (priority IN ('low', 'medium', 'high', 'urgent')),

    -- completed_at is set iff status is done
    CONSTRAINT chk_personal_tasks_completed_consistency
        CHECK (
            (status = 'done' AND completed_at IS NOT NULL)
            OR (status != 'done' AND completed_at IS NULL)
        )
);

-- Primary read path: "all personal tasks for a member, filtered by status"
-- Top 5 Tasks query: assigned_to + status, sorted by priority/due_at
CREATE INDEX idx_personal_tasks_assigned_status
    ON personal_tasks (assigned_to, status);

-- Tenant-scoped queries
CREATE INDEX idx_personal_tasks_family_id ON personal_tasks (family_id);

-- Due-date scans (e.g., "due today", "due this week")
CREATE INDEX idx_personal_tasks_due_at
    ON personal_tasks (due_at)
    WHERE due_at IS NOT NULL;

-- FK indexes
CREATE INDEX idx_personal_tasks_created_by ON personal_tasks (created_by);
CREATE INDEX idx_personal_tasks_event_id
    ON personal_tasks (event_id)
    WHERE event_id IS NOT NULL;

CREATE TRIGGER trg_personal_tasks_updated_at
    BEFORE UPDATE ON personal_tasks
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
