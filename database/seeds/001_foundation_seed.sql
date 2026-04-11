-- Seed 001: Foundation + Connectors
-- Realistic fake data for local development and testing.
-- Requires: 001_foundation_connectors.sql applied first.
--
-- Family: the Whitfield household
-- Adults: Andrew (dad), Sally (mom), Tyler (adult, non-parent)
-- Children: Sadie (13), Townes (10), River (8)

BEGIN;

-- ============================================================================
-- family
-- ============================================================================

INSERT INTO families (id, name, timezone)
VALUES ('a1b2c3d4-0000-4000-8000-000000000001', 'Whitfield', 'America/Chicago');

-- ============================================================================
-- family_members
-- ============================================================================

-- adults
INSERT INTO family_members (id, family_id, first_name, last_name, role, birthdate)
VALUES
    ('b1000000-0000-4000-8000-000000000001',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'Andrew', 'Whitfield', 'adult', '1985-06-14'),

    ('b1000000-0000-4000-8000-000000000002',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'Sally', 'Whitfield', 'adult', '1987-03-22'),

    ('b1000000-0000-4000-8000-000000000006',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'Tyler', 'Whitfield', 'adult', '1990-01-15');

-- children
INSERT INTO family_members (id, family_id, first_name, last_name, role, birthdate)
VALUES
    ('b1000000-0000-4000-8000-000000000003',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'Sadie', 'Whitfield', 'child', '2012-09-10'),

    ('b1000000-0000-4000-8000-000000000004',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'Townes', 'Whitfield', 'child', '2015-11-28'),

    ('b1000000-0000-4000-8000-000000000005',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'River', 'Whitfield', 'child', '2017-07-04');

-- ============================================================================
-- user_accounts (adults only)
-- ============================================================================

-- password_hash is a bcrypt placeholder, not a real credential
INSERT INTO user_accounts (id, family_member_id, email, phone, auth_provider, password_hash, is_primary)
VALUES
    ('c1000000-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'andrew@whitfield.family', '+15125550101', 'email',
     '$2a$12$LJ3m4ys2Kq9PLACEHOLDER.HASH000000000000000000000000000',
     true),

    ('c1000000-0000-4000-8000-000000000002',
     'b1000000-0000-4000-8000-000000000002',
     'sally@whitfield.family', '+15125550102', 'google',
     NULL,
     false);

-- ============================================================================
-- role_tiers
-- ============================================================================

INSERT INTO role_tiers (id, name, permissions, behavior_config)
VALUES
    ('d1000000-0000-4000-8000-000000000001', 'parent',
     '{"manage_family": true, "manage_connectors": true, "manage_chores": true, "view_all": true}',
     '{"can_override_deadlines": true, "receives_digest": true}'),

    ('d1000000-0000-4000-8000-000000000002', 'admin',
     '{"manage_family": true, "manage_connectors": true, "manage_chores": true, "view_all": true}',
     '{"can_override_deadlines": true, "receives_digest": true}'),

    ('d1000000-0000-4000-8000-000000000003', 'kid',
     '{"view_own_tasks": true, "complete_tasks": true, "view_own_allowance": true}',
     '{"can_override_deadlines": false, "receives_digest": false}'),

    ('d1000000-0000-4000-8000-000000000004', 'viewer',
     '{"view_all": true}',
     '{"can_override_deadlines": false, "receives_digest": false}');

-- ============================================================================
-- role_tier_overrides
-- ============================================================================

-- Andrew: parent tier, no overrides needed (baseline)
INSERT INTO role_tier_overrides (id, family_member_id, role_tier_id, override_permissions, override_behavior)
VALUES
    ('e1000000-0000-4000-8000-000000000001',
     'b1000000-0000-4000-8000-000000000001',
     'd1000000-0000-4000-8000-000000000001',
     '{}', '{}');

-- Sally: parent tier, no overrides
INSERT INTO role_tier_overrides (id, family_member_id, role_tier_id, override_permissions, override_behavior)
VALUES
    ('e1000000-0000-4000-8000-000000000002',
     'b1000000-0000-4000-8000-000000000002',
     'd1000000-0000-4000-8000-000000000001',
     '{}', '{}');

-- Tyler: viewer tier, no overrides
INSERT INTO role_tier_overrides (id, family_member_id, role_tier_id, override_permissions, override_behavior)
VALUES
    ('e1000000-0000-4000-8000-000000000006',
     'b1000000-0000-4000-8000-000000000006',
     'd1000000-0000-4000-8000-000000000004',
     '{}', '{}');

-- Sadie: kid tier, override to allow viewing family calendar
INSERT INTO role_tier_overrides (id, family_member_id, role_tier_id, override_permissions, override_behavior)
VALUES
    ('e1000000-0000-4000-8000-000000000003',
     'b1000000-0000-4000-8000-000000000003',
     'd1000000-0000-4000-8000-000000000003',
     '{"view_family_calendar": true}',
     '{"receives_digest": true}');

-- Townes: kid tier, no overrides
INSERT INTO role_tier_overrides (id, family_member_id, role_tier_id, override_permissions, override_behavior)
VALUES
    ('e1000000-0000-4000-8000-000000000004',
     'b1000000-0000-4000-8000-000000000004',
     'd1000000-0000-4000-8000-000000000003',
     '{}', '{}');

-- River: kid tier, no overrides
INSERT INTO role_tier_overrides (id, family_member_id, role_tier_id, override_permissions, override_behavior)
VALUES
    ('e1000000-0000-4000-8000-000000000005',
     'b1000000-0000-4000-8000-000000000005',
     'd1000000-0000-4000-8000-000000000003',
     '{}', '{}');

-- ============================================================================
-- connector_configs
-- ============================================================================

-- google_calendar: family-scoped, bidirectional, source of truth
INSERT INTO connector_configs (id, family_id, family_member_id, connector_name, auth_token, refresh_token, config, scope, sync_direction, authority_level)
VALUES
    ('f1000000-0000-4000-8000-000000000001',
     'a1b2c3d4-0000-4000-8000-000000000001', NULL,
     'google_calendar',
     'ya29.FAKE_ACCESS_TOKEN_gcal',
     '1//FAKE_REFRESH_TOKEN_gcal',
     '{"calendar_id": "whitfield.family@gmail.com", "sync_interval_minutes": 15}',
     'family', 'bidirectional', 'source_of_truth');

-- hearth: family-scoped, read-only, source of truth for chores/routines
INSERT INTO connector_configs (id, family_id, family_member_id, connector_name, auth_token, refresh_token, config, scope, sync_direction, authority_level)
VALUES
    ('f1000000-0000-4000-8000-000000000002',
     'a1b2c3d4-0000-4000-8000-000000000001', NULL,
     'hearth',
     'hearth_tok_FAKE_abc123',
     'hearth_ref_FAKE_xyz789',
     '{"household_id": "hh_12345", "sync_routines": true, "sync_chores": true}',
     'family', 'read', 'source_of_truth');

-- ynab: family-scoped, read-only, source of truth for allowance/budget
INSERT INTO connector_configs (id, family_id, family_member_id, connector_name, auth_token, refresh_token, config, scope, sync_direction, authority_level)
VALUES
    ('f1000000-0000-4000-8000-000000000003',
     'a1b2c3d4-0000-4000-8000-000000000001', NULL,
     'ynab',
     'ynab_tok_FAKE_def456',
     'ynab_ref_FAKE_uvw321',
     '{"budget_id": "budget-fake-uuid-here", "allowance_category_group": "Kids Allowance"}',
     'family', 'read', 'source_of_truth');

-- ============================================================================
-- connector_mappings
-- ============================================================================

-- google_calendar: family -> external calendar ID
INSERT INTO connector_mappings (id, connector_name, internal_table, internal_id, external_id, metadata)
VALUES
    ('aa000000-0000-4000-8000-000000000001',
     'google_calendar', 'families',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'whitfield.family@gmail.com',
     '{"resource_type": "calendar"}');

-- hearth: family -> external household
INSERT INTO connector_mappings (id, connector_name, internal_table, internal_id, external_id, metadata)
VALUES
    ('aa000000-0000-4000-8000-000000000002',
     'hearth', 'families',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'hh_12345',
     '{"resource_type": "household"}');

-- hearth: Sadie -> external hearth member
INSERT INTO connector_mappings (id, connector_name, internal_table, internal_id, external_id, metadata)
VALUES
    ('aa000000-0000-4000-8000-000000000003',
     'hearth', 'family_members',
     'b1000000-0000-4000-8000-000000000003',
     'hearth_member_sadie_001',
     '{"resource_type": "member", "display_name": "Sadie"}');

-- hearth: Townes -> external hearth member
INSERT INTO connector_mappings (id, connector_name, internal_table, internal_id, external_id, metadata)
VALUES
    ('aa000000-0000-4000-8000-000000000004',
     'hearth', 'family_members',
     'b1000000-0000-4000-8000-000000000004',
     'hearth_member_townes_001',
     '{"resource_type": "member", "display_name": "Townes"}');

-- hearth: River -> external hearth member
INSERT INTO connector_mappings (id, connector_name, internal_table, internal_id, external_id, metadata)
VALUES
    ('aa000000-0000-4000-8000-000000000005',
     'hearth', 'family_members',
     'b1000000-0000-4000-8000-000000000005',
     'hearth_member_river_001',
     '{"resource_type": "member", "display_name": "River"}');

-- ynab: family -> external YNAB budget
INSERT INTO connector_mappings (id, connector_name, internal_table, internal_id, external_id, metadata)
VALUES
    ('aa000000-0000-4000-8000-000000000006',
     'ynab', 'families',
     'a1b2c3d4-0000-4000-8000-000000000001',
     'budget-fake-uuid-here',
     '{"resource_type": "budget", "budget_name": "Whitfield Family"}');

COMMIT;
