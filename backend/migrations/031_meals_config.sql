-- Migration 031: Seed meals configuration
--
-- Seeds three family-level config keys for meals in family_config:
--
--   meals.plan_rules  — week cadence, dinners, batch cook day, generation style
--   meals.rating_scale — max rating, repeat options, notes requirement
--   meals.dietary_notes — editable list of dietary category labels
--
-- Safe to re-run: uses ON CONFLICT DO UPDATE.

BEGIN;

DO $$
DECLARE
    v_family_id uuid;
BEGIN
    SELECT id INTO v_family_id
    FROM public.families
    WHERE name ILIKE 'Roberts%'
    ORDER BY created_at ASC
    LIMIT 1;

    IF v_family_id IS NULL THEN
        RAISE NOTICE 'migration 031 skipped: no Roberts family found';
        RETURN;
    END IF;

    -- meals.plan_rules
    INSERT INTO family_config (family_id, key, value)
    VALUES (
        v_family_id,
        'meals.plan_rules',
        '{
            "week_starts_on": "monday",
            "dinners_per_week": 7,
            "batch_cook_day": "sunday",
            "generation_style": "balanced"
        }'::jsonb
    )
    ON CONFLICT (family_id, key) DO UPDATE
        SET value      = EXCLUDED.value,
            updated_at = NOW();

    -- meals.rating_scale
    INSERT INTO family_config (family_id, key, value)
    VALUES (
        v_family_id,
        'meals.rating_scale',
        '{
            "max_rating": 5,
            "repeat_options": ["repeat", "tweak", "retire"],
            "require_notes_for_retire": false
        }'::jsonb
    )
    ON CONFLICT (family_id, key) DO UPDATE
        SET value      = EXCLUDED.value,
            updated_at = NOW();

    -- meals.dietary_notes
    INSERT INTO family_config (family_id, key, value)
    VALUES (
        v_family_id,
        'meals.dietary_notes',
        '{
            "categories": [
                "No restrictions",
                "Vegetarian-lean",
                "No onions",
                "Dairy-free",
                "Gluten-free",
                "Nut-free"
            ]
        }'::jsonb
    )
    ON CONFLICT (family_id, key) DO UPDATE
        SET value      = EXCLUDED.value,
            updated_at = NOW();

    RAISE NOTICE 'migration 031: meals config seeded for family %', v_family_id;
END $$;

COMMIT;
