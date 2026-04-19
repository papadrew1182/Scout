-- Phase 2: Manual data entry permission keys
-- Adds tasks.manage_self, calendar.manage_self, meals.manage_staples
-- and grants them to appropriate role tiers.

-- 1. Insert permission keys
INSERT INTO scout.permissions (permission_key, description) VALUES
('tasks.manage_self', 'Create, update, complete, and delete own personal tasks'),
('calendar.manage_self', 'Create, update, and delete own calendar events'),
('meals.manage_staples', 'Create and manage meal staples library (admin)')
ON CONFLICT (permission_key) DO NOTHING;

-- 2. Grant tasks.manage_self to YOUNG_CHILD, CHILD, TEEN, PARENT, PRIMARY_PARENT
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('YOUNG_CHILD', 'CHILD', 'TEEN', 'PARENT', 'PRIMARY_PARENT')
  AND p.permission_key = 'tasks.manage_self'
ON CONFLICT DO NOTHING;

-- 3. Grant calendar.manage_self to TEEN, PARENT, PRIMARY_PARENT
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('TEEN', 'PARENT', 'PRIMARY_PARENT')
  AND p.permission_key = 'calendar.manage_self'
ON CONFLICT DO NOTHING;

-- 4. Grant meals.manage_staples to PARENT, PRIMARY_PARENT
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('PARENT', 'PRIMARY_PARENT')
  AND p.permission_key = 'meals.manage_staples'
ON CONFLICT DO NOTHING;
