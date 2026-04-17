-- Migration 034: Reconcile PR #15 permission system with 022 canonical schema
--
-- This migration unifies the two parallel permission systems:
--
--   System A (from 022): scout.permissions + scout.role_tier_permissions tables
--     with 9 permission keys and UPPERCASE canonical tier names
--     (PRIMARY_PARENT, PARENT, TEEN, CHILD, YOUNG_CHILD, DISPLAY_ONLY).
--
--   System B (from PR #15, migrations 024-027): JSONB `permissions` column on
--     public.role_tiers rows with 5 lowercase tiers (admin, parent_peer, teen,
--     child, kid) and 22+ permission keys stored as JSONB.
--
-- Goal: merge everything into System A. System B becomes dead code.
--
-- Steps:
--   1. Insert PR #15 permission keys into scout.permissions (idempotent).
--   2. Map the new permissions to canonical tiers via scout.role_tier_permissions.
--   3. Update public.role_tier_overrides FKs to point at canonical tier IDs.
--   4. Delete the 5 PR #15 duplicate tier rows.
--   5. Clear the JSONB permissions column on all remaining tier rows.
--
-- IMPORTANT: All table references are schema-qualified because the scout
-- schema has views over public.* tables and search_path may resolve
-- unqualified names to the wrong schema.

BEGIN;

-- ============================================================================
-- STEP 1: Insert PR #15 permission keys into scout.permissions
-- ============================================================================
-- The 022 migration already seeded 9 permission keys. Here we add the 22+
-- additional keys that PR #15 introduced via the JSONB approach. Idempotent
-- via WHERE NOT EXISTS.

INSERT INTO scout.permissions (permission_key, description)
SELECT permission_key, description FROM (VALUES
    ('family.manage_accounts',       'Create, edit, and remove sign-in accounts for family members'),
    ('family.manage_members',        'Add, remove, and edit family member profiles'),
    ('family.manage_learning_notes', 'Edit learning and personality notes for children'),
    ('scout_ai.manage_toggles',      'Toggle Scout AI capabilities for the family'),
    ('admin.manage_permissions',     'Assign role tiers and override permissions'),
    ('admin.manage_config',          'Edit family-wide and per-member configuration'),
    ('admin.view_config',            'View family-wide and per-member configuration'),
    ('admin.view_permissions',       'View the permissions matrix for all family members'),
    ('dashboard.view_parent',        'Access the parent dashboard and parent-only insights'),
    ('action_items.resolve',         'Resolve parent action items (briefs, alerts)'),
    ('allowance.run_payout',         'Trigger weekly allowance payouts'),
    ('allowance.manage_config',      'Configure per-kid allowance targets and rules'),
    ('chores.manage_config',         'Configure per-kid chore routines and point values'),
    ('grocery.manage_config',        'Configure stores, categories, and approval workflow'),
    ('grocery.approve',              'Approve pending grocery items'),
    ('grocery.add_item',             'Add items directly to the grocery list'),
    ('grocery.request_item',         'Request items for the grocery list (may require approval)'),
    ('purchase_request.approve',     'Approve or convert purchase requests from children'),
    ('purchase_request.submit',      'Submit purchase requests'),
    ('meals.manage_config',          'Configure meal plan rules, rating scale, dietary categories'),
    ('meal_plan.generate',           'Generate weekly meal plans'),
    ('meal_plan.approve',            'Approve draft weekly meal plans'),
    ('meal.review_self',             'Submit meal reviews'),
    ('rewards.manage_config',        'Configure reward tiers and redemption rules'),
    ('account.update_self',          'Update own account settings and password'),
    ('chore.complete_self',          'Mark own assigned chores as complete'),
    ('ai.manage',                    'Manage AI chat settings and view AI usage reports'),
    ('notes.manage_any',             'Create, edit, and delete family notes')
) AS seed(permission_key, description)
WHERE NOT EXISTS (
    SELECT 1 FROM scout.permissions p WHERE p.permission_key = seed.permission_key
);

-- ============================================================================
-- STEP 2: Map the new permissions to canonical tiers via scout.role_tier_permissions
-- ============================================================================

-- PRIMARY_PARENT + PARENT get ALL permissions except display.view_only
-- (which is reserved for the DISPLAY_ONLY tier).
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM public.role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('PRIMARY_PARENT', 'PARENT')
  AND p.permission_key NOT IN ('display.view_only')
  AND NOT EXISTS (
      SELECT 1 FROM scout.role_tier_permissions rtp
      WHERE rtp.role_tier_id = rt.id AND rtp.permission_id = p.id
  );

-- TEEN: self-scoped + limited autonomy (grocery add, purchase request submit)
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM public.role_tiers rt
JOIN scout.permissions p ON p.permission_key IN (
    'household.complete_own_task',
    'chore.complete_self',
    'rewards.view_own_payout',
    'account.update_self',
    'meal.review_self',
    'grocery.add_item',
    'purchase_request.submit'
)
WHERE rt.name = 'TEEN'
  AND NOT EXISTS (
      SELECT 1 FROM scout.role_tier_permissions rtp
      WHERE rtp.role_tier_id = rt.id AND rtp.permission_id = p.id
  );

-- CHILD: self-scoped + grocery request (not add), purchase request submit
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM public.role_tiers rt
JOIN scout.permissions p ON p.permission_key IN (
    'household.complete_own_task',
    'chore.complete_self',
    'rewards.view_own_payout',
    'account.update_self',
    'meal.review_self',
    'grocery.request_item',
    'purchase_request.submit'
)
WHERE rt.name = 'CHILD'
  AND NOT EXISTS (
      SELECT 1 FROM scout.role_tier_permissions rtp
      WHERE rtp.role_tier_id = rt.id AND rtp.permission_id = p.id
  );

-- YOUNG_CHILD: most restricted — chore completion + supervised grocery request only
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM public.role_tiers rt
JOIN scout.permissions p ON p.permission_key IN (
    'household.complete_own_task',
    'chore.complete_self',
    'rewards.view_own_payout',
    'grocery.request_item'
)
WHERE rt.name = 'YOUNG_CHILD'
  AND NOT EXISTS (
      SELECT 1 FROM scout.role_tier_permissions rtp
      WHERE rtp.role_tier_id = rt.id AND rtp.permission_id = p.id
  );

-- ============================================================================
-- STEP 3: Update public.role_tier_overrides to point at canonical tier IDs
-- ============================================================================
-- Roberts family members were assigned to PR #15 lowercase tiers in
-- migration 024. Re-point their override FKs to the canonical UPPERCASE
-- tiers before we delete the old rows.
--
-- Mapping:
--   admin        → PRIMARY_PARENT
--   parent_peer  → PARENT
--   teen         → TEEN
--   child        → CHILD
--   kid          → YOUNG_CHILD

UPDATE public.role_tier_overrides rto
SET role_tier_id = canonical.id
FROM public.role_tiers old_tier,
     public.role_tiers canonical
WHERE rto.role_tier_id = old_tier.id
  AND old_tier.name = CASE
      WHEN canonical.name = 'PRIMARY_PARENT' THEN 'admin'
      WHEN canonical.name = 'PARENT'         THEN 'parent_peer'
      WHEN canonical.name = 'TEEN'           THEN 'teen'
      WHEN canonical.name = 'CHILD'          THEN 'child'
      WHEN canonical.name = 'YOUNG_CHILD'    THEN 'kid'
      ELSE NULL
  END;

-- ============================================================================
-- STEP 4: Delete the 5 PR #15 duplicate tier rows
-- ============================================================================
-- Step 3 must run first so the FK constraint on role_tier_overrides is not
-- violated. Any remaining overrides pointing to these tiers would block the
-- delete — but the UPDATE above handles all known Roberts assignments.

DELETE FROM public.role_tiers WHERE name IN ('admin', 'parent_peer', 'teen', 'child', 'kid');

-- ============================================================================
-- STEP 5: Clear the JSONB permissions column on all remaining tier rows
-- ============================================================================
-- The JSONB column is no longer the source of truth for permissions.
-- resolve_effective_permissions() is being rewired to query
-- scout.role_tier_permissions instead. Clearing the column prevents
-- stale JSONB from being accidentally used by any code still referencing it.

UPDATE public.role_tiers SET permissions = '{}'::jsonb;

-- ============================================================================
-- Verification counts (logged via RAISE NOTICE for visibility)
-- ============================================================================

DO $$
DECLARE
    v_perm_count    integer;
    v_tier_count    integer;
    v_rtp_count     integer;
BEGIN
    SELECT COUNT(*) INTO v_perm_count FROM scout.permissions;
    SELECT COUNT(*) INTO v_tier_count FROM public.role_tiers;
    SELECT COUNT(*) INTO v_rtp_count  FROM scout.role_tier_permissions;

    RAISE NOTICE '034 reconcile_permissions: scout.permissions=%,  public.role_tiers=%,  scout.role_tier_permissions=%',
        v_perm_count, v_tier_count, v_rtp_count;
END $$;

COMMIT;
