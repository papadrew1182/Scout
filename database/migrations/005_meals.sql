-- Migration 005: Meals
-- Source of truth: BACKEND_ROADMAP.md + Scout conventions
-- Generated: 2026-04-09
--
-- 3 tables: meal_plans, meals, dietary_preferences
--
-- Depends on: 001_foundation_connectors.sql

BEGIN;

-- ============================================================================
-- meal_plans (optional weekly container)
-- ============================================================================
-- One row per family per week_start. week_start is always a Monday.
-- Meals can exist with or without a parent plan.

CREATE TABLE IF NOT EXISTS meal_plans (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id   uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    created_by  uuid        REFERENCES family_members (id) ON DELETE SET NULL,
    week_start  date        NOT NULL,
    notes       text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),

    -- week_start must be a Monday: isodow 1 = Monday
    CONSTRAINT chk_meal_plans_week_start_monday
        CHECK (EXTRACT(isodow FROM week_start) = 1),

    -- one plan per family per week
    CONSTRAINT uq_meal_plans_family_week
        UNIQUE (family_id, week_start)
);

CREATE INDEX idx_meal_plans_created_by ON meal_plans (created_by);

CREATE TRIGGER trg_meal_plans_updated_at
    BEFORE UPDATE ON meal_plans
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- meals (individual meal entries by date + type)
-- ============================================================================
-- One row per (family, meal_date, meal_type). family_id is denormalized for
-- tenant-scoped query performance; write-path must validate family_id matches
-- meal_plan.family_id (when set) and the creator's family.

CREATE TABLE IF NOT EXISTS meals (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id    uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    meal_plan_id uuid        REFERENCES meal_plans (id) ON DELETE SET NULL,
    created_by   uuid        REFERENCES family_members (id) ON DELETE SET NULL,
    meal_date    date        NOT NULL,
    meal_type    text        NOT NULL,
    title        text        NOT NULL,
    description  text,
    notes        text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_meals_meal_type
        CHECK (meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')),

    -- one meal per type per day per family
    CONSTRAINT uq_meals_family_date_type
        UNIQUE (family_id, meal_date, meal_type)
);

-- primary read path: "what are we eating today?"
CREATE INDEX idx_meals_family_date ON meals (family_id, meal_date);

CREATE INDEX idx_meals_meal_plan_id
    ON meals (meal_plan_id)
    WHERE meal_plan_id IS NOT NULL;

CREATE INDEX idx_meals_created_by ON meals (created_by);

CREATE TRIGGER trg_meals_updated_at
    BEFORE UPDATE ON meals
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- dietary_preferences (per-member, minimal hook)
-- ============================================================================
-- Thin table for future dietary support. Not referenced by meals yet.
-- One row per (member, label) pair.

CREATE TABLE IF NOT EXISTS dietary_preferences (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_member_id uuid        NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    label            text        NOT NULL,
    kind             text        NOT NULL,
    notes            text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_dietary_preferences_kind
        CHECK (kind IN ('preference', 'restriction', 'allergy')),

    -- one preference label per member
    CONSTRAINT uq_dietary_preferences_member_label
        UNIQUE (family_member_id, label)
);

CREATE TRIGGER trg_dietary_preferences_updated_at
    BEFORE UPDATE ON dietary_preferences
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
