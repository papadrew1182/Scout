-- Migration 036: Migrate chores.routines from member_config
--                into scout.routine_templates (normalized rows).
--
-- Each member_config row with key = 'chores.routines' holds a JSONB
-- value like:
--   { "routines": [{ "id": "make_bed", "name": "Make bed", "pts": 10 }, ...] }
--
-- Transformation: one scout.routine_templates row per routine element.
--   routine_key            = element.id
--   label                  = element.name
--   block_label            = 'Chores'
--   recurrence             = 'daily'
--   owner_family_member_id = the member_config.family_member_id
--
-- Idempotent: ON CONFLICT DO NOTHING on the unique constraint
-- (family_id, routine_key, owner_family_member_id).
--
-- After migration the source rows are deleted from member_config.

DO $$
DECLARE
    mc      RECORD;
    routine RECORD;
    v_family_id UUID;
BEGIN
    FOR mc IN
        SELECT cfg.family_member_id, cfg.value
        FROM   member_config cfg
        WHERE  cfg.key = 'chores.routines'
    LOOP
        SELECT fm.family_id INTO v_family_id
        FROM   public.family_members fm
        WHERE  fm.id = mc.family_member_id;

        IF v_family_id IS NULL THEN
            CONTINUE;
        END IF;

        FOR routine IN
            SELECT r.value AS v
            FROM   jsonb_array_elements(mc.value -> 'routines') AS r
        LOOP
            -- Skip malformed elements that have no id or name
            IF routine.v ->> 'id' IS NULL OR routine.v ->> 'name' IS NULL THEN
                CONTINUE;
            END IF;

            INSERT INTO scout.routine_templates (
                family_id,
                routine_key,
                label,
                block_label,
                recurrence,
                owner_family_member_id
            ) VALUES (
                v_family_id,
                routine.v ->> 'id',
                routine.v ->> 'name',
                'Chores',
                'daily',
                mc.family_member_id
            )
            ON CONFLICT (family_id, routine_key, owner_family_member_id) DO NOTHING;
        END LOOP;
    END LOOP;
END $$;

-- Clean up source rows once migrated.
DELETE FROM member_config WHERE key = 'chores.routines';
