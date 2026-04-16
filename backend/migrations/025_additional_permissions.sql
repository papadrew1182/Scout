-- Migration 025: Additional permission keys for Phase 2 control-plane migration
--
-- These keys were identified during the Phase 2 sweep of require_adult()
-- call sites. They did not exist in migration 024 and are added here via
-- UPDATE so that existing tier rows gain the new keys.
--
-- New keys and their intended meaning:
--   dashboard.view_parent     — view the parent dashboard and action inbox
--   action_items.resolve      — mark a parent action item as resolved
--   allowance.run_payout      — trigger the weekly payout run
--   scout_ai.manage_toggles   — toggle family-level AI settings (allow_general_chat, etc.)
--   family.manage_learning_notes — edit member grade_level / learning_notes / personality_notes
--   meal_plan.generate        — generate or save a weekly meal plan draft
--   meal_plan.approve         — approve, archive, or update a weekly meal plan
--
-- Granted to: admin + parent_peer (operational adult tiers)
-- NOT granted to: teen, child, kid
--
-- append-only: DO NOT edit migration 024 to add these keys.

BEGIN;

-- admin tier — grant all new keys
UPDATE role_tiers
SET permissions = permissions || '{
    "dashboard.view_parent":        true,
    "action_items.resolve":         true,
    "allowance.run_payout":         true,
    "scout_ai.manage_toggles":      true,
    "family.manage_learning_notes": true,
    "meal_plan.generate":           true,
    "meal_plan.approve":            true
}'::jsonb
WHERE name = 'admin';

-- parent_peer tier — grant all new keys (same operational scope as admin
-- except member/account management which is already excluded)
UPDATE role_tiers
SET permissions = permissions || '{
    "dashboard.view_parent":        true,
    "action_items.resolve":         true,
    "allowance.run_payout":         true,
    "scout_ai.manage_toggles":      true,
    "family.manage_learning_notes": true,
    "meal_plan.generate":           true,
    "meal_plan.approve":            true
}'::jsonb
WHERE name = 'parent_peer';

-- teen / child / kid tiers: no new permissions granted

COMMIT;
