-- Migration 026: Seed scout_ai.toggles family_config for Roberts
--
-- Inserts a single family_config row under key "scout_ai.toggles" for
-- every family, seeding allow_general_chat and allow_homework_help from
-- the existing columns on the families table so the config store stays
-- consistent with whatever the legacy columns already say.
--
-- The two new toggle keys (proactive_suggestions, push_notifications)
-- have no legacy column equivalents — they default to true.
--
-- ON CONFLICT DO NOTHING makes this idempotent: re-running the migration
-- after the config row already exists is a no-op.

BEGIN;

INSERT INTO family_config (family_id, key, value)
SELECT
    id,
    'scout_ai.toggles',
    jsonb_build_object(
        'allow_general_chat',    allow_general_chat,
        'allow_homework_help',   allow_homework_help,
        'proactive_suggestions', true,
        'push_notifications',    true
    )
FROM families
ON CONFLICT (family_id, key) DO NOTHING;

COMMIT;
