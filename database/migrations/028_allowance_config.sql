-- Migration 028: Seed allowance configuration
--
-- Seeds per-kid allowance.target config rows in member_config and a
-- family-level allowance.rules row in family_config for the Roberts family.
--
-- Per-kid allowance.target shape:
--   { "weekly_target_cents": N, "baseline_cents": N, "payout_schedule": "weekly" }
--
-- Family allowance.rules shape:
--   { "requires_approval_for_bonus": bool, "max_weekly_bonus_cents": N,
--     "streak_bonus_days": N, "streak_bonus_cents": N }
--
-- Uses a CTE to resolve member IDs by first_name within the Roberts family
-- (same pattern as migration 024). Safe to re-run: uses ON CONFLICT DO UPDATE.

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
        RAISE NOTICE 'migration 028 skipped: no Roberts family found';
        RETURN;
    END IF;

    -- Per-kid allowance.target rows
    INSERT INTO member_config (family_member_id, key, value)
    SELECT
        fm.id,
        'allowance.target',
        CASE fm.first_name
            WHEN 'Sadie'  THEN '{"weekly_target_cents": 1000, "baseline_cents": 500, "payout_schedule": "weekly"}'::jsonb
            WHEN 'Townes' THEN '{"weekly_target_cents": 800,  "baseline_cents": 400, "payout_schedule": "weekly"}'::jsonb
            WHEN 'Tyler'  THEN '{"weekly_target_cents": 1200, "baseline_cents": 600, "payout_schedule": "weekly"}'::jsonb
            WHEN 'River'  THEN '{"weekly_target_cents": 600,  "baseline_cents": 300, "payout_schedule": "weekly"}'::jsonb
        END
    FROM public.family_members fm
    WHERE fm.family_id = v_family_id
      AND fm.first_name IN ('Sadie', 'Townes', 'Tyler', 'River')
      AND fm.is_active
    ON CONFLICT (family_member_id, key) DO UPDATE
        SET value      = EXCLUDED.value,
            updated_at = NOW();

    -- Family-level allowance.rules row
    INSERT INTO family_config (family_id, key, value)
    VALUES (
        v_family_id,
        'allowance.rules',
        '{
            "requires_approval_for_bonus": true,
            "max_weekly_bonus_cents": 500,
            "streak_bonus_days": 7,
            "streak_bonus_cents": 200
        }'::jsonb
    )
    ON CONFLICT (family_id, key) DO UPDATE
        SET value      = EXCLUDED.value,
            updated_at = NOW();

    RAISE NOTICE 'migration 028: allowance config seeded for family %', v_family_id;
END $$;

COMMIT;
