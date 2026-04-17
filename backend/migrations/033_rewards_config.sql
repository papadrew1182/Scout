-- Migration 033: Seed rewards configuration
--
-- Seeds family-level rewards.tiers and rewards.redemption_rules rows in
-- family_config for the Roberts family.
--
-- Also adds rewards.manage_config permission to admin and parent_peer
-- permission tiers (if the permission_definitions and role_permissions
-- tables exist, as seeded by migration 024).
--
-- Safe to re-run: uses ON CONFLICT DO UPDATE / DO NOTHING throughout.

BEGIN;

DO $$
DECLARE
    v_family_id uuid;
    v_perm_id   uuid;
BEGIN
    -- ----------------------------------------------------------------
    -- Locate the Roberts family
    -- ----------------------------------------------------------------
    SELECT id INTO v_family_id
    FROM public.families
    WHERE name ILIKE 'Roberts%'
    ORDER BY created_at ASC
    LIMIT 1;

    IF v_family_id IS NULL THEN
        RAISE NOTICE 'migration 033 skipped: no Roberts family found';
        RETURN;
    END IF;

    -- ----------------------------------------------------------------
    -- Seed rewards.tiers
    -- ----------------------------------------------------------------
    INSERT INTO family_config (family_id, key, value)
    VALUES (
        v_family_id,
        'rewards.tiers',
        '{
            "tiers": [
                { "id": "small",  "label": "Small reward",  "cost_pts": 200,  "example": "30 min extra screen time" },
                { "id": "medium", "label": "Medium reward", "cost_pts": 500,  "example": "Movie night pick" },
                { "id": "large",  "label": "Large reward",  "cost_pts": 1000, "example": "Day trip pick" }
            ]
        }'::jsonb
    )
    ON CONFLICT (family_id, key) DO UPDATE
        SET value      = EXCLUDED.value,
            updated_at = NOW();

    RAISE NOTICE 'migration 033: rewards.tiers seeded for family %', v_family_id;

    -- ----------------------------------------------------------------
    -- Seed rewards.redemption_rules
    -- ----------------------------------------------------------------
    INSERT INTO family_config (family_id, key, value)
    VALUES (
        v_family_id,
        'rewards.redemption_rules',
        '{
            "require_approval": true,
            "max_redemptions_per_week": 2,
            "allow_negative_balance": false
        }'::jsonb
    )
    ON CONFLICT (family_id, key) DO UPDATE
        SET value      = EXCLUDED.value,
            updated_at = NOW();

    RAISE NOTICE 'migration 033: rewards.redemption_rules seeded for family %', v_family_id;

    -- ----------------------------------------------------------------
    -- Add rewards.manage_config permission definition
    -- (guard with IF EXISTS so it's safe if permission_definitions
    --  table is absent in older environments)
    -- ----------------------------------------------------------------
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name   = 'permission_definitions'
    ) THEN
        INSERT INTO permission_definitions (key, description, category)
        VALUES (
            'rewards.manage_config',
            'View and edit rewards tiers and redemption rules in admin',
            'rewards'
        )
        ON CONFLICT (key) DO NOTHING;

        SELECT id INTO v_perm_id
        FROM permission_definitions
        WHERE key = 'rewards.manage_config';

        IF v_perm_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name   = 'role_permissions'
        ) THEN
            -- Grant to admin tier
            INSERT INTO role_permissions (role, permission_id)
            VALUES ('admin', v_perm_id)
            ON CONFLICT DO NOTHING;

            -- Grant to parent_peer tier
            INSERT INTO role_permissions (role, permission_id)
            VALUES ('parent_peer', v_perm_id)
            ON CONFLICT DO NOTHING;

            RAISE NOTICE 'migration 033: rewards.manage_config granted to admin and parent_peer';
        END IF;
    END IF;
END $$;

COMMIT;
