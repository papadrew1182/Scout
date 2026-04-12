-- Migration 013: Weekly Meal Plans + Meal Reviews
-- Turns AI-generated meal plans into first-class persisted workflow.
--
-- Adds:
--   - weekly_meal_plans: draft/approved plans with structured JSONB content
--   - meal_reviews: fast family feedback on specific meals
--   - grocery_items.weekly_plan_id / linked_meal_ref (sync from approved plans)
--   - parent_action_items.action_type allows 'meal_plan_review'
--
-- Depends on: 005_meals.sql, 011_grocery_purchase_requests.sql, 012_parent_action_items.sql

BEGIN;

-- ============================================================================
-- weekly_meal_plans
-- ============================================================================
-- One row per generated or manually created weekly plan. Structured content
-- lives in JSONB: week_plan (dinners/breakfast/lunch/snacks), prep_plan
-- (batch cook tasks + timeline), grocery_plan (store grouping snapshot).
--
-- A family can have multiple drafts but only one approved plan per week_start.
-- Draft status is not constrained by uniqueness so parents can regenerate.

CREATE TABLE IF NOT EXISTS weekly_meal_plans (
    id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id             uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    created_by_member_id  uuid        NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    week_start_date       date        NOT NULL,
    source                text        NOT NULL DEFAULT 'ai',
    status                text        NOT NULL DEFAULT 'draft',
    title                 text,
    constraints_snapshot  jsonb       NOT NULL DEFAULT '{}'::jsonb,
    week_plan             jsonb       NOT NULL DEFAULT '{}'::jsonb,
    prep_plan             jsonb       NOT NULL DEFAULT '{}'::jsonb,
    grocery_plan          jsonb       NOT NULL DEFAULT '{}'::jsonb,
    plan_summary          text,
    approved_by_member_id uuid        REFERENCES family_members (id) ON DELETE SET NULL,
    approved_at           timestamptz,
    archived_at           timestamptz,
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_weekly_meal_plans_source
        CHECK (source IN ('ai', 'manual')),
    CONSTRAINT chk_weekly_meal_plans_status
        CHECK (status IN ('draft', 'approved', 'archived')),
    CONSTRAINT chk_weekly_meal_plans_week_start_monday
        CHECK (EXTRACT(isodow FROM week_start_date) = 1),
    CONSTRAINT chk_weekly_meal_plans_approved_fields
        CHECK (
            (status <> 'approved') OR
            (approved_by_member_id IS NOT NULL AND approved_at IS NOT NULL)
        )
);

CREATE INDEX idx_weekly_meal_plans_family_week
    ON weekly_meal_plans (family_id, week_start_date DESC);
CREATE INDEX idx_weekly_meal_plans_family_status
    ON weekly_meal_plans (family_id, status);

-- Only one approved plan per family per week
CREATE UNIQUE INDEX uq_weekly_meal_plans_family_week_approved
    ON weekly_meal_plans (family_id, week_start_date)
    WHERE status = 'approved';

CREATE TRIGGER trg_weekly_meal_plans_updated_at
    BEFORE UPDATE ON weekly_meal_plans
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ============================================================================
-- meal_reviews
-- ============================================================================
-- Fast structured family feedback on a specific meal.
-- linked_meal_ref is a free-form identifier from the plan's week_plan JSON
-- (e.g. "2026-04-13:dinner") so reviews can survive plan edits without FK
-- gymnastics. weekly_plan_id is nullable to allow standalone reviews.

CREATE TABLE IF NOT EXISTS meal_reviews (
    id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id             uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    weekly_plan_id        uuid        REFERENCES weekly_meal_plans (id) ON DELETE SET NULL,
    reviewed_by_member_id uuid        NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    linked_meal_ref       text,
    meal_title            text        NOT NULL,
    rating_overall        integer     NOT NULL,
    kid_acceptance        integer,
    effort                integer,
    cleanup               integer,
    leftovers             text,
    repeat_decision       text        NOT NULL,
    notes                 text,
    created_at            timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_meal_reviews_rating_overall
        CHECK (rating_overall BETWEEN 1 AND 5),
    CONSTRAINT chk_meal_reviews_kid_acceptance
        CHECK (kid_acceptance IS NULL OR kid_acceptance BETWEEN 1 AND 5),
    CONSTRAINT chk_meal_reviews_effort
        CHECK (effort IS NULL OR effort BETWEEN 1 AND 5),
    CONSTRAINT chk_meal_reviews_cleanup
        CHECK (cleanup IS NULL OR cleanup BETWEEN 1 AND 5),
    CONSTRAINT chk_meal_reviews_leftovers
        CHECK (leftovers IS NULL OR leftovers IN ('none', 'some', 'plenty')),
    CONSTRAINT chk_meal_reviews_repeat_decision
        CHECK (repeat_decision IN ('repeat', 'tweak', 'retire')),
    CONSTRAINT chk_meal_reviews_meal_title_not_blank
        CHECK (length(btrim(meal_title)) > 0)
);

CREATE INDEX idx_meal_reviews_family_created
    ON meal_reviews (family_id, created_at DESC);
CREATE INDEX idx_meal_reviews_weekly_plan
    ON meal_reviews (weekly_plan_id)
    WHERE weekly_plan_id IS NOT NULL;
CREATE INDEX idx_meal_reviews_repeat_decision
    ON meal_reviews (family_id, repeat_decision);


-- ============================================================================
-- grocery_items extensions — link synced items back to the plan/meal
-- ============================================================================

ALTER TABLE grocery_items
    ADD COLUMN IF NOT EXISTS weekly_plan_id  uuid REFERENCES weekly_meal_plans (id) ON DELETE SET NULL;
ALTER TABLE grocery_items
    ADD COLUMN IF NOT EXISTS linked_meal_ref text;

CREATE INDEX IF NOT EXISTS idx_grocery_items_weekly_plan
    ON grocery_items (weekly_plan_id)
    WHERE weekly_plan_id IS NOT NULL;


-- ============================================================================
-- parent_action_items — allow meal_plan_review action type
-- ============================================================================

ALTER TABLE parent_action_items
    DROP CONSTRAINT IF EXISTS chk_parent_action_items_action_type;
ALTER TABLE parent_action_items
    ADD CONSTRAINT chk_parent_action_items_action_type
    CHECK (action_type IN ('grocery_review', 'purchase_request', 'chore_override', 'general', 'meal_plan_review'));

COMMIT;
