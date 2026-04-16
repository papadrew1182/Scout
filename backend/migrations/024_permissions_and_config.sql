-- Migration 024: Permissions + Configuration Control Plane
--
-- Phase 1 of the admin control plane.
--
-- role_tiers already exists (migration 001) with a restrictive CHECK constraint
-- on name and a UNIQUE(name) constraint. This migration:
--   1. Drops the old name CHECK so we can use the full five-tier vocabulary
--   2. Adds a 'description' column to role_tiers
--   3. Renames/replaces role_tier_overrides UNIQUE constraint from
--      UNIQUE(family_member_id, role_tier_id) to UNIQUE(family_member_id)
--      — a member has exactly one tier row (the active one)
--   4. Adds updated_at to role_tier_overrides (was missing in migration 001)
--   5. Creates family_config and member_config tables (new)
--   6. Seeds the five role tiers with their permission bundles
--   7. Seeds Roberts family tier assignments via role_tier_overrides
--
-- All DDL changes are guarded with IF EXISTS / IF NOT EXISTS so the
-- migration is safe to re-run.

BEGIN;

-- =============================================================================
-- 1. Extend role_tiers
-- =============================================================================

-- Drop the old CHECK constraint that restricted names to the legacy four-value set.
ALTER TABLE public.role_tiers
    DROP CONSTRAINT IF EXISTS chk_role_tiers_name;

-- Widen the name column to VARCHAR(20) if it is still TEXT (idempotent — TEXT
-- is wider so this is a no-op if already VARCHAR(20), but we unify the type).
-- We leave it as-is since TEXT >= VARCHAR(20); no explicit ALTER needed.

-- Add description column if not present.
ALTER TABLE public.role_tiers
    ADD COLUMN IF NOT EXISTS description TEXT;

-- Re-create the scout.role_tiers view so it picks up the new description
-- column. Postgres expands SELECT * at view-creation time, so adding a
-- column to public.role_tiers after the view exists does NOT update the
-- view's column list. Re-creating the view is the explicit refresh.
CREATE OR REPLACE VIEW scout.role_tiers AS SELECT * FROM public.role_tiers;

-- =============================================================================
-- 2. Extend role_tier_overrides
-- =============================================================================

-- Add updated_at if missing.
ALTER TABLE public.role_tier_overrides
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Drop the old composite UNIQUE (family_member_id, role_tier_id) and replace
-- with a single-column UNIQUE (family_member_id) so each member has exactly
-- one active tier assignment.
ALTER TABLE public.role_tier_overrides
    DROP CONSTRAINT IF EXISTS uq_role_tier_overrides_member_tier;

-- Also drop old unnamed unique constraint if it happens to exist with a
-- generated name (defensive).
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'public.role_tier_overrides'::regclass
          AND contype = 'u'
          AND conname != 'role_tier_overrides_pkey'
    LOOP
        EXECUTE 'ALTER TABLE public.role_tier_overrides DROP CONSTRAINT IF EXISTS ' || quote_ident(r.conname);
    END LOOP;
END $$;

ALTER TABLE public.role_tier_overrides
    ADD CONSTRAINT uq_role_tier_overrides_member UNIQUE (family_member_id);

-- Add updated_at trigger (guard: drop if already exists, then recreate).
DROP TRIGGER IF EXISTS trg_role_tier_overrides_updated_at ON public.role_tier_overrides;
CREATE TRIGGER trg_role_tier_overrides_updated_at
    BEFORE UPDATE ON public.role_tier_overrides
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Re-create the scout.role_tier_overrides view so it picks up the new
-- updated_at column (same reason as above — SELECT * is expanded at
-- view-creation time).
CREATE OR REPLACE VIEW scout.role_tier_overrides AS SELECT * FROM public.role_tier_overrides;

-- =============================================================================
-- 3. family_config — per-family key/value config store (new table)
-- =============================================================================

CREATE TABLE IF NOT EXISTS family_config (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id        UUID        NOT NULL REFERENCES public.families(id) ON DELETE CASCADE,
    key              TEXT        NOT NULL,
    value            JSONB       NOT NULL,
    updated_by       UUID        REFERENCES public.family_members(id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (family_id, key)
);

CREATE INDEX IF NOT EXISTS idx_family_config_family ON family_config(family_id);

DROP TRIGGER IF EXISTS trg_family_config_updated_at ON family_config;
CREATE TRIGGER trg_family_config_updated_at
    BEFORE UPDATE ON family_config
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- 4. member_config — per-member key/value config store (new table)
-- =============================================================================

CREATE TABLE IF NOT EXISTS member_config (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_member_id UUID        NOT NULL REFERENCES public.family_members(id) ON DELETE CASCADE,
    key              TEXT        NOT NULL,
    value            JSONB       NOT NULL,
    updated_by       UUID        REFERENCES public.family_members(id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (family_member_id, key)
);

CREATE INDEX IF NOT EXISTS idx_member_config_member ON member_config(family_member_id);

DROP TRIGGER IF EXISTS trg_member_config_updated_at ON member_config;
CREATE TRIGGER trg_member_config_updated_at
    BEFORE UPDATE ON member_config
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- 5. Seed: role_tiers
-- =============================================================================
-- Upsert five tiers. ON CONFLICT (name) DO UPDATE so repeated runs stay fresh.
--
-- admin tier
-- All *.manage, *.approve, family.*, members.*, admin.* permissions.

INSERT INTO public.role_tiers (name, description, permissions, behavior_config)
VALUES (
    'admin',
    'Full household administrator. Manages members, accounts, permissions, budgets, and all family configuration.',
    '{
        "family.view":                   true,
        "family.update":                 true,
        "family.manage_members":         true,
        "family.manage_accounts":        true,
        "family.manage_config":          true,
        "members.view":                  true,
        "members.update":                true,
        "members.manage":                true,
        "chore.view":                    true,
        "chore.manage":                  true,
        "chore.approve":                 true,
        "chore.complete_self":           true,
        "chore.complete_any":            true,
        "grocery.view":                  true,
        "grocery.add_item":              true,
        "grocery.manage":                true,
        "grocery.approve":               true,
        "grocery.request_item":          true,
        "meal.view":                     true,
        "meal.manage":                   true,
        "meal.approve":                  true,
        "meal.review_self":              true,
        "meal.review_any":               true,
        "account.view_self":             true,
        "account.update_self":           true,
        "account.view_any":              true,
        "account.manage":                true,
        "finance.view":                  true,
        "finance.manage":                true,
        "finance.approve":               true,
        "allowance.view":                true,
        "allowance.manage":              true,
        "allowance.approve":             true,
        "calendar.view":                 true,
        "calendar.manage":               true,
        "routine.view":                  true,
        "routine.manage":                true,
        "task.view":                     true,
        "task.manage":                   true,
        "task.complete_self":            true,
        "task.complete_any":             true,
        "daily_win.view":                true,
        "daily_win.manage":              true,
        "daily_win.approve":             true,
        "notes.view_self":               true,
        "notes.manage_self":             true,
        "notes.view_any":                true,
        "notes.manage_any":              true,
        "health.view_self":              true,
        "health.view_any":               true,
        "health.manage":                 true,
        "ai.chat":                       true,
        "ai.manage":                     true,
        "purchase_request.view":         true,
        "purchase_request.submit":       true,
        "purchase_request.approve":      true,
        "purchase_request.manage":       true,
        "admin.view_permissions":        true,
        "admin.manage_permissions":      true,
        "admin.view_config":             true,
        "admin.manage_config":           true
    }'::jsonb,
    '{}'::jsonb
)
ON CONFLICT (name) DO UPDATE
    SET description     = EXCLUDED.description,
        permissions     = EXCLUDED.permissions,
        behavior_config = EXCLUDED.behavior_config,
        updated_at      = NOW();

-- parent_peer tier
-- Same as admin minus family member/account management.

INSERT INTO public.role_tiers (name, description, permissions, behavior_config)
VALUES (
    'parent_peer',
    'Trusted adult co-parent with full operational access but cannot add/remove members or accounts.',
    '{
        "family.view":                   true,
        "family.update":                 true,
        "family.manage_config":          true,
        "members.view":                  true,
        "members.update":                true,
        "chore.view":                    true,
        "chore.manage":                  true,
        "chore.approve":                 true,
        "chore.complete_self":           true,
        "chore.complete_any":            true,
        "grocery.view":                  true,
        "grocery.add_item":              true,
        "grocery.manage":                true,
        "grocery.approve":               true,
        "grocery.request_item":          true,
        "meal.view":                     true,
        "meal.manage":                   true,
        "meal.approve":                  true,
        "meal.review_self":              true,
        "meal.review_any":               true,
        "account.view_self":             true,
        "account.update_self":           true,
        "finance.view":                  true,
        "finance.manage":                true,
        "finance.approve":               true,
        "allowance.view":                true,
        "allowance.manage":              true,
        "allowance.approve":             true,
        "calendar.view":                 true,
        "calendar.manage":               true,
        "routine.view":                  true,
        "routine.manage":                true,
        "task.view":                     true,
        "task.manage":                   true,
        "task.complete_self":            true,
        "task.complete_any":             true,
        "daily_win.view":                true,
        "daily_win.manage":              true,
        "daily_win.approve":             true,
        "notes.view_self":               true,
        "notes.manage_self":             true,
        "notes.view_any":                true,
        "notes.manage_any":              true,
        "health.view_self":              true,
        "health.view_any":               true,
        "health.manage":                 true,
        "ai.chat":                       true,
        "purchase_request.view":         true,
        "purchase_request.submit":       true,
        "purchase_request.approve":      true,
        "admin.view_permissions":        true,
        "admin.view_config":             true,
        "admin.manage_config":           true
    }'::jsonb,
    '{}'::jsonb
)
ON CONFLICT (name) DO UPDATE
    SET description     = EXCLUDED.description,
        permissions     = EXCLUDED.permissions,
        behavior_config = EXCLUDED.behavior_config,
        updated_at      = NOW();

-- teen tier
-- Older child with self-scoped writes + family read access.

INSERT INTO public.role_tiers (name, description, permissions, behavior_config)
VALUES (
    'teen',
    'Older child / teenager with self-scoped write access and family read access.',
    '{
        "family.view":                   true,
        "members.view":                  true,
        "chore.view":                    true,
        "chore.complete_self":           true,
        "grocery.view":                  true,
        "grocery.add_item":              true,
        "grocery.request_item":          true,
        "meal.view":                     true,
        "meal.review_self":              true,
        "account.view_self":             true,
        "account.update_self":           true,
        "allowance.view":                true,
        "calendar.view":                 true,
        "routine.view":                  true,
        "task.view":                     true,
        "task.complete_self":            true,
        "daily_win.view":                true,
        "notes.view_self":               true,
        "notes.manage_self":             true,
        "health.view_self":              true,
        "ai.chat":                       true,
        "purchase_request.submit":       true
    }'::jsonb,
    '{}'::jsonb
)
ON CONFLICT (name) DO UPDATE
    SET description     = EXCLUDED.description,
        permissions     = EXCLUDED.permissions,
        behavior_config = EXCLUDED.behavior_config,
        updated_at      = NOW();

-- child tier
-- School-age child with chore + request permissions and meal review.

INSERT INTO public.role_tiers (name, description, permissions, behavior_config)
VALUES (
    'child',
    'School-age child with chore completion, grocery requests, and meal review for self.',
    '{
        "family.view":                   true,
        "members.view":                  true,
        "chore.view":                    true,
        "chore.complete_self":           true,
        "grocery.view":                  true,
        "grocery.request_item":          true,
        "meal.view":                     true,
        "meal.review_self":              true,
        "account.view_self":             true,
        "account.update_self":           true,
        "allowance.view":                true,
        "calendar.view":                 true,
        "routine.view":                  true,
        "task.view":                     true,
        "task.complete_self":            true,
        "daily_win.view":                true,
        "notes.view_self":               true,
        "notes.manage_self":             true,
        "health.view_self":              true,
        "ai.chat":                       true,
        "purchase_request.submit":       true
    }'::jsonb,
    '{}'::jsonb
)
ON CONFLICT (name) DO UPDATE
    SET description     = EXCLUDED.description,
        permissions     = EXCLUDED.permissions,
        behavior_config = EXCLUDED.behavior_config,
        updated_at      = NOW();

-- kid tier
-- Young child with most restricted access.

INSERT INTO public.role_tiers (name, description, permissions, behavior_config)
VALUES (
    'kid',
    'Young child with chore completion and supervised grocery requests only.',
    '{
        "family.view":                   true,
        "members.view":                  true,
        "chore.view":                    true,
        "chore.complete_self":           true,
        "grocery.view":                  true,
        "grocery.request_item":          true,
        "meal.view":                     true,
        "account.view_self":             true,
        "allowance.view":                true,
        "calendar.view":                 true,
        "routine.view":                  true,
        "task.view":                     true,
        "task.complete_self":            true,
        "daily_win.view":                true,
        "notes.view_self":               true,
        "health.view_self":              true,
        "ai.chat":                       true
    }'::jsonb,
    '{}'::jsonb
)
ON CONFLICT (name) DO UPDATE
    SET description     = EXCLUDED.description,
        permissions     = EXCLUDED.permissions,
        behavior_config = EXCLUDED.behavior_config,
        updated_at      = NOW();

-- =============================================================================
-- 6. Seed: role_tier_overrides for the Roberts family
-- =============================================================================
-- Resolves member IDs by first_name within the Roberts family.
-- Uses ON CONFLICT (family_member_id) DO NOTHING so re-runs are safe.
--
-- Tier assignments:
--   Andrew, Sally  → admin
--   Tyler, Sadie   → teen
--   Townes         → child
--   River          → kid

DO $$
DECLARE
    v_family_id uuid;
BEGIN
    SELECT id INTO v_family_id
    FROM public.families
    WHERE name ILIKE 'Roberts%'
    ORDER BY created_at ASC
    LIMIT 1;

    IF v_family_id IS NULL THEN
        RAISE NOTICE 'roberts tier seed skipped: no Roberts family found';
        RETURN;
    END IF;

    INSERT INTO role_tier_overrides (family_member_id, role_tier_id)
    SELECT roberts.id, tiers.id
    FROM (
        SELECT id, first_name
        FROM public.family_members
        WHERE family_id = v_family_id AND is_active
    ) AS roberts
    JOIN (SELECT id, name FROM role_tiers) AS tiers
        ON tiers.name = CASE
            WHEN roberts.first_name IN ('Andrew', 'Sally')  THEN 'admin'
            WHEN roberts.first_name IN ('Tyler', 'Sadie')   THEN 'teen'
            WHEN roberts.first_name = 'Townes'              THEN 'child'
            WHEN roberts.first_name = 'River'               THEN 'kid'
            ELSE NULL
        END
    WHERE tiers.name IS NOT NULL
    ON CONFLICT (family_member_id) DO NOTHING;

    RAISE NOTICE 'roberts tier overrides seeded for family %', v_family_id;
END $$;

COMMIT;
