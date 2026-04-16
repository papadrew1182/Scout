-- Migration 030: Seed grocery configuration
--
-- Seeds family-level config rows in family_config for the Roberts family:
--   grocery.stores     — list of stores (id, name, kind)
--   grocery.categories — list of category strings
--   grocery.approval_rules — approval workflow settings
--
-- Uses the same pattern as migration 028 (allowance_config).
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
        RAISE NOTICE 'migration 030 skipped: no Roberts family found';
        RETURN;
    END IF;

    -- grocery.stores — matches the hardcoded GROCERY stores in seedData.ts
    INSERT INTO family_config (family_id, key, value)
    VALUES (
        v_family_id,
        'grocery.stores',
        '{
            "stores": [
                { "id": "costco",    "name": "Costco",    "kind": "bulk"  },
                { "id": "tom_thumb", "name": "Tom Thumb", "kind": "local" }
            ]
        }'::jsonb
    )
    ON CONFLICT (family_id, key) DO UPDATE
        SET value      = EXCLUDED.value,
            updated_at = NOW();

    -- grocery.categories
    INSERT INTO family_config (family_id, key, value)
    VALUES (
        v_family_id,
        'grocery.categories',
        '{"categories": ["Produce", "Protein", "Pantry", "Dairy", "Requested"]}'::jsonb
    )
    ON CONFLICT (family_id, key) DO UPDATE
        SET value      = EXCLUDED.value,
            updated_at = NOW();

    -- grocery.approval_rules
    INSERT INTO family_config (family_id, key, value)
    VALUES (
        v_family_id,
        'grocery.approval_rules',
        '{
            "require_approval_for_children": true,
            "require_approval_for_teens":    false,
            "auto_approve_under_cents":      500
        }'::jsonb
    )
    ON CONFLICT (family_id, key) DO UPDATE
        SET value      = EXCLUDED.value,
            updated_at = NOW();

    RAISE NOTICE 'migration 030: grocery config seeded for family %', v_family_id;
END $$;

COMMIT;
