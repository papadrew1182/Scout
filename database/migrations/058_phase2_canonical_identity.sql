-- Migration 058: Phase 2 PR 2.1 - canonical identity tables.
--
-- Builds scout.{families, family_members, user_accounts, role_tiers,
-- role_tier_overrides, member_config} from snapshot DDL contract.
-- Seeds 6 reference rows in scout.role_tiers.
-- Restores 63 of 68 expected post-Phase-2 §2 FKs (PR 2.6 reconciles
-- the full 68-row set; the remaining 5 are owned by PR 2.2 and PR 2.5).
--
-- Spec: docs/plans/2026-04-25_canonical_rewrite_manifest_v1_1.md v1.1.2
--       §6 PR 2.1 gate criteria 1-9.
-- Snapshot DDL: docs/plans/_snapshots/2026-04-22_pre_rewrite_full.sql
--
-- Risk class: first canonical schema mutation since 057. Every DDL and
-- DML reference is schema-qualified per §6 criterion 7. CREATE TABLE
-- is used without IF NOT EXISTS — fail loudly on collision per §6
-- criterion 6 (the six identity tables must not pre-exist as base
-- tables; if they do, something has drifted and we want to know).
--
-- All FKs land convalidated = true (no NOT VALID); the verification
-- block at the end of this file asserts that contract before commit.

BEGIN;

-- =====================================================================
-- Step A: tables with no FK dependencies.
-- =====================================================================
-- scout.families and scout.role_tiers can be built independently.
-- Both are referenced by Step B/C tables, so they go first.

CREATE TABLE scout.families (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    timezone text DEFAULT 'America/Chicago'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    allow_general_chat boolean DEFAULT true NOT NULL,
    allow_homework_help boolean DEFAULT true NOT NULL,
    home_location text
);

ALTER TABLE scout.families
    ADD CONSTRAINT families_pkey PRIMARY KEY (id);

CREATE TABLE scout.role_tiers (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    permissions jsonb DEFAULT '{}'::jsonb NOT NULL,
    behavior_config jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    description text
);

ALTER TABLE scout.role_tiers
    ADD CONSTRAINT role_tiers_pkey PRIMARY KEY (id);

ALTER TABLE scout.role_tiers
    ADD CONSTRAINT uq_role_tiers_name UNIQUE (name);

-- =====================================================================
-- Step B: scout.family_members (FK to scout.families).
-- =====================================================================
-- chk_family_members_role preserves snapshot casing exactly: lowercase
-- 'adult'/'child'. Do not normalize to uppercase.

CREATE TABLE scout.family_members (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_id uuid NOT NULL,
    first_name text NOT NULL,
    last_name text,
    role text NOT NULL,
    birthdate date,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    grade_level text,
    learning_notes text,
    read_aloud_enabled boolean DEFAULT false NOT NULL,
    personality_notes text,
    CONSTRAINT chk_family_members_role CHECK ((role = ANY (ARRAY['adult'::text, 'child'::text])))
);

ALTER TABLE scout.family_members
    ADD CONSTRAINT family_members_pkey PRIMARY KEY (id);

ALTER TABLE scout.family_members
    ADD CONSTRAINT family_members_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

-- =====================================================================
-- Step C: scout.user_accounts, scout.role_tier_overrides, scout.member_config.
-- =====================================================================
-- All three depend on scout.family_members (and role_tier_overrides also
-- depends on scout.role_tiers). Built after Step B.

-- ---- scout.user_accounts ------------------------------------------------
-- chk_user_accounts_auth_provider locks the provider vocabulary.
-- chk_user_accounts_email_auth requires password_hash when auth_provider
-- is 'email' (otherwise email-auth users could be created without
-- credentials).

CREATE TABLE scout.user_accounts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_member_id uuid NOT NULL,
    email text,
    phone text,
    auth_provider text NOT NULL,
    password_hash text,
    is_primary boolean DEFAULT false NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    last_login_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_user_accounts_auth_provider CHECK ((auth_provider = ANY (ARRAY['email'::text, 'apple'::text, 'google'::text]))),
    CONSTRAINT chk_user_accounts_email_auth CHECK (((auth_provider <> 'email'::text) OR (password_hash IS NOT NULL)))
);

ALTER TABLE scout.user_accounts
    ADD CONSTRAINT user_accounts_pkey PRIMARY KEY (id);

ALTER TABLE scout.user_accounts
    ADD CONSTRAINT user_accounts_family_member_id_fkey
    FOREIGN KEY (family_member_id) REFERENCES scout.family_members(id) ON DELETE CASCADE;

-- ---- scout.role_tier_overrides ------------------------------------------
-- uq_role_tier_overrides_member enforces "one override row per member."

CREATE TABLE scout.role_tier_overrides (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_member_id uuid NOT NULL,
    role_tier_id uuid NOT NULL,
    override_permissions jsonb DEFAULT '{}'::jsonb NOT NULL,
    override_behavior jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE scout.role_tier_overrides
    ADD CONSTRAINT role_tier_overrides_pkey PRIMARY KEY (id);

ALTER TABLE scout.role_tier_overrides
    ADD CONSTRAINT uq_role_tier_overrides_member UNIQUE (family_member_id);

ALTER TABLE scout.role_tier_overrides
    ADD CONSTRAINT role_tier_overrides_family_member_id_fkey
    FOREIGN KEY (family_member_id) REFERENCES scout.family_members(id) ON DELETE CASCADE;

ALTER TABLE scout.role_tier_overrides
    ADD CONSTRAINT role_tier_overrides_role_tier_id_fkey
    FOREIGN KEY (role_tier_id) REFERENCES scout.role_tiers(id) ON DELETE RESTRICT;

-- ---- scout.member_config ------------------------------------------------
-- member_config_family_member_id_key_key (the doubled '_key' name is
-- exactly what the snapshot has — preserved verbatim) enforces one row
-- per (family_member_id, key) pair.

CREATE TABLE scout.member_config (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    family_member_id uuid NOT NULL,
    key text NOT NULL,
    value jsonb NOT NULL,
    updated_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

ALTER TABLE scout.member_config
    ADD CONSTRAINT member_config_pkey PRIMARY KEY (id);

ALTER TABLE scout.member_config
    ADD CONSTRAINT member_config_family_member_id_key_key UNIQUE (family_member_id, key);

ALTER TABLE scout.member_config
    ADD CONSTRAINT member_config_family_member_id_fkey
    FOREIGN KEY (family_member_id) REFERENCES scout.family_members(id) ON DELETE CASCADE;

ALTER TABLE scout.member_config
    ADD CONSTRAINT member_config_updated_by_fkey
    FOREIGN KEY (updated_by) REFERENCES scout.family_members(id) ON DELETE SET NULL;

-- =====================================================================
-- Step D: indexes and triggers.
-- =====================================================================
-- Five indexes on the rebuilt tables (PKs and uniques already create
-- their own implicit indexes; these are the explicit ones from the
-- snapshot). uq_user_accounts_email is partial: WHERE email IS NOT NULL.
-- Six updated_at triggers all invoke public.set_updated_at() — do not
-- normalize to clock_timestamp() or any other function.

CREATE INDEX idx_family_members_family_id ON scout.family_members USING btree (family_id);
CREATE INDEX idx_user_accounts_family_member_id ON scout.user_accounts USING btree (family_member_id);
CREATE UNIQUE INDEX uq_user_accounts_email ON scout.user_accounts USING btree (email) WHERE (email IS NOT NULL);
CREATE INDEX idx_role_tier_overrides_role_tier_id ON scout.role_tier_overrides USING btree (role_tier_id);
CREATE INDEX idx_member_config_member ON scout.member_config USING btree (family_member_id);

CREATE TRIGGER trg_families_updated_at BEFORE UPDATE ON scout.families FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_family_members_updated_at BEFORE UPDATE ON scout.family_members FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_user_accounts_updated_at BEFORE UPDATE ON scout.user_accounts FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_role_tiers_updated_at BEFORE UPDATE ON scout.role_tiers FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_role_tier_overrides_updated_at BEFORE UPDATE ON scout.role_tier_overrides FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_member_config_updated_at BEFORE UPDATE ON scout.member_config FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- =====================================================================
-- Step E: seed scout.role_tiers (6 canonical reference rows).
-- =====================================================================
-- Manifest §1.4 source-of-truth: exactly six tier names. No ADULT.
-- No lowercase variants. UUIDs come from gen_random_uuid() defaults —
-- non-deterministic. Phase 5 PR 5.1's role_tier_permissions reseed
-- joins on scout.role_tiers.name (the natural key), not on id.

INSERT INTO scout.role_tiers (name) VALUES
    ('DISPLAY_ONLY'),
    ('PRIMARY_PARENT'),
    ('PARENT'),
    ('TEEN'),
    ('YOUNG_CHILD'),
    ('CHILD');

-- =====================================================================
-- Step F: 63 §2 FK restores.
-- =====================================================================
-- Per manifest §6 PR 2.1 gate criterion 8:
--   27 FKs targeting scout.families(id)
--   28 FKs targeting scout.family_members(id)
--    6 FKs targeting scout.user_accounts(id)
--    2 FKs targeting scout.role_tiers(id)
--    0 FKs targeting scout.role_tier_overrides(id)
-- = 63 total. PR 2.6 reconciles the full 68-row post-Phase-2 set.
--
-- Each FK preserves the original constraint name, source column, and
-- ON DELETE action verbatim from §2; only the target schema is
-- rewritten from public.* to scout.*. All land convalidated = true.

-- ---- 27 FKs targeting scout.families(id) --------------------------------

ALTER TABLE scout.connector_accounts
    ADD CONSTRAINT connector_accounts_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.home_assets
    ADD CONSTRAINT home_assets_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.home_zones
    ADD CONSTRAINT home_zones_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.household_rules
    ADD CONSTRAINT household_rules_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.maintenance_instances
    ADD CONSTRAINT maintenance_instances_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.maintenance_templates
    ADD CONSTRAINT maintenance_templates_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.nudge_rules
    ADD CONSTRAINT nudge_rules_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.quiet_hours_family
    ADD CONSTRAINT quiet_hours_family_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.reward_policies
    ADD CONSTRAINT reward_policies_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.user_family_memberships
    ADD CONSTRAINT user_family_memberships_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.allowance_periods
    ADD CONSTRAINT allowance_periods_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.reward_extras_catalog
    ADD CONSTRAINT reward_extras_catalog_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.reward_ledger_entries
    ADD CONSTRAINT reward_ledger_entries_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.settlement_batches
    ADD CONSTRAINT settlement_batches_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.standards_of_done
    ADD CONSTRAINT standards_of_done_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.daily_win_results
    ADD CONSTRAINT daily_win_results_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.time_blocks
    ADD CONSTRAINT time_blocks_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.calendar_exports
    ADD CONSTRAINT calendar_exports_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.activity_events
    ADD CONSTRAINT activity_events_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.external_calendar_events
    ADD CONSTRAINT external_calendar_events_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.work_context_events
    ADD CONSTRAINT work_context_events_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.budget_snapshots
    ADD CONSTRAINT budget_snapshots_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.bill_snapshots
    ADD CONSTRAINT bill_snapshots_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.travel_estimates
    ADD CONSTRAINT travel_estimates_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.project_templates
    ADD CONSTRAINT project_templates_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

ALTER TABLE scout.projects
    ADD CONSTRAINT projects_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

-- Kept-public source: public.scout_scheduled_runs targeting scout.families.
ALTER TABLE public.scout_scheduled_runs
    ADD CONSTRAINT scout_scheduled_runs_family_id_fkey
    FOREIGN KEY (family_id) REFERENCES scout.families(id) ON DELETE CASCADE;

-- ---- 28 FKs targeting scout.family_members(id) --------------------------

ALTER TABLE scout.affirmations
    ADD CONSTRAINT affirmations_created_by_fkey
    FOREIGN KEY (created_by) REFERENCES scout.family_members(id) ON DELETE SET NULL;

ALTER TABLE scout.affirmations
    ADD CONSTRAINT affirmations_updated_by_fkey
    FOREIGN KEY (updated_by) REFERENCES scout.family_members(id) ON DELETE SET NULL;

ALTER TABLE scout.affirmation_feedback
    ADD CONSTRAINT affirmation_feedback_family_member_id_fkey
    FOREIGN KEY (family_member_id) REFERENCES scout.family_members(id) ON DELETE CASCADE;

ALTER TABLE scout.affirmation_delivery_log
    ADD CONSTRAINT affirmation_delivery_log_family_member_id_fkey
    FOREIGN KEY (family_member_id) REFERENCES scout.family_members(id) ON DELETE CASCADE;

ALTER TABLE scout.maintenance_instances
    ADD CONSTRAINT maintenance_instances_owner_member_id_fkey
    FOREIGN KEY (owner_member_id) REFERENCES scout.family_members(id) ON DELETE CASCADE;

ALTER TABLE scout.maintenance_instances
    ADD CONSTRAINT maintenance_instances_completed_by_member_id_fkey
    FOREIGN KEY (completed_by_member_id) REFERENCES scout.family_members(id) ON DELETE SET NULL;

ALTER TABLE scout.maintenance_templates
    ADD CONSTRAINT maintenance_templates_default_owner_member_id_fkey
    FOREIGN KEY (default_owner_member_id) REFERENCES scout.family_members(id) ON DELETE SET NULL;

ALTER TABLE scout.nudge_dispatch_items
    ADD CONSTRAINT nudge_dispatch_items_family_member_id_fkey
    FOREIGN KEY (family_member_id) REFERENCES scout.family_members(id) ON DELETE CASCADE;

ALTER TABLE scout.nudge_dispatches
    ADD CONSTRAINT nudge_dispatches_family_member_id_fkey
    FOREIGN KEY (family_member_id) REFERENCES scout.family_members(id) ON DELETE CASCADE;

ALTER TABLE scout.nudge_rules
    ADD CONSTRAINT nudge_rules_created_by_family_member_id_fkey
    FOREIGN KEY (created_by_family_member_id) REFERENCES scout.family_members(id) ON DELETE SET NULL;

ALTER TABLE scout.push_deliveries
    ADD CONSTRAINT push_deliveries_family_member_id_fkey
    FOREIGN KEY (family_member_id) REFERENCES scout.family_members(id) ON DELETE CASCADE;

ALTER TABLE scout.push_devices
    ADD CONSTRAINT push_devices_family_member_id_fkey
    FOREIGN KEY (family_member_id) REFERENCES scout.family_members(id) ON DELETE CASCADE;

ALTER TABLE scout.reward_policies
    ADD CONSTRAINT reward_policies_family_member_id_fkey
    FOREIGN KEY (family_member_id) REFERENCES scout.family_members(id) ON DELETE CASCADE;

ALTER TABLE scout.user_family_memberships
    ADD CONSTRAINT user_family_memberships_family_member_id_fkey
    FOREIGN KEY (family_member_id) REFERENCES scout.family_members(id) ON DELETE SET NULL;

ALTER TABLE scout.task_completions
    ADD CONSTRAINT task_completions_completed_by_fkey
    FOREIGN KEY (completed_by) REFERENCES scout.family_members(id) ON DELETE SET NULL;

ALTER TABLE scout.task_notes
    ADD CONSTRAINT task_notes_author_id_fkey
    FOREIGN KEY (author_id) REFERENCES scout.family_members(id) ON DELETE SET NULL;

ALTER TABLE scout.task_exceptions
    ADD CONSTRAINT task_exceptions_created_by_fkey
    FOREIGN KEY (created_by) REFERENCES scout.family_members(id) ON DELETE SET NULL;

ALTER TABLE scout.allowance_results
    ADD CONSTRAINT allowance_results_family_member_id_fkey
    FOREIGN KEY (family_member_id) REFERENCES scout.family_members(id) ON DELETE CASCADE;

ALTER TABLE scout.reward_ledger_entries
    ADD CONSTRAINT reward_ledger_entries_family_member_id_fkey
    FOREIGN KEY (family_member_id) REFERENCES scout.family_members(id) ON DELETE CASCADE;

ALTER TABLE scout.daily_win_results
    ADD CONSTRAINT daily_win_results_family_member_id_fkey
    FOREIGN KEY (family_member_id) REFERENCES scout.family_members(id) ON DELETE CASCADE;

ALTER TABLE scout.greenlight_exports
    ADD CONSTRAINT greenlight_exports_family_member_id_fkey
    FOREIGN KEY (family_member_id) REFERENCES scout.family_members(id) ON DELETE CASCADE;

ALTER TABLE scout.activity_events
    ADD CONSTRAINT activity_events_family_member_id_fkey
    FOREIGN KEY (family_member_id) REFERENCES scout.family_members(id) ON DELETE SET NULL;

ALTER TABLE scout.project_templates
    ADD CONSTRAINT project_templates_created_by_family_member_id_fkey
    FOREIGN KEY (created_by_family_member_id) REFERENCES scout.family_members(id) ON DELETE SET NULL;

ALTER TABLE scout.projects
    ADD CONSTRAINT projects_primary_owner_family_member_id_fkey
    FOREIGN KEY (primary_owner_family_member_id) REFERENCES scout.family_members(id) ON DELETE SET NULL;

ALTER TABLE scout.projects
    ADD CONSTRAINT projects_created_by_family_member_id_fkey
    FOREIGN KEY (created_by_family_member_id) REFERENCES scout.family_members(id) ON DELETE CASCADE;

ALTER TABLE scout.project_tasks
    ADD CONSTRAINT project_tasks_owner_family_member_id_fkey
    FOREIGN KEY (owner_family_member_id) REFERENCES scout.family_members(id) ON DELETE SET NULL;

ALTER TABLE scout.project_budget_entries
    ADD CONSTRAINT project_budget_entries_recorded_by_family_member_id_fkey
    FOREIGN KEY (recorded_by_family_member_id) REFERENCES scout.family_members(id) ON DELETE CASCADE;

-- Kept-public source: public.scout_scheduled_runs targeting scout.family_members.
ALTER TABLE public.scout_scheduled_runs
    ADD CONSTRAINT scout_scheduled_runs_member_id_fkey
    FOREIGN KEY (member_id) REFERENCES scout.family_members(id) ON DELETE CASCADE;

-- ---- 6 FKs targeting scout.user_accounts(id) ----------------------------

ALTER TABLE scout.connector_accounts
    ADD CONSTRAINT connector_accounts_user_account_id_fkey
    FOREIGN KEY (user_account_id) REFERENCES scout.user_accounts(id) ON DELETE SET NULL;

ALTER TABLE scout.device_registrations
    ADD CONSTRAINT device_registrations_user_account_id_fkey
    FOREIGN KEY (user_account_id) REFERENCES scout.user_accounts(id) ON DELETE CASCADE;

ALTER TABLE scout.user_family_memberships
    ADD CONSTRAINT user_family_memberships_user_account_id_fkey
    FOREIGN KEY (user_account_id) REFERENCES scout.user_accounts(id) ON DELETE CASCADE;

ALTER TABLE scout.user_preferences
    ADD CONSTRAINT user_preferences_user_account_id_fkey
    FOREIGN KEY (user_account_id) REFERENCES scout.user_accounts(id) ON DELETE CASCADE;

ALTER TABLE scout.work_context_events
    ADD CONSTRAINT work_context_events_user_account_id_fkey
    FOREIGN KEY (user_account_id) REFERENCES scout.user_accounts(id) ON DELETE SET NULL;

-- Kept-public source: public.sessions targeting scout.user_accounts.
ALTER TABLE public.sessions
    ADD CONSTRAINT sessions_user_account_id_fkey
    FOREIGN KEY (user_account_id) REFERENCES scout.user_accounts(id) ON DELETE CASCADE;

-- ---- 2 FKs targeting scout.role_tiers(id) -------------------------------

ALTER TABLE scout.role_tier_permissions
    ADD CONSTRAINT role_tier_permissions_role_tier_id_fkey
    FOREIGN KEY (role_tier_id) REFERENCES scout.role_tiers(id) ON DELETE CASCADE;

ALTER TABLE scout.user_family_memberships
    ADD CONSTRAINT user_family_memberships_role_tier_id_fkey
    FOREIGN KEY (role_tier_id) REFERENCES scout.role_tiers(id) ON DELETE SET NULL;

-- =====================================================================
-- Verification block (per §6 PR 2.1 gate criterion 6).
-- =====================================================================
-- Asserts every required object exists with the expected properties
-- before the migration commits. Any mismatch raises EXCEPTION and the
-- whole transaction rolls back.
--
-- Counts and exact-set assertions:
--   6 base tables
--   6 PKs
--   3 explicit unique constraints (uq_role_tier_overrides_member,
--                                  uq_role_tiers_name,
--                                  member_config_family_member_id_key_key);
--                                  PK-implicit uniques are counted in PKs above
--   3 CHECK constraints (chk_family_members_role,
--                        chk_user_accounts_auth_provider,
--                        chk_user_accounts_email_auth)
--   5 explicit indexes (incl. uq_user_accounts_email partial-predicate
--                       check that pg_index.indpred contains "email IS NOT NULL")
--   6 updated_at triggers (each verified to invoke public.set_updated_at()
--                          via tgfoid -> pg_proc -> pg_namespace)
--   6 internal FKs (rebuilt-table FKs)
--   63 §2 FKs (PR 2.1 owned subset) — exact-set match by
--             (constraint_name, source_qual, source_column, target_qual,
--              on_delete) using a FULL OUTER JOIN against an inline
--             VALUES list. Catches both "missing" and "unexpected"
--             constraints; raises EXCEPTION for either direction with
--             the offending constraint names.
-- All FKs must be convalidated = true.

DO $$
DECLARE
    cnt int;
    -- §2 FK exact-set difference outputs (missing or wrong-attributes;
    -- unexpected). Set to NULL by string_agg when no rows match the
    -- corresponding FILTER predicate, which is the pass condition.
    missing_fks text;
    extra_fks text;
    -- Partial-index predicate for uq_user_accounts_email, captured via
    -- pg_get_expr(indpred, indrelid). Expected to contain the substring
    -- "email IS NOT NULL".
    email_predicate text;
    expected_tables text[] := ARRAY[
        'families', 'family_members', 'user_accounts',
        'role_tiers', 'role_tier_overrides', 'member_config'
    ];
    expected_pkeys text[] := ARRAY[
        'families_pkey', 'family_members_pkey', 'user_accounts_pkey',
        'role_tiers_pkey', 'role_tier_overrides_pkey', 'member_config_pkey'
    ];
    expected_uniques text[] := ARRAY[
        'uq_role_tiers_name',
        'uq_role_tier_overrides_member',
        'member_config_family_member_id_key_key'
    ];
    expected_checks text[] := ARRAY[
        'chk_family_members_role',
        'chk_user_accounts_auth_provider',
        'chk_user_accounts_email_auth'
    ];
    expected_indexes text[] := ARRAY[
        'idx_family_members_family_id',
        'idx_user_accounts_family_member_id',
        'uq_user_accounts_email',
        'idx_role_tier_overrides_role_tier_id',
        'idx_member_config_member'
    ];
    expected_triggers text[] := ARRAY[
        'trg_families_updated_at',
        'trg_family_members_updated_at',
        'trg_user_accounts_updated_at',
        'trg_role_tiers_updated_at',
        'trg_role_tier_overrides_updated_at',
        'trg_member_config_updated_at'
    ];
    expected_internal_fks text[] := ARRAY[
        'family_members_family_id_fkey',
        'user_accounts_family_member_id_fkey',
        'role_tier_overrides_family_member_id_fkey',
        'role_tier_overrides_role_tier_id_fkey',
        'member_config_family_member_id_fkey',
        'member_config_updated_by_fkey'
    ];
BEGIN
    -- 6 base tables in scout.
    SELECT count(*) INTO cnt
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'scout' AND c.relkind = 'r' AND c.relname = ANY(expected_tables);
    IF cnt <> 6 THEN
        RAISE EXCEPTION '058 verification: expected 6 scout identity base tables, got %', cnt;
    END IF;

    -- 6 PKs.
    SELECT count(*) INTO cnt
    FROM pg_constraint c
    JOIN pg_namespace n ON n.oid = c.connamespace
    WHERE n.nspname = 'scout' AND c.contype = 'p' AND c.conname = ANY(expected_pkeys);
    IF cnt <> 6 THEN
        RAISE EXCEPTION '058 verification: expected 6 PKs, got %', cnt;
    END IF;

    -- 3 explicit unique constraints (excluding PK-implicit uniques).
    SELECT count(*) INTO cnt
    FROM pg_constraint c
    JOIN pg_namespace n ON n.oid = c.connamespace
    WHERE n.nspname = 'scout' AND c.contype = 'u' AND c.conname = ANY(expected_uniques);
    IF cnt <> 3 THEN
        RAISE EXCEPTION '058 verification: expected 3 unique constraints, got %', cnt;
    END IF;

    -- 3 CHECK constraints.
    SELECT count(*) INTO cnt
    FROM pg_constraint c
    JOIN pg_namespace n ON n.oid = c.connamespace
    WHERE n.nspname = 'scout' AND c.contype = 'c' AND c.conname = ANY(expected_checks);
    IF cnt <> 3 THEN
        RAISE EXCEPTION '058 verification: expected 3 CHECK constraints, got %', cnt;
    END IF;

    -- 5 explicit indexes.
    SELECT count(*) INTO cnt
    FROM pg_indexes
    WHERE schemaname = 'scout' AND indexname = ANY(expected_indexes);
    IF cnt <> 5 THEN
        RAISE EXCEPTION '058 verification: expected 5 explicit indexes, got %', cnt;
    END IF;

    -- uq_user_accounts_email partial-index predicate must contain
    -- "email IS NOT NULL". Per ChatGPT tertiary review: the index name
    -- check above does not prove the predicate. A regression that
    -- changed the predicate (e.g., to NOT NULL on a different column,
    -- or removed the partial-ness entirely so the index covers all
    -- rows including NULL emails) would still pass the name check.
    SELECT pg_get_expr(i.indpred, i.indrelid)
    INTO email_predicate
    FROM pg_index i
    JOIN pg_class c ON c.oid = i.indexrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'scout' AND c.relname = 'uq_user_accounts_email';
    IF email_predicate IS NULL THEN
        RAISE EXCEPTION '058 verification: uq_user_accounts_email index missing or has no partial predicate (pg_index.indpred IS NULL)';
    END IF;
    -- pg_get_expr renders the predicate as text; for the source
    -- "WHERE (email IS NOT NULL)" Postgres typically returns
    -- "email IS NOT NULL" (with or without enclosing parens).
    IF email_predicate NOT LIKE '%email IS NOT NULL%' THEN
        RAISE EXCEPTION '058 verification: uq_user_accounts_email predicate is wrong (expected "email IS NOT NULL", got: %)', email_predicate;
    END IF;

    -- 6 updated_at triggers, all invoking public.set_updated_at().
    -- Per ChatGPT tertiary review: name-only matching does not prove
    -- function target. Joining pg_proc + pg_namespace via tgfoid asserts
    -- the trigger fires public.set_updated_at() specifically — a
    -- regression that swapped the function (e.g., to a custom variant
    -- or to clock_timestamp() inline) would drop the count below 6.
    SELECT count(*) INTO cnt
    FROM pg_trigger t
    JOIN pg_class c ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_proc p ON p.oid = t.tgfoid
    JOIN pg_namespace pn ON pn.oid = p.pronamespace
    WHERE n.nspname = 'scout'
      AND NOT t.tgisinternal
      AND t.tgname = ANY(expected_triggers)
      AND p.proname = 'set_updated_at'
      AND pn.nspname = 'public';
    IF cnt <> 6 THEN
        RAISE EXCEPTION '058 verification: expected 6 updated_at triggers invoking public.set_updated_at(), got %', cnt;
    END IF;

    -- 6 internal FKs, all convalidated.
    SELECT count(*) INTO cnt
    FROM pg_constraint c
    JOIN pg_namespace n ON n.oid = c.connamespace
    WHERE n.nspname = 'scout'
      AND c.contype = 'f'
      AND c.convalidated = true
      AND c.conname = ANY(expected_internal_fks);
    IF cnt <> 6 THEN
        RAISE EXCEPTION '058 verification: expected 6 internal FKs convalidated, got %', cnt;
    END IF;

    -- 63 §2 FKs (PR 2.1 owned subset), exact-set match by
    -- (constraint_name, source_qual, source_column, target_qual,
    -- on_delete) using a FULL OUTER JOIN against an inline VALUES
    -- list of the expected 63 rows. Sources span scout.* (60) and
    -- public.* kept tables (3: sessions + 2 on scout_scheduled_runs).
    --
    -- Per ChatGPT tertiary review: count-only verification could pass
    -- with semantically wrong content (e.g., one expected FK missing
    -- AND one unexpected FK landed; or CASCADE swapped to SET NULL on
    -- two rows). The FULL OUTER JOIN below catches both directions:
    -- expected rows missing from actual aggregate to missing_fks;
    -- actual rows missing from expected aggregate to extra_fks. A
    -- single FK with wrong attributes shows in BOTH lists (its
    -- constraint name) — the operator can read that as "FK exists but
    -- with wrong attributes."
    --
    -- The actual-side filter pulls every FK whose target is one of
    -- the five identity tables (families, family_members,
    -- user_accounts, role_tiers, role_tier_overrides) excluding the
    -- six internal FKs sourced inside the new identity tables. This
    -- catches stray FKs that target role_tier_overrides (none expected
    -- in PR 2.1's owned subset) — they would show in extra_fks.
    SELECT
        string_agg(expected.conname, ', ' ORDER BY expected.conname) FILTER (WHERE actual.conname IS NULL),
        string_agg(actual.conname, ', ' ORDER BY actual.conname) FILTER (WHERE expected.conname IS NULL)
    INTO missing_fks, extra_fks
    FROM (VALUES
        -- 27 FKs targeting scout.families(id)
        ('connector_accounts_family_id_fkey', 'scout.connector_accounts', 'family_id', 'scout.families', 'CASCADE'),
        ('home_assets_family_id_fkey', 'scout.home_assets', 'family_id', 'scout.families', 'CASCADE'),
        ('home_zones_family_id_fkey', 'scout.home_zones', 'family_id', 'scout.families', 'CASCADE'),
        ('household_rules_family_id_fkey', 'scout.household_rules', 'family_id', 'scout.families', 'CASCADE'),
        ('maintenance_instances_family_id_fkey', 'scout.maintenance_instances', 'family_id', 'scout.families', 'CASCADE'),
        ('maintenance_templates_family_id_fkey', 'scout.maintenance_templates', 'family_id', 'scout.families', 'CASCADE'),
        ('nudge_rules_family_id_fkey', 'scout.nudge_rules', 'family_id', 'scout.families', 'CASCADE'),
        ('quiet_hours_family_family_id_fkey', 'scout.quiet_hours_family', 'family_id', 'scout.families', 'CASCADE'),
        ('reward_policies_family_id_fkey', 'scout.reward_policies', 'family_id', 'scout.families', 'CASCADE'),
        ('user_family_memberships_family_id_fkey', 'scout.user_family_memberships', 'family_id', 'scout.families', 'CASCADE'),
        ('allowance_periods_family_id_fkey', 'scout.allowance_periods', 'family_id', 'scout.families', 'CASCADE'),
        ('reward_extras_catalog_family_id_fkey', 'scout.reward_extras_catalog', 'family_id', 'scout.families', 'CASCADE'),
        ('reward_ledger_entries_family_id_fkey', 'scout.reward_ledger_entries', 'family_id', 'scout.families', 'CASCADE'),
        ('settlement_batches_family_id_fkey', 'scout.settlement_batches', 'family_id', 'scout.families', 'CASCADE'),
        ('standards_of_done_family_id_fkey', 'scout.standards_of_done', 'family_id', 'scout.families', 'CASCADE'),
        ('daily_win_results_family_id_fkey', 'scout.daily_win_results', 'family_id', 'scout.families', 'CASCADE'),
        ('time_blocks_family_id_fkey', 'scout.time_blocks', 'family_id', 'scout.families', 'CASCADE'),
        ('calendar_exports_family_id_fkey', 'scout.calendar_exports', 'family_id', 'scout.families', 'CASCADE'),
        ('activity_events_family_id_fkey', 'scout.activity_events', 'family_id', 'scout.families', 'CASCADE'),
        ('external_calendar_events_family_id_fkey', 'scout.external_calendar_events', 'family_id', 'scout.families', 'CASCADE'),
        ('work_context_events_family_id_fkey', 'scout.work_context_events', 'family_id', 'scout.families', 'CASCADE'),
        ('budget_snapshots_family_id_fkey', 'scout.budget_snapshots', 'family_id', 'scout.families', 'CASCADE'),
        ('bill_snapshots_family_id_fkey', 'scout.bill_snapshots', 'family_id', 'scout.families', 'CASCADE'),
        ('travel_estimates_family_id_fkey', 'scout.travel_estimates', 'family_id', 'scout.families', 'CASCADE'),
        ('project_templates_family_id_fkey', 'scout.project_templates', 'family_id', 'scout.families', 'CASCADE'),
        ('projects_family_id_fkey', 'scout.projects', 'family_id', 'scout.families', 'CASCADE'),
        ('scout_scheduled_runs_family_id_fkey', 'public.scout_scheduled_runs', 'family_id', 'scout.families', 'CASCADE'),
        -- 28 FKs targeting scout.family_members(id)
        ('affirmations_created_by_fkey', 'scout.affirmations', 'created_by', 'scout.family_members', 'SET NULL'),
        ('affirmations_updated_by_fkey', 'scout.affirmations', 'updated_by', 'scout.family_members', 'SET NULL'),
        ('affirmation_feedback_family_member_id_fkey', 'scout.affirmation_feedback', 'family_member_id', 'scout.family_members', 'CASCADE'),
        ('affirmation_delivery_log_family_member_id_fkey', 'scout.affirmation_delivery_log', 'family_member_id', 'scout.family_members', 'CASCADE'),
        ('maintenance_instances_owner_member_id_fkey', 'scout.maintenance_instances', 'owner_member_id', 'scout.family_members', 'CASCADE'),
        ('maintenance_instances_completed_by_member_id_fkey', 'scout.maintenance_instances', 'completed_by_member_id', 'scout.family_members', 'SET NULL'),
        ('maintenance_templates_default_owner_member_id_fkey', 'scout.maintenance_templates', 'default_owner_member_id', 'scout.family_members', 'SET NULL'),
        ('nudge_dispatch_items_family_member_id_fkey', 'scout.nudge_dispatch_items', 'family_member_id', 'scout.family_members', 'CASCADE'),
        ('nudge_dispatches_family_member_id_fkey', 'scout.nudge_dispatches', 'family_member_id', 'scout.family_members', 'CASCADE'),
        ('nudge_rules_created_by_family_member_id_fkey', 'scout.nudge_rules', 'created_by_family_member_id', 'scout.family_members', 'SET NULL'),
        ('push_deliveries_family_member_id_fkey', 'scout.push_deliveries', 'family_member_id', 'scout.family_members', 'CASCADE'),
        ('push_devices_family_member_id_fkey', 'scout.push_devices', 'family_member_id', 'scout.family_members', 'CASCADE'),
        ('reward_policies_family_member_id_fkey', 'scout.reward_policies', 'family_member_id', 'scout.family_members', 'CASCADE'),
        ('user_family_memberships_family_member_id_fkey', 'scout.user_family_memberships', 'family_member_id', 'scout.family_members', 'SET NULL'),
        ('task_completions_completed_by_fkey', 'scout.task_completions', 'completed_by', 'scout.family_members', 'SET NULL'),
        ('task_notes_author_id_fkey', 'scout.task_notes', 'author_id', 'scout.family_members', 'SET NULL'),
        ('task_exceptions_created_by_fkey', 'scout.task_exceptions', 'created_by', 'scout.family_members', 'SET NULL'),
        ('allowance_results_family_member_id_fkey', 'scout.allowance_results', 'family_member_id', 'scout.family_members', 'CASCADE'),
        ('reward_ledger_entries_family_member_id_fkey', 'scout.reward_ledger_entries', 'family_member_id', 'scout.family_members', 'CASCADE'),
        ('daily_win_results_family_member_id_fkey', 'scout.daily_win_results', 'family_member_id', 'scout.family_members', 'CASCADE'),
        ('greenlight_exports_family_member_id_fkey', 'scout.greenlight_exports', 'family_member_id', 'scout.family_members', 'CASCADE'),
        ('activity_events_family_member_id_fkey', 'scout.activity_events', 'family_member_id', 'scout.family_members', 'SET NULL'),
        ('project_templates_created_by_family_member_id_fkey', 'scout.project_templates', 'created_by_family_member_id', 'scout.family_members', 'SET NULL'),
        ('projects_primary_owner_family_member_id_fkey', 'scout.projects', 'primary_owner_family_member_id', 'scout.family_members', 'SET NULL'),
        ('projects_created_by_family_member_id_fkey', 'scout.projects', 'created_by_family_member_id', 'scout.family_members', 'CASCADE'),
        ('project_tasks_owner_family_member_id_fkey', 'scout.project_tasks', 'owner_family_member_id', 'scout.family_members', 'SET NULL'),
        ('project_budget_entries_recorded_by_family_member_id_fkey', 'scout.project_budget_entries', 'recorded_by_family_member_id', 'scout.family_members', 'CASCADE'),
        ('scout_scheduled_runs_member_id_fkey', 'public.scout_scheduled_runs', 'member_id', 'scout.family_members', 'CASCADE'),
        -- 6 FKs targeting scout.user_accounts(id)
        ('connector_accounts_user_account_id_fkey', 'scout.connector_accounts', 'user_account_id', 'scout.user_accounts', 'SET NULL'),
        ('device_registrations_user_account_id_fkey', 'scout.device_registrations', 'user_account_id', 'scout.user_accounts', 'CASCADE'),
        ('user_family_memberships_user_account_id_fkey', 'scout.user_family_memberships', 'user_account_id', 'scout.user_accounts', 'CASCADE'),
        ('user_preferences_user_account_id_fkey', 'scout.user_preferences', 'user_account_id', 'scout.user_accounts', 'CASCADE'),
        ('work_context_events_user_account_id_fkey', 'scout.work_context_events', 'user_account_id', 'scout.user_accounts', 'SET NULL'),
        ('sessions_user_account_id_fkey', 'public.sessions', 'user_account_id', 'scout.user_accounts', 'CASCADE'),
        -- 2 FKs targeting scout.role_tiers(id)
        ('role_tier_permissions_role_tier_id_fkey', 'scout.role_tier_permissions', 'role_tier_id', 'scout.role_tiers', 'CASCADE'),
        ('user_family_memberships_role_tier_id_fkey', 'scout.user_family_memberships', 'role_tier_id', 'scout.role_tiers', 'SET NULL')
    ) AS expected (conname, src_qual, src_col, tgt_qual, on_delete)
    FULL OUTER JOIN (
        SELECT
            c.conname::text AS conname,
            (src_ns.nspname || '.' || src.relname)::text AS src_qual,
            src_attr.attname::text AS src_col,
            (tgt_ns.nspname || '.' || tgt.relname)::text AS tgt_qual,
            CASE c.confdeltype
                WHEN 'c' THEN 'CASCADE'
                WHEN 'n' THEN 'SET NULL'
                WHEN 'r' THEN 'RESTRICT'
                WHEN 'a' THEN 'NO ACTION'
                WHEN 'd' THEN 'SET DEFAULT'
                ELSE 'UNKNOWN(' || c.confdeltype::text || ')'
            END AS on_delete
        FROM pg_constraint c
        JOIN pg_class src ON src.oid = c.conrelid
        JOIN pg_namespace src_ns ON src_ns.oid = src.relnamespace
        JOIN pg_attribute src_attr ON src_attr.attrelid = c.conrelid
                                  AND src_attr.attnum = c.conkey[1]
        JOIN pg_class tgt ON tgt.oid = c.confrelid
        JOIN pg_namespace tgt_ns ON tgt_ns.oid = tgt.relnamespace
        WHERE c.contype = 'f'
          AND c.convalidated = true
          AND tgt_ns.nspname = 'scout'
          AND tgt.relname IN ('families', 'family_members', 'user_accounts',
                              'role_tiers', 'role_tier_overrides')
          -- Exclude the 6 internal FKs sourced inside the new identity tables.
          AND NOT (src_ns.nspname = 'scout' AND src.relname IN (
              'family_members', 'user_accounts',
              'role_tier_overrides', 'member_config'
          ))
    ) AS actual
    ON expected.conname = actual.conname
       AND expected.src_qual = actual.src_qual
       AND expected.src_col = actual.src_col
       AND expected.tgt_qual = actual.tgt_qual
       AND expected.on_delete = actual.on_delete;

    IF missing_fks IS NOT NULL THEN
        RAISE EXCEPTION '058 verification: §2 FKs missing or with wrong attributes (constraint names): %', missing_fks;
    END IF;
    IF extra_fks IS NOT NULL THEN
        RAISE EXCEPTION '058 verification: unexpected §2 FKs landed (constraint names): %', extra_fks;
    END IF;

    -- 6 role_tiers reference rows by exact natural-key set.
    SELECT count(*) INTO cnt
    FROM scout.role_tiers
    WHERE name IN ('DISPLAY_ONLY', 'PRIMARY_PARENT', 'PARENT', 'TEEN', 'YOUNG_CHILD', 'CHILD');
    IF cnt <> 6 THEN
        RAISE EXCEPTION '058 verification: expected 6 canonical role_tiers rows, got %', cnt;
    END IF;

    -- Belt-and-suspenders: ensure no unexpected role_tier names slipped in.
    SELECT count(*) INTO cnt FROM scout.role_tiers;
    IF cnt <> 6 THEN
        RAISE EXCEPTION '058 verification: scout.role_tiers contains % rows, expected exactly 6', cnt;
    END IF;
END $$;

COMMIT;
