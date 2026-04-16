-- Migration 032: Seed integrations configuration
--
-- Seeds a family-level integrations.connections row in family_config for
-- the Roberts family.
--
-- integrations.connections shape:
--   { "connections": [ { "id": string, "name": string, "status": string, "category": string }, ... ] }
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
        RAISE NOTICE 'migration 032 skipped: no Roberts family found';
        RETURN;
    END IF;

    INSERT INTO family_config (family_id, key, value)
    VALUES (
        v_family_id,
        'integrations.connections',
        '{
            "connections": [
                { "id": "google_calendar",  "name": "Google Calendar",        "status": "connected",     "category": "calendar" },
                { "id": "greenlight",       "name": "Greenlight (allowance)", "status": "connected",     "category": "finance"  },
                { "id": "hearth_display",   "name": "Hearth Display",         "status": "connected",     "category": "device"   },
                { "id": "ynab",             "name": "YNAB",                   "status": "needs_reauth",  "category": "finance"  },
                { "id": "apple_health",     "name": "Apple Health",           "status": "not_connected", "category": "health"   },
                { "id": "nike_run_club",    "name": "Nike Run Club",          "status": "not_connected", "category": "health"   }
            ]
        }'::jsonb
    )
    ON CONFLICT (family_id, key) DO UPDATE
        SET value      = EXCLUDED.value,
            updated_at = NOW();

    RAISE NOTICE 'migration 032: integrations config seeded for family %', v_family_id;
END $$;

COMMIT;
