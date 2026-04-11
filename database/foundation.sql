-- Scout Foundation + Connectors DDL
-- Source of truth: Scout Foundation + Connectors ERD
-- Generated: 2026-04-08

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- updated_at trigger function
-- ============================================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- families (tenant boundary)
-- ============================================================================

CREATE TABLE IF NOT EXISTS families (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text        NOT NULL,
    timezone    text        NOT NULL DEFAULT 'America/Chicago',
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_families_updated_at
    BEFORE UPDATE ON families
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- family_members (people, may exist without a login)
-- ============================================================================

CREATE TABLE IF NOT EXISTS family_members (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id   uuid        NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    first_name  text        NOT NULL,
    last_name   text,
    role        text        NOT NULL,
    birthdate   date,
    is_active   boolean     NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_family_members_role CHECK (role IN ('adult', 'child'))
);

CREATE INDEX idx_family_members_family_id ON family_members (family_id);

CREATE TRIGGER trg_family_members_updated_at
    BEFORE UPDATE ON family_members
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- user_accounts (authentication identities)
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_accounts (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_member_id  uuid        NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    email             text,
    phone             text,
    auth_provider     text        NOT NULL,
    password_hash     text,
    is_primary        boolean     NOT NULL DEFAULT false,
    is_active         boolean     NOT NULL DEFAULT true,
    last_login_at     timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_user_accounts_auth_provider
        CHECK (auth_provider IN ('email', 'apple', 'google')),

    -- email-based auth requires a password hash
    CONSTRAINT chk_user_accounts_email_auth
        CHECK (auth_provider != 'email' OR password_hash IS NOT NULL)
);

-- nullable email: partial unique index ensures uniqueness only for non-null values
CREATE UNIQUE INDEX uq_user_accounts_email
    ON user_accounts (email)
    WHERE email IS NOT NULL;

CREATE INDEX idx_user_accounts_family_member_id ON user_accounts (family_member_id);

CREATE TRIGGER trg_user_accounts_updated_at
    BEFORE UPDATE ON user_accounts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- sessions
-- ============================================================================

CREATE TABLE IF NOT EXISTS sessions (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_account_id uuid        NOT NULL REFERENCES user_accounts (id) ON DELETE CASCADE,
    token           text        NOT NULL,
    expires_at      timestamptz NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),

    -- unique constraint creates the index; no separate CREATE INDEX needed
    CONSTRAINT uq_sessions_token UNIQUE (token)
);

CREATE INDEX idx_sessions_user_account_id ON sessions (user_account_id);
CREATE INDEX idx_sessions_expires_at ON sessions (expires_at);

-- ============================================================================
-- role_tiers
-- ============================================================================

CREATE TABLE IF NOT EXISTS role_tiers (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text        NOT NULL,
    permissions     jsonb       NOT NULL DEFAULT '{}',
    behavior_config jsonb       NOT NULL DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_role_tiers_name CHECK (name IN ('parent', 'admin', 'kid', 'viewer')),
    CONSTRAINT uq_role_tiers_name UNIQUE (name)
);

CREATE TRIGGER trg_role_tiers_updated_at
    BEFORE UPDATE ON role_tiers
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- role_tier_overrides (per-member overrides against a role_tier)
-- ============================================================================
-- Tenant safety: no direct family_id. Write-path must validate tenant
-- context via family_members.family_id before inserting.

CREATE TABLE IF NOT EXISTS role_tier_overrides (
    id                   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_member_id     uuid        NOT NULL REFERENCES family_members (id) ON DELETE CASCADE,
    role_tier_id         uuid        NOT NULL REFERENCES role_tiers (id) ON DELETE RESTRICT,
    override_permissions jsonb       NOT NULL DEFAULT '{}',
    override_behavior    jsonb       NOT NULL DEFAULT '{}',
    created_at           timestamptz NOT NULL DEFAULT now(),

    -- unique constraint's leading column covers family_member_id lookups
    CONSTRAINT uq_role_tier_overrides_member_tier
        UNIQUE (family_member_id, role_tier_id)
);

-- role_tier_id is not the leading column in the unique index, so it needs its own
CREATE INDEX idx_role_tier_overrides_role_tier_id ON role_tier_overrides (role_tier_id);

-- ============================================================================
-- connector_configs
-- ============================================================================
-- scope enforcement:
--   family  => family_id NOT NULL, family_member_id NULL
--   member  => family_member_id NOT NULL, family_id NULL
-- family_id is NOT carried on member-scoped rows; derive via family_members
-- if tenant scoping is needed at query time.

CREATE TABLE IF NOT EXISTS connector_configs (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id         uuid        REFERENCES families (id) ON DELETE CASCADE,
    family_member_id  uuid        REFERENCES family_members (id) ON DELETE CASCADE,
    connector_name    text        NOT NULL,
    auth_token        text,
    refresh_token     text,
    config            jsonb       NOT NULL DEFAULT '{}',
    scope             text        NOT NULL,
    sync_direction    text        NOT NULL,
    authority_level   text        NOT NULL,
    is_active         boolean     NOT NULL DEFAULT true,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_connector_configs_connector_name
        CHECK (connector_name IN (
            'google_calendar', 'hearth', 'ynab', 'apple_health', 'rex'
        )),

    CONSTRAINT chk_connector_configs_scope
        CHECK (scope IN ('family', 'member')),

    CONSTRAINT chk_connector_configs_sync_direction
        CHECK (sync_direction IN ('read', 'write', 'bidirectional')),

    CONSTRAINT chk_connector_configs_authority_level
        CHECK (authority_level IN ('source_of_truth', 'secondary')),

    CONSTRAINT chk_connector_configs_scope_family
        CHECK (scope != 'family' OR (family_id IS NOT NULL AND family_member_id IS NULL)),

    CONSTRAINT chk_connector_configs_scope_member
        CHECK (scope != 'member' OR (family_member_id IS NOT NULL AND family_id IS NULL))
);

CREATE INDEX idx_connector_configs_family_id ON connector_configs (family_id);
CREATE INDEX idx_connector_configs_family_member_id ON connector_configs (family_member_id);
CREATE INDEX idx_connector_configs_connector_name ON connector_configs (connector_name);

-- prevent duplicate ACTIVE configs per scope
CREATE UNIQUE INDEX uq_connector_configs_family
    ON connector_configs (family_id, connector_name)
    WHERE scope = 'family' AND is_active = true;

CREATE UNIQUE INDEX uq_connector_configs_member
    ON connector_configs (family_member_id, connector_name)
    WHERE scope = 'member' AND is_active = true;

CREATE TRIGGER trg_connector_configs_updated_at
    BEFORE UPDATE ON connector_configs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- connector_mappings (global external-ID bridge, intentionally decoupled)
-- ============================================================================
-- No FK to connector_configs. This table is polymorphic:
-- internal_table + internal_id point to any domain row.
-- connector_name + external_id point to any external system record.

CREATE TABLE IF NOT EXISTS connector_mappings (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_name  text        NOT NULL,
    internal_table  text        NOT NULL,
    internal_id     uuid        NOT NULL,
    external_id     text        NOT NULL,
    metadata        jsonb       NOT NULL DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT chk_connector_mappings_connector_name
        CHECK (connector_name IN (
            'google_calendar', 'hearth', 'ynab', 'apple_health', 'rex'
        )),

    CONSTRAINT uq_connector_mappings_internal
        UNIQUE (connector_name, internal_table, internal_id),

    CONSTRAINT uq_connector_mappings_external
        UNIQUE (connector_name, external_id)
);

-- leading columns of unique indexes are connector_name, not internal_table;
-- this index serves "find all mappings for this domain record" lookups
CREATE INDEX idx_connector_mappings_internal_lookup
    ON connector_mappings (internal_table, internal_id);
