-- Migration 051: Sprint 05 Phase 4 - Admin rule engine schema for proactive
-- nudges. Introduces scout.nudge_rules, the per-family table that stores
-- custom nudge rule definitions authored via the Parent admin surface.
--
-- Two deliverables per Sprint 05 revised plan Section 7 Phase 4:
--   1. scout.nudge_rules: parent-authored custom nudge rule definitions.
--      v1 ships source_kind='sql_template' only; 'predicate' is reserved
--      for a future release.
--   2. Permission nudges.configure for PARENT + PRIMARY_PARENT so only
--      parent tiers can create, edit, and delete custom rules.
--
-- canonical_sql is populated by the Task 3 whitelist validator on CRUD
-- write. Storing the re-serialized canonical form means the scheduler
-- never re-validates at scan time.
--
-- UNIQUE (family_id, name) keeps display names unique within a family.
-- The partial index on (family_id, is_active) WHERE is_active = true
-- matches the scheduler's scan-only-active-rules query shape.
--
-- trigger_kind is constrained to ('custom_rule') for v1 and must match
-- the scout.nudge_dispatch_items.trigger_kind CHECK list from migration
-- 049 so Task 5 dispatch inserts do not fail the child-row constraint.
--
-- DISPLAY_ONLY excluded by existing repo convention.

BEGIN;

-- ============================================================================
-- scout.nudge_rules (parent-authored custom nudge rule definitions)
-- ============================================================================

CREATE TABLE IF NOT EXISTS scout.nudge_rules (
    id                              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id                       uuid        NOT NULL
                                                REFERENCES public.families (id) ON DELETE CASCADE,
    name                            text        NOT NULL,
    description                     text,
    is_active                       boolean     NOT NULL DEFAULT true,
    source_kind                     text        NOT NULL,
    template_sql                    text,
    canonical_sql                   text,
    template_params                 jsonb       NOT NULL DEFAULT '{}'::jsonb,
    trigger_kind                    text        NOT NULL DEFAULT 'custom_rule',
    default_lead_time_minutes       integer     NOT NULL DEFAULT 0,
    severity                        text        NOT NULL DEFAULT 'normal',
    created_by_family_member_id     uuid        REFERENCES public.family_members (id) ON DELETE SET NULL,
    created_at                      timestamptz NOT NULL DEFAULT now(),
    updated_at                      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT uq_nudge_rules_family_name
        UNIQUE (family_id, name),
    CONSTRAINT chk_nudge_rules_source_kind
        CHECK (source_kind IN ('sql_template', 'predicate')),
    CONSTRAINT chk_nudge_rules_trigger_kind
        CHECK (trigger_kind IN ('custom_rule')),
    CONSTRAINT chk_nudge_rules_severity
        CHECK (severity IN ('low', 'normal', 'high')),
    CONSTRAINT chk_nudge_rules_lead_time
        CHECK (default_lead_time_minutes >= 0 AND default_lead_time_minutes <= 1440),
    CONSTRAINT chk_nudge_rules_sql_template_has_sql
        CHECK (source_kind <> 'sql_template' OR template_sql IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_nudge_rules_family_active
    ON scout.nudge_rules (family_id, is_active)
    WHERE is_active = true;

DROP TRIGGER IF EXISTS trg_nudge_rules_updated_at ON scout.nudge_rules;
CREATE TRIGGER trg_nudge_rules_updated_at
    BEFORE UPDATE ON scout.nudge_rules
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================================
-- Permission registration: nudges.configure
-- ============================================================================

INSERT INTO scout.permissions (permission_key, description) VALUES
    ('nudges.configure',
     'Create, edit, and delete custom Scout nudge rules')
ON CONFLICT (permission_key) DO NOTHING;

-- nudges.configure: PARENT + PRIMARY_PARENT only
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM public.role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('PARENT', 'PRIMARY_PARENT')
  AND p.permission_key = 'nudges.configure'
ON CONFLICT DO NOTHING;

COMMIT;
