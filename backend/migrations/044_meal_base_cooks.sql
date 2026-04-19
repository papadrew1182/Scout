-- Phase 5: Meal base-cook model
-- Extends meal_staples with base-cook fields and adds transformations table.

-- 1. Add base-cook columns to the meals table (used as staples)
-- The existing public.meals table serves as the staple registry.
ALTER TABLE public.meals
  ADD COLUMN IF NOT EXISTS is_base_cook boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS base_cook_yield_servings integer,
  ADD COLUMN IF NOT EXISTS base_cook_keeps_days integer,
  ADD COLUMN IF NOT EXISTS storage_notes text;

-- 2. Meal transformations (many-to-many through table)
CREATE TABLE IF NOT EXISTS scout.meal_transformations (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id               UUID NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    base_staple_id          UUID NOT NULL REFERENCES public.meals(id) ON DELETE CASCADE,
    transformed_staple_id   UUID NOT NULL REFERENCES public.meals(id) ON DELETE CASCADE,
    transformation_name     TEXT NOT NULL,
    notes                   TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_meal_transformations_base ON scout.meal_transformations(base_staple_id);
CREATE INDEX IF NOT EXISTS idx_meal_transformations_family ON scout.meal_transformations(family_id);

-- 3. Weekly meal plan entries extensions
-- Check if weekly_meal_plan_entries table exists before altering
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'weekly_meal_plan_entries') THEN
        ALTER TABLE public.weekly_meal_plan_entries
            ADD COLUMN IF NOT EXISTS is_base_cook_execution boolean DEFAULT false,
            ADD COLUMN IF NOT EXISTS base_cook_source_entry_id uuid;
    END IF;
END $$;
