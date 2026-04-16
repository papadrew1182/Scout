-- Migration 027: Add feature-specific admin permissions and admin management keys
--
-- Adds new permission keys for feature-specific admin configuration:
--   allowance.manage_config  — configure allowance settings
--   chores.manage_config     — configure chores settings
--   grocery.manage_config    — configure grocery settings
--   meals.manage_config      — configure meals settings
--
-- Also adds keys for admin surface management (Phase 4 readiness):
--   admin.view_config        — view system configuration (gating entry to /admin)
--   admin.view_permissions   — view role tiers and permissions
--   admin.manage_permissions — edit role tiers and permission overrides
--
-- These are granted to admin and parent_peer tiers to enable operational
-- access to the new admin control surface without permissions escalation.
--
-- Granted to: admin + parent_peer (operational adult tiers)

BEGIN;

-- admin tier — grant all new keys
UPDATE role_tiers
SET permissions = permissions || '{
    "allowance.manage_config":  true,
    "chores.manage_config":     true,
    "grocery.manage_config":    true,
    "meals.manage_config":      true,
    "admin.view_config":        true,
    "admin.view_permissions":   true,
    "admin.manage_permissions": true
}'::jsonb
WHERE name = 'admin';

-- parent_peer tier — grant all new keys (same operational scope as admin
-- except member/account management which is already excluded)
UPDATE role_tiers
SET permissions = permissions || '{
    "allowance.manage_config":  true,
    "chores.manage_config":     true,
    "grocery.manage_config":    true,
    "meals.manage_config":      true,
    "admin.view_config":        true,
    "admin.view_permissions":   true,
    "admin.manage_permissions": true
}'::jsonb
WHERE name = 'parent_peer';

COMMIT;
