-- Migration 052: normalize the 046_* filename collision in
-- _scout_migrations tracking.
--
-- Background: PR #35 (Sprint Expansion Phase 1, push notifications)
-- and PR #37 (Sprint 04 Phase 1, AI conversation resume) both shipped
-- migrations named 046_*.sql on the same day. migrate.py tracks by
-- full filename so runtime behavior was correct, but the on-disk
-- ambiguity was flagged in five handoffs as cosmetic debt. This PR
-- renames the files to 046a_push_notifications.sql and
-- 046b_ai_conversation_resume.sql (earliest-PR = a).
--
-- On a database where the old filenames are already applied (Railway
-- production, any dev environment that ran the collision), this
-- migration rewrites the tracker rows so migrate.py does not
-- re-apply the renamed files. The underlying SQL in both migrations
-- is idempotent (CREATE TABLE IF NOT EXISTS, ADD COLUMN IF NOT
-- EXISTS), so even if this migration is skipped, no data harm; the
-- tracker would just carry two rows per migration.
--
-- On a fresh DB where only the new names ever existed, the DELETEs
-- match zero rows and the INSERTs collide with rows already inserted
-- by the rename files (046a_*.sql, 046b_*.sql) running earlier in
-- the same migrate.py pass. ON CONFLICT DO NOTHING makes that safe.

BEGIN;

-- The test conftest runs migrations directly without going through
-- migrate.py, so _scout_migrations may not exist in that path. Match
-- migrate.py's own setup so this migration is safe to run either way.
CREATE TABLE IF NOT EXISTS _scout_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT NOW()
);

-- Remove the old tracker rows if they exist.
DELETE FROM _scout_migrations
    WHERE filename IN (
        '046_push_notifications.sql',
        '046_ai_conversation_resume.sql'
    );

-- Ensure the new tracker rows exist. Idempotent on fresh DBs where
-- the rename files already inserted themselves in the same pass.
INSERT INTO _scout_migrations (filename)
VALUES
    ('046a_push_notifications.sql'),
    ('046b_ai_conversation_resume.sql')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
