-- Sprint Expansion Phase 1: Push notification delivery
-- Adds per-device registration and per-attempt delivery log tables so
-- the backend can distinguish provider acceptance from provider handoff
-- and recover from DeviceNotRegistered errors by deactivating tokens.

-- 1. Registered push devices (one row per physical device per member).
CREATE TABLE IF NOT EXISTS scout.push_devices (
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_member_id                UUID NOT NULL REFERENCES public.family_members(id) ON DELETE CASCADE,
    expo_push_token                 TEXT NOT NULL UNIQUE,
    device_label                    TEXT,
    platform                        TEXT NOT NULL CHECK (platform IN ('ios', 'android', 'web')),
    app_version                     TEXT,
    is_active                       BOOLEAN NOT NULL DEFAULT true,
    last_registered_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_successful_delivery_at     TIMESTAMPTZ,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_push_devices_member
    ON scout.push_devices(family_member_id);
CREATE INDEX IF NOT EXISTS idx_push_devices_active
    ON scout.push_devices(is_active)
    WHERE is_active = true;

-- 2. Per-attempt delivery log. One row per (notification_group_id, device)
-- pair so a push to a member with three devices produces three rows that
-- share a notification_group_id.
CREATE TABLE IF NOT EXISTS scout.push_deliveries (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_group_id       UUID NOT NULL,
    family_member_id            UUID NOT NULL REFERENCES public.family_members(id) ON DELETE CASCADE,
    push_device_id              UUID NOT NULL REFERENCES scout.push_devices(id) ON DELETE CASCADE,
    provider                    TEXT NOT NULL DEFAULT 'expo' CHECK (provider IN ('expo')),
    category                    TEXT NOT NULL,
    title                       TEXT NOT NULL,
    body                        TEXT NOT NULL,
    data                        JSONB NOT NULL DEFAULT '{}'::jsonb,
    trigger_source              TEXT NOT NULL,
    status                      TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'provider_accepted', 'provider_handoff_ok', 'provider_error')),
    provider_ticket_id          TEXT,
    provider_receipt_status     TEXT,
    provider_receipt_payload    JSONB,
    error_message               TEXT,
    sent_at                     TIMESTAMPTZ,
    receipt_checked_at          TIMESTAMPTZ,
    provider_handoff_at         TIMESTAMPTZ,
    tapped_at                   TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_push_deliveries_member_created
    ON scout.push_deliveries(family_member_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_push_deliveries_status_created
    ON scout.push_deliveries(status, created_at);
CREATE INDEX IF NOT EXISTS idx_push_deliveries_group
    ON scout.push_deliveries(notification_group_id);

-- 3. Permission keys.
INSERT INTO scout.permissions (permission_key, description) VALUES
    ('push.register_device', 'Register an Expo push token for the current device'),
    ('push.revoke_device', 'Revoke one of the current member''s push devices'),
    ('push.send_to_member', 'Send a push notification to another family member'),
    ('push.view_delivery_log', 'View the family-wide push delivery log')
ON CONFLICT (permission_key) DO NOTHING;

-- push.register_device, push.revoke_device → everyone except DISPLAY_ONLY.
-- These are self-scoped device lifecycle actions the backend enforces
-- via family_member_id ownership, not via tier.
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('YOUNG_CHILD', 'CHILD', 'TEEN', 'PARENT', 'PRIMARY_PARENT')
  AND p.permission_key IN ('push.register_device', 'push.revoke_device')
ON CONFLICT DO NOTHING;

-- push.send_to_member, push.view_delivery_log → admin / parent_peer only
-- (PRIMARY_PARENT / PARENT in DB naming). Kids cannot push other kids
-- and cannot see the family-wide delivery log.
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('PARENT', 'PRIMARY_PARENT')
  AND p.permission_key IN ('push.send_to_member', 'push.view_delivery_log')
ON CONFLICT DO NOTHING;
