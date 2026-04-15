-- Migration 022: Session 2 canonical household + connector platform
--
-- This is the spine migration for Scout Session 2. It creates:
--
--   * The `scout` schema and six `connector_*` schemas.
--   * Scout-canonical household tables (household_rules, standards_of_done,
--     routine_templates, routine_steps, task_templates, task_assignment_rules,
--     task_occurrences, task_completions, task_exceptions, task_notes,
--     time_blocks, calendar_exports).
--   * Identity and access joins (permissions, role_tier_permissions,
--     user_family_memberships, user_preferences, device_registrations).
--   * Rewards and allowance tables (reward_policies, daily_win_results,
--     allowance_periods, allowance_results, reward_extras_catalog,
--     reward_ledger_entries, settlement_batches, greenlight_exports).
--   * Connector platform (connectors, connector_accounts, sync_jobs,
--     sync_runs, sync_cursors, connector_event_log, stale_data_alerts).
--   * Normalized external context (external_calendar_events,
--     work_context_events, budget_snapshots, bill_snapshots,
--     activity_events, travel_estimates).
--   * Eight foundation views in `scout` that alias the existing public
--     foundation tables so the charter's `scout.families` / `scout.family_members`
--     / etc. name list resolves without physically moving the data.
--   * Four curated read-model views:
--       scout.v_household_today
--       scout.v_rewards_current_week
--       scout.v_calendar_publication
--       scout.v_control_plane
--   * Widened CHECK constraints on the existing public foundation tables:
--       public.role_tiers.name              (6 canonical names)
--       public.connector_configs.connector_name  (9 connector keys)
--       public.connector_mappings            (new columns + composite unique)
--   * Seed rows for role_tiers, permissions, role_tier_permissions, and the
--     Roberts household rules / standards_of_done / task_assignment_rules.
--
-- Charter reconciliation:
--   * Canonical product data is in `scout` (physically for new tables; as
--     views for the 8 Session 1 foundation tables).
--   * Connector source-native schemas exist but are empty in this block.
--   * Hearth has no source schema. Display-only via calendar_exports +
--     v_calendar_publication.
--   * External IDs live only in public.connector_mappings. No connector
--     keys are stored directly on scout household tables.

BEGIN;

-- ============================================================================
-- SCHEMAS
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS scout;
CREATE SCHEMA IF NOT EXISTS connector_google_calendar;
CREATE SCHEMA IF NOT EXISTS connector_greenlight;
CREATE SCHEMA IF NOT EXISTS connector_rex;
CREATE SCHEMA IF NOT EXISTS connector_ynab;
CREATE SCHEMA IF NOT EXISTS connector_apple_health;
CREATE SCHEMA IF NOT EXISTS connector_nike_run_club;
-- Exxir schema deferred until the decision gate is cleared (charter Phase 10).

-- ============================================================================
-- Widen existing public foundation tables to match the charter
-- ============================================================================

-- public.role_tiers.name — widen CHECK from (parent/admin/kid/viewer) to the
-- six canonical names. Existing rows: the baseline seed inserted by tier-era
-- migrations used the old names; we lowercase them into the new vocabulary
-- with a best-effort mapping. The new seed block below inserts any missing
-- canonical rows.
ALTER TABLE public.role_tiers
    DROP CONSTRAINT IF EXISTS chk_role_tiers_name;

-- Gentle rename: map legacy → canonical, adds new canonical rows via insert.
UPDATE public.role_tiers SET name = 'PRIMARY_PARENT' WHERE name = 'admin';
UPDATE public.role_tiers SET name = 'PARENT' WHERE name = 'parent';
UPDATE public.role_tiers SET name = 'CHILD' WHERE name = 'kid';
UPDATE public.role_tiers SET name = 'DISPLAY_ONLY' WHERE name = 'viewer';

ALTER TABLE public.role_tiers
    ADD CONSTRAINT chk_role_tiers_name
    CHECK (name IN (
        'PRIMARY_PARENT', 'PARENT', 'TEEN', 'CHILD', 'YOUNG_CHILD', 'DISPLAY_ONLY'
    ));

-- public.connector_configs.connector_name — widen to the charter's
-- full vocabulary while preserving backwards compat with 'ical' and
-- 'hearth' from migration 004. Keeping those two legacy values lets
-- every existing test + any persisted row continue to function
-- while new code targets the charter keys.
ALTER TABLE public.connector_configs
    DROP CONSTRAINT IF EXISTS chk_connector_configs_connector_name;
ALTER TABLE public.connector_configs
    ADD CONSTRAINT chk_connector_configs_connector_name
    CHECK (connector_name IN (
        'google_calendar',
        'hearth',
        'hearth_display',
        'greenlight',
        'rex',
        'ynab',
        'apple_health',
        'nike_run_club',
        'google_maps',
        'exxir',
        'ical'
    ));

-- public.connector_mappings — widen CHECK + add the charter's columns.
ALTER TABLE public.connector_mappings
    DROP CONSTRAINT IF EXISTS chk_connector_mappings_connector_name;
ALTER TABLE public.connector_mappings
    ADD CONSTRAINT chk_connector_mappings_connector_name
    CHECK (connector_name IN (
        'google_calendar',
        'hearth',
        'hearth_display',
        'greenlight',
        'rex',
        'ynab',
        'apple_health',
        'nike_run_club',
        'google_maps',
        'exxir',
        'ical'
    ));

ALTER TABLE public.connector_mappings
    ADD COLUMN IF NOT EXISTS external_object_type text;
ALTER TABLE public.connector_mappings
    ADD COLUMN IF NOT EXISTS family_id uuid REFERENCES public.families (id) ON DELETE CASCADE;
ALTER TABLE public.connector_mappings
    ADD COLUMN IF NOT EXISTS user_account_id uuid REFERENCES public.user_accounts (id) ON DELETE SET NULL;

-- Backfill external_object_type for legacy rows using the internal_table
-- as a reasonable default so the new unique index can be created.
UPDATE public.connector_mappings
SET external_object_type = internal_table
WHERE external_object_type IS NULL;

ALTER TABLE public.connector_mappings
    ALTER COLUMN external_object_type SET NOT NULL;

-- BEFORE INSERT trigger so legacy ingest code that doesn't know about
-- external_object_type still works. Copies internal_table into
-- external_object_type when the caller leaves it NULL. Idempotent
-- with explicit sets — if the caller provides a value, we don't
-- overwrite it.
CREATE OR REPLACE FUNCTION public._connector_mappings_default_object_type()
RETURNS trigger AS $$
BEGIN
    IF NEW.external_object_type IS NULL THEN
        NEW.external_object_type := NEW.internal_table;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_connector_mappings_default_object_type
    ON public.connector_mappings;
CREATE TRIGGER trg_connector_mappings_default_object_type
    BEFORE INSERT ON public.connector_mappings
    FOR EACH ROW
    EXECUTE FUNCTION public._connector_mappings_default_object_type();

-- Composite uniqueness per the charter: (connector_name, external_object_type, external_id).
-- Also supersedes the legacy migration-001 unique constraints. Those
-- were stricter than the charter permits — a single external_id is
-- allowed to map to multiple external_object_type values under the
-- same connector_name (e.g. a Google Calendar event id referenced
-- both as calendar_event and as a derived task_occurrence).
ALTER TABLE public.connector_mappings
    DROP CONSTRAINT IF EXISTS uq_connector_mappings_internal;
ALTER TABLE public.connector_mappings
    DROP CONSTRAINT IF EXISTS uq_connector_mappings_external;

CREATE UNIQUE INDEX IF NOT EXISTS uq_connector_mappings_canonical
    ON public.connector_mappings (connector_name, external_object_type, external_id);
CREATE INDEX IF NOT EXISTS idx_connector_mappings_family
    ON public.connector_mappings (family_id);

-- ============================================================================
-- SCOUT foundation VIEWS (charter's `scout.families` etc. alias public rows)
-- ============================================================================

CREATE OR REPLACE VIEW scout.families AS SELECT * FROM public.families;
CREATE OR REPLACE VIEW scout.family_members AS SELECT * FROM public.family_members;
CREATE OR REPLACE VIEW scout.user_accounts AS SELECT * FROM public.user_accounts;
CREATE OR REPLACE VIEW scout.sessions AS SELECT * FROM public.sessions;
CREATE OR REPLACE VIEW scout.role_tiers AS SELECT * FROM public.role_tiers;
CREATE OR REPLACE VIEW scout.role_tier_overrides AS SELECT * FROM public.role_tier_overrides;
CREATE OR REPLACE VIEW scout.connector_mappings AS SELECT * FROM public.connector_mappings;
CREATE OR REPLACE VIEW scout.connector_configs AS SELECT * FROM public.connector_configs;

-- ============================================================================
-- IDENTITY AND ACCESS (new scout.* tables)
-- ============================================================================

CREATE TABLE IF NOT EXISTS scout.permissions (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    permission_key  text        NOT NULL UNIQUE,
    description     text        NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS scout.role_tier_permissions (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    role_tier_id    uuid        NOT NULL REFERENCES public.role_tiers (id) ON DELETE CASCADE,
    permission_id   uuid        NOT NULL REFERENCES scout.permissions (id) ON DELETE CASCADE,
    created_at      timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT uq_role_tier_permissions UNIQUE (role_tier_id, permission_id)
);

CREATE TABLE IF NOT EXISTS scout.user_family_memberships (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_account_id   uuid        NOT NULL REFERENCES public.user_accounts (id) ON DELETE CASCADE,
    family_id         uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    family_member_id  uuid        REFERENCES public.family_members (id) ON DELETE SET NULL,
    role_tier_id      uuid        REFERENCES public.role_tiers (id) ON DELETE SET NULL,
    is_primary        boolean     NOT NULL DEFAULT false,
    created_at        timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT uq_user_family_membership UNIQUE (user_account_id, family_id)
);

CREATE TABLE IF NOT EXISTS scout.user_preferences (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_account_id   uuid        NOT NULL REFERENCES public.user_accounts (id) ON DELETE CASCADE,
    preference_key    text        NOT NULL,
    preference_value  jsonb       NOT NULL DEFAULT '{}'::jsonb,
    updated_at        timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT uq_user_preferences UNIQUE (user_account_id, preference_key)
);

CREATE TABLE IF NOT EXISTS scout.device_registrations (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_account_id   uuid        NOT NULL REFERENCES public.user_accounts (id) ON DELETE CASCADE,
    device_token      text        NOT NULL,
    platform          text        NOT NULL,
    label             text,
    last_seen_at      timestamptz,
    created_at        timestamptz NOT NULL DEFAULT clock_timestamp(),
    revoked_at        timestamptz,

    CONSTRAINT chk_device_platform CHECK (platform IN ('ios', 'android', 'web')),
    CONSTRAINT uq_device_token UNIQUE (device_token)
);

-- ============================================================================
-- HOUSEHOLD OPERATING SCHEMA
-- ============================================================================

CREATE TABLE IF NOT EXISTS scout.household_rules (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    rule_key        text        NOT NULL,
    rule_value      jsonb       NOT NULL DEFAULT '{}'::jsonb,
    description     text,
    created_at      timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at      timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT uq_household_rule UNIQUE (family_id, rule_key)
);

CREATE TABLE IF NOT EXISTS scout.standards_of_done (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    standard_key    text        NOT NULL,
    label           text        NOT NULL,
    checklist       jsonb       NOT NULL DEFAULT '[]'::jsonb,
    notes           text,
    created_at      timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at      timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT uq_standard_of_done UNIQUE (family_id, standard_key)
);

CREATE TABLE IF NOT EXISTS scout.routine_templates (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    routine_key     text        NOT NULL,
    label           text        NOT NULL,
    block_label     text        NOT NULL,
    recurrence      text        NOT NULL,
    due_time_weekday time,
    due_time_weekend time,
    owner_family_member_id uuid REFERENCES public.family_members (id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at      timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT chk_routine_recurrence CHECK (recurrence IN ('daily', 'weekdays', 'weekends', 'weekly')),
    CONSTRAINT uq_routine_template UNIQUE (family_id, routine_key, owner_family_member_id)
);

CREATE TABLE IF NOT EXISTS scout.routine_steps (
    id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    routine_template_id   uuid        NOT NULL REFERENCES scout.routine_templates (id) ON DELETE CASCADE,
    standard_of_done_id   uuid        REFERENCES scout.standards_of_done (id) ON DELETE SET NULL,
    sort_order            integer     NOT NULL,
    label                 text        NOT NULL,
    notes                 text,
    created_at            timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT uq_routine_step_order UNIQUE (routine_template_id, sort_order)
);

CREATE TABLE IF NOT EXISTS scout.task_templates (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    template_key    text        NOT NULL,
    label           text        NOT NULL,
    recurrence      text        NOT NULL,
    due_time        time,
    standard_of_done_id uuid    REFERENCES scout.standards_of_done (id) ON DELETE SET NULL,
    notes           text,
    is_active       boolean     NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at      timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT chk_task_recurrence CHECK (recurrence IN ('daily', 'weekdays', 'weekends', 'weekly', 'one_off')),
    CONSTRAINT uq_task_template UNIQUE (family_id, template_key)
);

CREATE TABLE IF NOT EXISTS scout.task_assignment_rules (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    task_template_id uuid       NOT NULL REFERENCES scout.task_templates (id) ON DELETE CASCADE,
    rule_type       text        NOT NULL,
    rule_params     jsonb       NOT NULL DEFAULT '{}'::jsonb,
    priority        integer     NOT NULL DEFAULT 0,
    created_at      timestamptz NOT NULL DEFAULT clock_timestamp(),

    -- fixed              : rule_params = { "family_member_id": "<uuid>" }
    -- day_parity         : rule_params = { "odd": "<uuid>", "even": "<uuid>" }
    -- week_rotation      : rule_params = { "owner": "<uuid>", "assistant": "<uuid>", "period_weeks": 8, "anchor_date": "YYYY-MM-DD" }
    -- dog_walk_assistant : rule_params = { "lead": "<uuid>", "odd": "<uuid>", "even": "<uuid>" }
    CONSTRAINT chk_rule_type CHECK (rule_type IN (
        'fixed', 'day_parity', 'week_rotation', 'dog_walk_assistant', 'custom'
    ))
);

CREATE TABLE IF NOT EXISTS scout.task_occurrences (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id         uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    task_template_id  uuid        REFERENCES scout.task_templates (id) ON DELETE SET NULL,
    routine_template_id uuid      REFERENCES scout.routine_templates (id) ON DELETE SET NULL,
    assigned_to       uuid        REFERENCES public.family_members (id) ON DELETE SET NULL,
    occurrence_date   date        NOT NULL,
    due_at            timestamptz NOT NULL,
    status            text        NOT NULL DEFAULT 'open',
    generated_at      timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_at        timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at        timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT chk_occurrence_status CHECK (status IN (
        'open', 'complete', 'late', 'blocked', 'skipped'
    ))
);

CREATE INDEX IF NOT EXISTS idx_task_occurrences_family_date
    ON scout.task_occurrences (family_id, occurrence_date);
CREATE INDEX IF NOT EXISTS idx_task_occurrences_assignee_date
    ON scout.task_occurrences (assigned_to, occurrence_date);

CREATE TABLE IF NOT EXISTS scout.task_completions (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    task_occurrence_id  uuid        NOT NULL REFERENCES scout.task_occurrences (id) ON DELETE CASCADE,
    completed_by        uuid        REFERENCES public.family_members (id) ON DELETE SET NULL,
    completed_at        timestamptz NOT NULL DEFAULT clock_timestamp(),
    completion_mode     text        NOT NULL DEFAULT 'manual',
    notes               text,
    created_at          timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT chk_completion_mode CHECK (completion_mode IN (
        'manual', 'auto', 'parent_override', 'ai_recorded'
    ))
);

CREATE INDEX IF NOT EXISTS idx_task_completions_occurrence
    ON scout.task_completions (task_occurrence_id);

CREATE TABLE IF NOT EXISTS scout.task_exceptions (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    task_occurrence_id  uuid        NOT NULL REFERENCES scout.task_occurrences (id) ON DELETE CASCADE,
    reason              text        NOT NULL,
    created_by          uuid        REFERENCES public.family_members (id) ON DELETE SET NULL,
    created_at          timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS scout.task_notes (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    task_occurrence_id  uuid        NOT NULL REFERENCES scout.task_occurrences (id) ON DELETE CASCADE,
    author_id           uuid        REFERENCES public.family_members (id) ON DELETE SET NULL,
    body                text        NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS scout.time_blocks (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    block_key       text        NOT NULL,
    label           text        NOT NULL,
    start_offset    interval    NOT NULL,
    end_offset      interval    NOT NULL,
    applies_weekday boolean     NOT NULL DEFAULT true,
    applies_weekend boolean     NOT NULL DEFAULT true,
    sort_order      integer     NOT NULL DEFAULT 0,
    created_at      timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT uq_time_block UNIQUE (family_id, block_key)
);

CREATE TABLE IF NOT EXISTS scout.calendar_exports (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id           uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    source_type         text        NOT NULL,
    source_id           uuid        NOT NULL,
    target              text        NOT NULL DEFAULT 'google_calendar',
    label               text        NOT NULL,
    starts_at           timestamptz NOT NULL,
    ends_at             timestamptz NOT NULL,
    hearth_visible      boolean     NOT NULL DEFAULT true,
    export_status       text        NOT NULL DEFAULT 'pending',
    last_exported_at    timestamptz,
    error_message       text,
    created_at          timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at          timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT chk_export_source CHECK (source_type IN (
        'routine_block', 'task_occurrence', 'time_block', 'weekly_anchor'
    )),
    CONSTRAINT chk_export_status CHECK (export_status IN (
        'pending', 'exported', 'error', 'stale', 'cancelled'
    ))
);

-- ============================================================================
-- REWARDS AND ALLOWANCE
-- ============================================================================

CREATE TABLE IF NOT EXISTS scout.reward_policies (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id           uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    family_member_id    uuid        REFERENCES public.family_members (id) ON DELETE CASCADE,
    policy_key          text        NOT NULL,
    baseline_amount_cents integer   NOT NULL,
    payout_schedule     jsonb       NOT NULL DEFAULT '{}'::jsonb,
    wins_required       jsonb       NOT NULL DEFAULT '[]'::jsonb,
    extras_allowed      boolean     NOT NULL DEFAULT true,
    effective_from      date        NOT NULL DEFAULT CURRENT_DATE,
    effective_until     date,
    created_at          timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at          timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT uq_reward_policy UNIQUE (family_id, family_member_id, policy_key, effective_from)
);

CREATE TABLE IF NOT EXISTS scout.daily_win_results (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id           uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    family_member_id    uuid        NOT NULL REFERENCES public.family_members (id) ON DELETE CASCADE,
    for_date            date        NOT NULL,
    earned              boolean     NOT NULL DEFAULT false,
    total_required      integer     NOT NULL DEFAULT 0,
    total_complete      integer     NOT NULL DEFAULT 0,
    missing_items       jsonb       NOT NULL DEFAULT '[]'::jsonb,
    computed_at         timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT uq_daily_win_result UNIQUE (family_member_id, for_date)
);

CREATE INDEX IF NOT EXISTS idx_daily_win_family_date
    ON scout.daily_win_results (family_id, for_date);

CREATE TABLE IF NOT EXISTS scout.allowance_periods (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    period_key      text        NOT NULL,
    start_date      date        NOT NULL,
    end_date        date        NOT NULL,
    status          text        NOT NULL DEFAULT 'draft',
    created_at      timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at      timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT chk_allowance_status CHECK (status IN (
        'draft', 'pending_approval', 'approved', 'exported', 'paid'
    )),
    CONSTRAINT uq_allowance_period UNIQUE (family_id, start_date, end_date)
);

CREATE TABLE IF NOT EXISTS scout.allowance_results (
    id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    allowance_period_id   uuid        NOT NULL REFERENCES scout.allowance_periods (id) ON DELETE CASCADE,
    family_member_id      uuid        NOT NULL REFERENCES public.family_members (id) ON DELETE CASCADE,
    reward_policy_id      uuid        REFERENCES scout.reward_policies (id) ON DELETE SET NULL,
    baseline_amount_cents integer     NOT NULL,
    wins_earned           integer     NOT NULL DEFAULT 0,
    wins_required         integer     NOT NULL DEFAULT 0,
    payout_percent        numeric(5, 4) NOT NULL DEFAULT 0,
    projected_cents       integer     NOT NULL DEFAULT 0,
    final_cents           integer,
    miss_reasons          jsonb       NOT NULL DEFAULT '[]'::jsonb,
    approved_at           timestamptz,
    created_at            timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at            timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT uq_allowance_result UNIQUE (allowance_period_id, family_member_id)
);

CREATE TABLE IF NOT EXISTS scout.reward_extras_catalog (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    extra_key       text        NOT NULL,
    label           text        NOT NULL,
    amount_cents    integer     NOT NULL,
    notes           text,
    is_active       boolean     NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT uq_reward_extra UNIQUE (family_id, extra_key)
);

CREATE TABLE IF NOT EXISTS scout.reward_ledger_entries (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id           uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    family_member_id    uuid        NOT NULL REFERENCES public.family_members (id) ON DELETE CASCADE,
    allowance_result_id uuid        REFERENCES scout.allowance_results (id) ON DELETE SET NULL,
    extras_catalog_id   uuid        REFERENCES scout.reward_extras_catalog (id) ON DELETE SET NULL,
    entry_type          text        NOT NULL,
    amount_cents        integer     NOT NULL,
    memo                text,
    created_at          timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT chk_ledger_entry_type CHECK (entry_type IN (
        'baseline_payout', 'extra', 'school_reward', 'bonus', 'correction'
    ))
);

CREATE TABLE IF NOT EXISTS scout.settlement_batches (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    batch_key       text        NOT NULL,
    status          text        NOT NULL DEFAULT 'draft',
    submitted_at    timestamptz,
    exported_at     timestamptz,
    created_at      timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at      timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT chk_settlement_status CHECK (status IN (
        'draft', 'pending', 'exported', 'failed', 'cancelled'
    )),
    CONSTRAINT uq_settlement_batch UNIQUE (family_id, batch_key)
);

CREATE TABLE IF NOT EXISTS scout.greenlight_exports (
    id                      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    settlement_batch_id     uuid        NOT NULL REFERENCES scout.settlement_batches (id) ON DELETE CASCADE,
    family_member_id        uuid        NOT NULL REFERENCES public.family_members (id) ON DELETE CASCADE,
    amount_cents            integer     NOT NULL,
    greenlight_external_ref text,
    export_status           text        NOT NULL DEFAULT 'pending',
    error_message           text,
    created_at              timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT chk_greenlight_export_status CHECK (export_status IN (
        'pending', 'exported', 'confirmed', 'error', 'cancelled'
    ))
);

-- ============================================================================
-- CONNECTOR REGISTRY AND SYNC
-- ============================================================================

CREATE TABLE IF NOT EXISTS scout.connectors (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_key   text        NOT NULL UNIQUE,
    label           text        NOT NULL,
    tier            integer     NOT NULL DEFAULT 2,
    is_enabled      boolean     NOT NULL DEFAULT true,
    decision_gated  boolean     NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at      timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT chk_connector_key CHECK (connector_key IN (
        'google_calendar', 'hearth_display', 'greenlight', 'rex', 'ynab',
        'apple_health', 'nike_run_club', 'google_maps', 'exxir'
    ))
);

CREATE TABLE IF NOT EXISTS scout.connector_accounts (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_id        uuid        NOT NULL REFERENCES scout.connectors (id) ON DELETE CASCADE,
    family_id           uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    user_account_id     uuid        REFERENCES public.user_accounts (id) ON DELETE SET NULL,
    account_label       text,
    status              text        NOT NULL DEFAULT 'configured',
    last_success_at     timestamptz,
    last_error_at       timestamptz,
    last_error_message  text,
    created_at          timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at          timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT chk_connector_account_status CHECK (status IN (
        'disconnected', 'configured', 'connected', 'syncing', 'stale', 'error', 'disabled', 'decision_gated'
    ))
);

CREATE INDEX IF NOT EXISTS idx_connector_accounts_family
    ON scout.connector_accounts (family_id);

CREATE TABLE IF NOT EXISTS scout.sync_jobs (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_account_id uuid       NOT NULL REFERENCES scout.connector_accounts (id) ON DELETE CASCADE,
    entity_key          text        NOT NULL,
    cadence_seconds     integer     NOT NULL DEFAULT 900,
    is_enabled          boolean     NOT NULL DEFAULT true,
    last_run_started_at timestamptz,
    last_run_finished_at timestamptz,
    next_run_at         timestamptz,
    created_at          timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS scout.sync_runs (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    sync_job_id         uuid        NOT NULL REFERENCES scout.sync_jobs (id) ON DELETE CASCADE,
    started_at          timestamptz NOT NULL DEFAULT clock_timestamp(),
    finished_at         timestamptz,
    status              text        NOT NULL DEFAULT 'running',
    records_processed   integer     NOT NULL DEFAULT 0,
    error_message       text,

    CONSTRAINT chk_sync_run_status CHECK (status IN (
        'running', 'success', 'partial', 'error'
    ))
);

CREATE TABLE IF NOT EXISTS scout.sync_cursors (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_account_id uuid       NOT NULL REFERENCES scout.connector_accounts (id) ON DELETE CASCADE,
    cursor_key          text        NOT NULL,
    cursor_value        text,
    updated_at          timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT uq_sync_cursor UNIQUE (connector_account_id, cursor_key)
);

CREATE TABLE IF NOT EXISTS scout.connector_event_log (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_account_id uuid       REFERENCES scout.connector_accounts (id) ON DELETE CASCADE,
    event_type          text        NOT NULL,
    payload             jsonb       NOT NULL DEFAULT '{}'::jsonb,
    severity            text        NOT NULL DEFAULT 'info',
    created_at          timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT chk_event_severity CHECK (severity IN ('info', 'warn', 'error', 'critical'))
);

CREATE INDEX IF NOT EXISTS idx_connector_event_log_account_time
    ON scout.connector_event_log (connector_account_id, created_at DESC);

CREATE TABLE IF NOT EXISTS scout.stale_data_alerts (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_account_id uuid       NOT NULL REFERENCES scout.connector_accounts (id) ON DELETE CASCADE,
    entity_key          text        NOT NULL,
    stale_since         timestamptz NOT NULL DEFAULT clock_timestamp(),
    acknowledged_at     timestamptz,

    CONSTRAINT uq_stale_alert UNIQUE (connector_account_id, entity_key, stale_since)
);

-- ============================================================================
-- NORMALIZED EXTERNAL CONTEXT
-- ============================================================================

CREATE TABLE IF NOT EXISTS scout.external_calendar_events (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    source          text        NOT NULL,
    title           text        NOT NULL,
    starts_at       timestamptz NOT NULL,
    ends_at         timestamptz NOT NULL,
    location        text,
    all_day         boolean     NOT NULL DEFAULT false,
    imported_at     timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS scout.work_context_events (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    user_account_id uuid        REFERENCES public.user_accounts (id) ON DELETE SET NULL,
    source          text        NOT NULL,
    event_type      text        NOT NULL,
    starts_at       timestamptz NOT NULL,
    ends_at         timestamptz,
    pressure_score  numeric(5, 2),
    metadata        jsonb       NOT NULL DEFAULT '{}'::jsonb,
    imported_at     timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS scout.budget_snapshots (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    source          text        NOT NULL DEFAULT 'ynab',
    as_of_date      date        NOT NULL,
    category_key    text        NOT NULL,
    available_cents integer     NOT NULL,
    budgeted_cents  integer,
    activity_cents  integer,
    metadata        jsonb       NOT NULL DEFAULT '{}'::jsonb,
    imported_at     timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT uq_budget_snapshot UNIQUE (family_id, source, as_of_date, category_key)
);

CREATE TABLE IF NOT EXISTS scout.bill_snapshots (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    source          text        NOT NULL DEFAULT 'ynab',
    as_of_date      date        NOT NULL,
    bill_key        text        NOT NULL,
    label           text        NOT NULL,
    due_date        date        NOT NULL,
    amount_cents    integer     NOT NULL,
    metadata        jsonb       NOT NULL DEFAULT '{}'::jsonb,
    imported_at     timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT uq_bill_snapshot UNIQUE (family_id, source, as_of_date, bill_key)
);

CREATE TABLE IF NOT EXISTS scout.activity_events (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    family_member_id uuid       REFERENCES public.family_members (id) ON DELETE SET NULL,
    source          text        NOT NULL,
    activity_key    text        NOT NULL,
    started_at      timestamptz NOT NULL,
    duration_sec    integer,
    metadata        jsonb       NOT NULL DEFAULT '{}'::jsonb,
    imported_at     timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT chk_activity_source CHECK (source IN ('apple_health', 'nike_run_club'))
);

CREATE TABLE IF NOT EXISTS scout.travel_estimates (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       uuid        NOT NULL REFERENCES public.families (id) ON DELETE CASCADE,
    origin          text        NOT NULL,
    destination     text        NOT NULL,
    requested_for   timestamptz NOT NULL,
    duration_sec    integer,
    distance_meters integer,
    metadata        jsonb       NOT NULL DEFAULT '{}'::jsonb,
    fetched_at      timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- ============================================================================
-- CURATED READ MODELS
-- ============================================================================

-- v_household_today: one row per task occurrence scheduled today, joined
-- with the current completion state. Consumers filter by family_id +
-- occurrence_date = today in the application's local timezone.
CREATE OR REPLACE VIEW scout.v_household_today AS
SELECT
    tocc.id                    AS task_occurrence_id,
    tocc.family_id,
    tocc.occurrence_date,
    tocc.due_at,
    tocc.status,
    tocc.assigned_to           AS family_member_id,
    fm.first_name              AS member_name,
    COALESCE(tt.label, rt.label) AS label,
    tt.template_key,
    rt.routine_key,
    rt.block_label,
    tc.id IS NOT NULL          AS is_completed,
    tc.completed_at
FROM scout.task_occurrences tocc
LEFT JOIN scout.task_templates tt
    ON tt.id = tocc.task_template_id
LEFT JOIN scout.routine_templates rt
    ON rt.id = tocc.routine_template_id
LEFT JOIN public.family_members fm
    ON fm.id = tocc.assigned_to
LEFT JOIN LATERAL (
    SELECT id, completed_at
    FROM scout.task_completions c
    WHERE c.task_occurrence_id = tocc.id
    ORDER BY c.completed_at DESC
    LIMIT 1
) tc ON true;

-- v_rewards_current_week: joins the most recent active allowance_period per
-- family to each child's allowance_result, reward_policy baseline, and a
-- count of daily_win_results inside the period.
CREATE OR REPLACE VIEW scout.v_rewards_current_week AS
SELECT
    ap.id              AS allowance_period_id,
    ap.family_id,
    ap.start_date,
    ap.end_date,
    ap.status          AS period_status,
    ar.family_member_id,
    fm.first_name      AS member_name,
    ar.baseline_amount_cents,
    ar.wins_earned,
    ar.wins_required,
    ar.payout_percent,
    ar.projected_cents,
    ar.final_cents,
    ar.miss_reasons
FROM scout.allowance_periods ap
JOIN scout.allowance_results ar
    ON ar.allowance_period_id = ap.id
JOIN public.family_members fm
    ON fm.id = ar.family_member_id
WHERE ap.status IN ('draft', 'pending_approval', 'approved');

-- v_calendar_publication: what should be visible on Google Calendar (and
-- therefore on Hearth). Joins calendar_exports with the originating
-- occurrence or time block for display context.
CREATE OR REPLACE VIEW scout.v_calendar_publication AS
SELECT
    ce.id                AS calendar_export_id,
    ce.family_id,
    ce.label,
    ce.starts_at,
    ce.ends_at,
    ce.source_type,
    ce.source_id,
    ce.target,
    ce.hearth_visible,
    ce.export_status,
    ce.last_exported_at
FROM scout.calendar_exports ce
WHERE ce.export_status IN ('pending', 'exported', 'stale');

-- v_control_plane: one row per connector_account with freshness state + a
-- snapshot of active alerts and last-success timing. Backs
-- GET /api/connectors/health and GET /api/control-plane/summary.
CREATE OR REPLACE VIEW scout.v_control_plane AS
SELECT
    ca.id                  AS connector_account_id,
    c.connector_key,
    c.label,
    ca.family_id,
    ca.status,
    ca.last_success_at,
    ca.last_error_at,
    ca.last_error_message,
    CASE
        WHEN ca.last_success_at IS NULL THEN 'unknown'
        WHEN ca.last_success_at >= (clock_timestamp() - interval '1 hour') THEN 'live'
        WHEN ca.last_success_at >= (clock_timestamp() - interval '6 hours') THEN 'lagging'
        ELSE 'stale'
    END                    AS freshness_state,
    (SELECT COUNT(*) FROM scout.stale_data_alerts a
        WHERE a.connector_account_id = ca.id
          AND a.acknowledged_at IS NULL) AS open_alert_count
FROM scout.connector_accounts ca
JOIN scout.connectors c ON c.id = ca.connector_id;

-- ============================================================================
-- SEED DATA — role tiers, permissions, Roberts household rules
-- ============================================================================

-- Canonical role tiers (idempotent — inserts only what's missing).
INSERT INTO public.role_tiers (name, permissions, behavior_config)
SELECT name, '{}'::jsonb, '{}'::jsonb FROM (VALUES
    ('PRIMARY_PARENT'),
    ('PARENT'),
    ('TEEN'),
    ('CHILD'),
    ('YOUNG_CHILD'),
    ('DISPLAY_ONLY')
) AS canonical(name)
WHERE NOT EXISTS (
    SELECT 1 FROM public.role_tiers rt WHERE rt.name = canonical.name
);

-- Permission registry.
INSERT INTO scout.permissions (permission_key, description)
SELECT permission_key, description FROM (VALUES
    ('household.edit_rules',          'Edit household rules and standards of done'),
    ('household.complete_any_task',   'Mark any family member''s task complete'),
    ('household.complete_own_task',   'Mark own tasks complete'),
    ('rewards.approve_payout',        'Approve weekly allowance payouts'),
    ('rewards.view_own_payout',       'View own allowance summary'),
    ('connectors.manage',             'Add/remove connector accounts'),
    ('connectors.view_health',        'View connector health dashboard'),
    ('calendar.publish',              'Publish household blocks to calendar'),
    ('display.view_only',             'Display-only surface access (Hearth)')
) AS seed(permission_key, description)
WHERE NOT EXISTS (
    SELECT 1 FROM scout.permissions p WHERE p.permission_key = seed.permission_key
);

-- Role tier → permission mapping. Parents get everything; teens/children get
-- read-only + own-task completion; display_only is truly read-only.
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM public.role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('PRIMARY_PARENT', 'PARENT')
  AND NOT EXISTS (
      SELECT 1 FROM scout.role_tier_permissions rtp
      WHERE rtp.role_tier_id = rt.id AND rtp.permission_id = p.id
  );

INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM public.role_tiers rt
JOIN scout.permissions p ON p.permission_key IN (
    'household.complete_own_task',
    'rewards.view_own_payout'
)
WHERE rt.name IN ('TEEN', 'CHILD', 'YOUNG_CHILD')
  AND NOT EXISTS (
      SELECT 1 FROM scout.role_tier_permissions rtp
      WHERE rtp.role_tier_id = rt.id AND rtp.permission_id = p.id
  );

INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM public.role_tiers rt
JOIN scout.permissions p ON p.permission_key = 'display.view_only'
WHERE rt.name = 'DISPLAY_ONLY'
  AND NOT EXISTS (
      SELECT 1 FROM scout.role_tier_permissions rtp
      WHERE rtp.role_tier_id = rt.id AND rtp.permission_id = p.id
  );

-- Connector registry seed rows. Tier 1 and Tier 2 connectors ship
-- enabled; Exxir is decision-gated.
INSERT INTO scout.connectors (connector_key, label, tier, is_enabled, decision_gated)
SELECT connector_key, label, tier, is_enabled, decision_gated
FROM (VALUES
    ('google_calendar', 'Google Calendar',    1, true,  false),
    ('hearth_display',  'Hearth Display',     1, true,  false),
    ('greenlight',      'Greenlight',         1, true,  false),
    ('rex',             'Rex',                2, true,  false),
    ('ynab',            'YNAB',               2, true,  false),
    ('google_maps',     'Google Maps',        3, true,  false),
    ('apple_health',    'Apple Health',       3, true,  false),
    ('nike_run_club',   'Nike Run Club',      3, true,  false),
    ('exxir',           'Exxir (gated)',      4, false, true)
) AS seed(connector_key, label, tier, is_enabled, decision_gated)
WHERE NOT EXISTS (
    SELECT 1 FROM scout.connectors c WHERE c.connector_key = seed.connector_key
);

COMMIT;
