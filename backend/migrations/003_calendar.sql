-- Migration 003: Calendar / Scheduling
-- Source of truth: BACKEND_ROADMAP.md + Scout conventions
-- Generated: 2026-04-09
--
-- 2 tables: events, event_attendees
-- External IDs (Google, iCal) live in connector_mappings only.
--
-- Depends on: 001_foundation_connectors.sql, 002_life_management.sql

BEGIN;

-- ============================================================================
-- events
-- ============================================================================
-- One row per calendar entry. Recurrence is stored as an RFC 5545 RRULE string
-- in `recurrence_rule`. Application code expands recurrences at query time.
--
-- Edited-instance behavior:
--   - The "series root" has recurrence_rule set, recurrence_parent_id NULL.
--   - An edited single occurrence is a NEW row with:
--       recurrence_parent_id   = series root id
--       recurrence_instance_date = the original occurrence date being overridden
--       recurrence_rule        = NULL (edited instances do not themselves recur)
--   - To cancel a single occurrence, create an edited instance with
--     is_cancelled = true.
--
-- family_id is denormalized for tenant-scoped queries; write-path must
-- validate family_id matches family_members.family_id and event parent.

CREATE TABLE IF NOT EXISTS events (
    id                       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id                uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    created_by               uuid        REFERENCES family_members (id) ON DELETE SET NULL,
    title                    text        NOT NULL,
    description              text,
    location                 text,
    starts_at                timestamptz NOT NULL,
    ends_at                  timestamptz NOT NULL,
    all_day                  boolean     NOT NULL DEFAULT false,
    recurrence_rule          text,
    recurrence_parent_id     uuid        REFERENCES events (id) ON DELETE CASCADE,
    recurrence_instance_date date,
    source                   text        NOT NULL DEFAULT 'scout',
    is_hearth_visible        boolean     NOT NULL DEFAULT true,
    task_instance_id         uuid        REFERENCES task_instances (id) ON DELETE SET NULL,
    is_cancelled             boolean     NOT NULL DEFAULT false,
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_events_source
        CHECK (source IN ('scout', 'google_cal', 'ical')),

    -- ends_at must not be earlier than starts_at
    CONSTRAINT chk_events_time_order
        CHECK (ends_at >= starts_at),

    -- A series root cannot itself be an edited instance.
    -- If recurrence_rule is set, recurrence_parent_id and instance_date must be NULL.
    CONSTRAINT chk_events_series_root
        CHECK (
            recurrence_rule IS NULL
            OR (recurrence_parent_id IS NULL AND recurrence_instance_date IS NULL)
        ),

    -- Edited instances must include both the parent reference and the instance date.
    CONSTRAINT chk_events_edited_instance
        CHECK (
            (recurrence_parent_id IS NULL AND recurrence_instance_date IS NULL)
            OR (recurrence_parent_id IS NOT NULL AND recurrence_instance_date IS NOT NULL)
        )
);

-- Only one override per (parent series, original occurrence date)
CREATE UNIQUE INDEX uq_events_recurrence_override
    ON events (recurrence_parent_id, recurrence_instance_date)
    WHERE recurrence_parent_id IS NOT NULL;

-- Tenant + range query: "all events for a family in this window"
CREATE INDEX idx_events_family_starts_at ON events (family_id, starts_at);

-- FK indexes
CREATE INDEX idx_events_created_by ON events (created_by);
CREATE INDEX idx_events_recurrence_parent_id ON events (recurrence_parent_id);
CREATE INDEX idx_events_task_instance_id
    ON events (task_instance_id)
    WHERE task_instance_id IS NOT NULL;

CREATE TRIGGER trg_events_updated_at
    BEFORE UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- event_attendees
-- ============================================================================
-- One row per (event, family_member) pair. Each attendee tracks their own
-- response status independently.

CREATE TABLE IF NOT EXISTS event_attendees (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id         uuid        NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    family_member_id uuid        NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    response_status  text        NOT NULL DEFAULT 'pending',
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_event_attendees_response_status
        CHECK (response_status IN ('pending', 'accepted', 'declined', 'tentative')),

    -- one row per (event, member); leading column covers event_id lookups
    CONSTRAINT uq_event_attendees_event_member
        UNIQUE (event_id, family_member_id)
);

-- "all events for a member" requires a separate index since the unique
-- constraint leads with event_id
CREATE INDEX idx_event_attendees_family_member_id
    ON event_attendees (family_member_id);

CREATE TRIGGER trg_event_attendees_updated_at
    BEFORE UPDATE ON event_attendees
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
