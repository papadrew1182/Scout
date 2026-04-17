-- Migration 029: Seed chores configuration
--
-- Seeds per-kid chores.routines config rows in member_config and a
-- family-level chores.rules row in family_config for the Roberts family.
--
-- Per-kid chores.routines shape:
--   { "routines": [ { "id": "...", "name": "...", "pts": N }, ... ] }
--
-- Family chores.rules shape:
--   { "streak_bonus_days": N, "streak_bonus_pts": N,
--     "max_daily_pts": N, "requires_check_off": bool }
--
-- Uses a CTE to resolve member IDs by first_name within the Roberts family
-- (same pattern as migration 028). Safe to re-run: uses ON CONFLICT DO UPDATE.

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
        RAISE NOTICE 'migration 029 skipped: no Roberts family found';
        RETURN;
    END IF;

    -- Per-kid chores.routines rows
    INSERT INTO member_config (family_member_id, key, value)
    SELECT
        fm.id,
        'chores.routines',
        CASE fm.first_name
            WHEN 'Sadie' THEN '{
                "routines": [
                    { "id": "clean_room",       "name": "Clean room",            "pts": 10 },
                    { "id": "practice_piano",   "name": "Practice piano 15 min", "pts": 10 },
                    { "id": "unload_dishwasher","name": "Unload dishwasher",     "pts": 10 },
                    { "id": "homework_checkin", "name": "Homework check-in",     "pts": 10 }
                ]
            }'::jsonb
            WHEN 'Townes' THEN '{
                "routines": [
                    { "id": "make_bed",          "name": "Make bed",           "pts": 10 },
                    { "id": "unload_dishwasher", "name": "Unload dishwasher",  "pts": 10 },
                    { "id": "feed_biscuit",      "name": "Feed Biscuit (dog)", "pts": 10 },
                    { "id": "clean_backpack",    "name": "Clean up backpack",  "pts": 10 }
                ]
            }'::jsonb
            WHEN 'Tyler' THEN '{
                "routines": [
                    { "id": "trash_out",     "name": "Trash out",        "pts": 15 },
                    { "id": "recycling_out", "name": "Recycling out",    "pts": 15 },
                    { "id": "mow_lawn",      "name": "Mow lawn (Sat)",   "pts": 20 },
                    { "id": "car_wash",      "name": "Car wash weekly",  "pts": 20 }
                ]
            }'::jsonb
            WHEN 'River' THEN '{
                "routines": [
                    { "id": "feed_fish",  "name": "Feed fish",  "pts": 10 },
                    { "id": "tidy_toys",  "name": "Tidy toys",  "pts": 10 },
                    { "id": "set_table",  "name": "Set table",  "pts": 10 }
                ]
            }'::jsonb
        END
    FROM public.family_members fm
    WHERE fm.family_id = v_family_id
      AND fm.first_name IN ('Sadie', 'Townes', 'Tyler', 'River')
      AND fm.is_active
    ON CONFLICT (family_member_id, key) DO UPDATE
        SET value      = EXCLUDED.value,
            updated_at = NOW();

    -- Family-level chores.rules row
    INSERT INTO family_config (family_id, key, value)
    VALUES (
        v_family_id,
        'chores.rules',
        '{
            "streak_bonus_days": 7,
            "streak_bonus_pts": 20,
            "max_daily_pts": 100,
            "requires_check_off": true
        }'::jsonb
    )
    ON CONFLICT (family_id, key) DO UPDATE
        SET value      = EXCLUDED.value,
            updated_at = NOW();

    RAISE NOTICE 'migration 029: chores config seeded for family %', v_family_id;
END $$;

COMMIT;
