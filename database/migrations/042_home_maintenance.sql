-- Phase 4: Home Maintenance OS - zones, assets, templates, instances

CREATE TABLE IF NOT EXISTS scout.home_zones (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       UUID NOT NULL REFERENCES public.families(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    zone_type       TEXT NOT NULL DEFAULT 'room',
    notes           TEXT,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scout.home_assets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       UUID NOT NULL REFERENCES public.families(id) ON DELETE CASCADE,
    zone_id         UUID REFERENCES scout.home_zones(id) ON DELETE SET NULL,
    name            TEXT NOT NULL,
    asset_type      TEXT,
    model           TEXT,
    serial          TEXT,
    purchase_date   DATE,
    warranty_expires_at TIMESTAMPTZ,
    manual_url      TEXT,
    receipt_url     TEXT,
    notes           TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scout.maintenance_templates (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id                   UUID NOT NULL REFERENCES public.families(id) ON DELETE CASCADE,
    zone_id                     UUID REFERENCES scout.home_zones(id) ON DELETE SET NULL,
    asset_id                    UUID REFERENCES scout.home_assets(id) ON DELETE SET NULL,
    name                        TEXT NOT NULL,
    description                 TEXT,
    cadence_type                TEXT NOT NULL DEFAULT 'monthly',
    rotation_month_mod          INTEGER,
    included                    JSONB NOT NULL DEFAULT '[]',
    not_included                JSONB NOT NULL DEFAULT '[]',
    done_means_done             TEXT,
    supplies                    JSONB NOT NULL DEFAULT '[]',
    estimated_duration_minutes  INTEGER,
    default_owner_member_id     UUID REFERENCES public.family_members(id) ON DELETE SET NULL,
    is_active                   BOOLEAN NOT NULL DEFAULT true,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scout.maintenance_instances (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id               UUID NOT NULL REFERENCES public.families(id) ON DELETE CASCADE,
    template_id             UUID NOT NULL REFERENCES scout.maintenance_templates(id) ON DELETE CASCADE,
    owner_member_id         UUID NOT NULL REFERENCES public.family_members(id) ON DELETE CASCADE,
    scheduled_for           TIMESTAMPTZ NOT NULL,
    completed_at            TIMESTAMPTZ,
    completed_by_member_id  UUID REFERENCES public.family_members(id) ON DELETE SET NULL,
    notes                   TEXT,
    is_active               BOOLEAN NOT NULL DEFAULT true,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_home_zones_family ON scout.home_zones(family_id);
CREATE INDEX IF NOT EXISTS idx_home_assets_family ON scout.home_assets(family_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_templates_family ON scout.maintenance_templates(family_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_instances_family_scheduled ON scout.maintenance_instances(family_id, scheduled_for);
