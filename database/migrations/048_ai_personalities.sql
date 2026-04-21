-- Migration 048: Sprint 04 Phase 2 - per-member AI personalities
--
-- No new tables. The per-member personality config lives in the
-- existing member_config table under key 'ai.personality'. Storing
-- through a JSON-keyed config table rather than a dedicated schema
-- means tier-default merging happens at read time in the backend
-- service layer; future members work without any backfill.
--
-- Permission keys:
--   ai.edit_own_personality - all user tiers can tune their own voice
--   ai.edit_any_personality - PARENT and PRIMARY_PARENT only, for
--       admin-surface editing of another member's personality.
--
-- DISPLAY_ONLY excluded by existing repo convention.

BEGIN;

INSERT INTO scout.permissions (permission_key, description) VALUES
    ('ai.edit_own_personality',
     'Edit own Scout AI personality config (tone, vocabulary, verbosity, notes)'),
    ('ai.edit_any_personality',
     'Edit another family member''s Scout AI personality config (admin surface)')
ON CONFLICT (permission_key) DO NOTHING;

-- ai.edit_own_personality: all user tiers
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('YOUNG_CHILD', 'CHILD', 'TEEN', 'PARENT', 'PRIMARY_PARENT')
  AND p.permission_key = 'ai.edit_own_personality'
ON CONFLICT DO NOTHING;

-- ai.edit_any_personality: PARENT + PRIMARY_PARENT only
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('PARENT', 'PRIMARY_PARENT')
  AND p.permission_key = 'ai.edit_any_personality'
ON CONFLICT DO NOTHING;

COMMIT;
