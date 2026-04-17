-- Migration 037: Migrate allowance.target from public.member_config
--                into scout.reward_policies (normalized rows).
--
-- Each member_config row with key = 'allowance.target' holds a JSONB
-- value like:
--   { "weekly_target_cents": 1000, "baseline_cents": 500, "payout_schedule": "weekly" }
--
-- Transformation: one scout.reward_policies row per member.
--   policy_key            = 'weekly_allowance'
--   baseline_amount_cents = value.baseline_cents (defaults to 0 if absent)
--   payout_schedule       = { "schedule": value.payout_schedule,
--                              "weekly_target_cents": value.weekly_target_cents }
--   effective_from        = CURRENT_DATE
--
-- Idempotent: ON CONFLICT DO NOTHING on the unique constraint
-- (family_id, family_member_id, policy_key, effective_from).
--
-- After migration the source rows are deleted from public.member_config.

DO $$
DECLARE
    mc          RECORD;
    v_family_id UUID;
    v_baseline  INTEGER;
    v_schedule  TEXT;
    v_weekly    INTEGER;
BEGIN
    FOR mc IN
        SELECT cfg.family_member_id, cfg.value
        FROM   public.member_config cfg
        WHERE  cfg.key = 'allowance.target'
    LOOP
        SELECT fm.family_id INTO v_family_id
        FROM   public.family_members fm
        WHERE  fm.id = mc.family_member_id;

        IF v_family_id IS NULL THEN
            CONTINUE;
        END IF;

        -- Coerce values defensively: missing keys become 0 / 'weekly'.
        v_baseline := COALESCE((mc.value ->> 'baseline_cents')::integer, 0);
        v_schedule := COALESCE(mc.value ->> 'payout_schedule', 'weekly');
        v_weekly   := COALESCE((mc.value ->> 'weekly_target_cents')::integer, 0);

        INSERT INTO scout.reward_policies (
            family_id,
            family_member_id,
            policy_key,
            baseline_amount_cents,
            payout_schedule,
            effective_from
        ) VALUES (
            v_family_id,
            mc.family_member_id,
            'weekly_allowance',
            v_baseline,
            jsonb_build_object(
                'schedule',             v_schedule,
                'weekly_target_cents',  v_weekly
            ),
            CURRENT_DATE
        )
        ON CONFLICT (family_id, family_member_id, policy_key, effective_from) DO NOTHING;
    END LOOP;
END $$;

-- Clean up source rows once migrated.
DELETE FROM public.member_config WHERE key = 'allowance.target';
