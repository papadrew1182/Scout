-- Phase 4: Home maintenance permission keys

INSERT INTO scout.permissions (permission_key, description) VALUES
('home.manage_zones', 'Create and manage home zones'),
('home.manage_assets', 'Create and manage home assets'),
('home.manage_templates', 'Create and manage maintenance templates'),
('home.complete_instance', 'Complete maintenance instances'),
('home.view', 'View home maintenance data')
ON CONFLICT (permission_key) DO NOTHING;

-- home.manage_zones, home.manage_assets, home.manage_templates -> PARENT, PRIMARY_PARENT
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('PARENT', 'PRIMARY_PARENT')
  AND p.permission_key IN ('home.manage_zones', 'home.manage_assets', 'home.manage_templates')
ON CONFLICT DO NOTHING;

-- home.complete_instance, home.view -> all tiers except DISPLAY_ONLY
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('YOUNG_CHILD', 'CHILD', 'TEEN', 'PARENT', 'PRIMARY_PARENT')
  AND p.permission_key IN ('home.complete_instance', 'home.view')
ON CONFLICT DO NOTHING;
