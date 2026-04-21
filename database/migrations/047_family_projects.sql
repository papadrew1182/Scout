-- Sprint Expansion Phase 3: Family projects engine
-- Six new tables under scout.* plus one additive column on personal_tasks.
-- Engine only — built-in template content is deferred to Sprint 3B.

-- ============================================================================
-- 1. project_templates — reusable blueprints (family-local only in Phase 3;
--    is_builtin/nullable family_id reserved for a later global library).
-- ============================================================================
CREATE TABLE IF NOT EXISTS scout.project_templates (
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id                       UUID REFERENCES public.families(id) ON DELETE CASCADE,
    name                            TEXT NOT NULL,
    description                     TEXT,
    category                        TEXT NOT NULL
        CHECK (category IN ('birthday','holiday','trip','school_event','home_project','weekend_reset','custom')),
    estimated_duration_days         INTEGER,
    default_lead_time_days          INTEGER NOT NULL DEFAULT 0,
    default_budget_cents            INTEGER,
    created_by_family_member_id     UUID REFERENCES public.family_members(id) ON DELETE SET NULL,
    is_active                       BOOLEAN NOT NULL DEFAULT true,
    is_builtin                      BOOLEAN NOT NULL DEFAULT false,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_project_templates_family
    ON scout.project_templates(family_id)
    WHERE family_id IS NOT NULL;

-- ============================================================================
-- 2. project_template_tasks — ordered tasks per template with relative offsets
-- ============================================================================
CREATE TABLE IF NOT EXISTS scout.project_template_tasks (
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_template_id             UUID NOT NULL REFERENCES scout.project_templates(id) ON DELETE CASCADE,
    title                           TEXT NOT NULL,
    description                     TEXT,
    order_index                     INTEGER NOT NULL DEFAULT 0,
    relative_day_offset             INTEGER NOT NULL DEFAULT 0,
    default_owner_role              TEXT,
    estimated_duration_minutes      INTEGER,
    has_budget_impact               BOOLEAN NOT NULL DEFAULT false,
    has_grocery_impact              BOOLEAN NOT NULL DEFAULT false,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_project_template_tasks_template
    ON scout.project_template_tasks(project_template_id, order_index);

-- ============================================================================
-- 3. projects — concrete instances
-- ============================================================================
CREATE TABLE IF NOT EXISTS scout.projects (
    id                                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id                           UUID NOT NULL REFERENCES public.families(id) ON DELETE CASCADE,
    project_template_id                 UUID REFERENCES scout.project_templates(id) ON DELETE SET NULL,
    name                                TEXT NOT NULL,
    description                         TEXT,
    category                            TEXT NOT NULL
        CHECK (category IN ('birthday','holiday','trip','school_event','home_project','weekend_reset','custom')),
    status                              TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','active','paused','complete','cancelled')),
    start_date                          DATE NOT NULL,
    target_end_date                     DATE,
    actual_end_date                     DATE,
    budget_cents                        INTEGER,
    actual_spent_cents                  INTEGER,
    primary_owner_family_member_id      UUID REFERENCES public.family_members(id) ON DELETE SET NULL,
    created_by_family_member_id         UUID NOT NULL REFERENCES public.family_members(id) ON DELETE CASCADE,
    created_at                          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_projects_family_active
    ON scout.projects(family_id, status)
    WHERE status IN ('active','draft');

-- ============================================================================
-- 4. project_tasks — the primary work unit. Source of truth; personal_tasks
--    copies are convenience only.
-- ============================================================================
CREATE TABLE IF NOT EXISTS scout.project_tasks (
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id                      UUID NOT NULL REFERENCES scout.projects(id) ON DELETE CASCADE,
    title                           TEXT NOT NULL,
    description                     TEXT,
    status                          TEXT NOT NULL DEFAULT 'todo'
        CHECK (status IN ('todo','in_progress','blocked','done','skipped')),
    owner_family_member_id          UUID REFERENCES public.family_members(id) ON DELETE SET NULL,
    due_date                        DATE,
    estimated_duration_minutes      INTEGER,
    actual_duration_minutes         INTEGER,
    budget_cents                    INTEGER,
    spent_cents                     INTEGER,
    depends_on_project_task_id      UUID REFERENCES scout.project_tasks(id) ON DELETE SET NULL,
    notes                           TEXT,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_project_tasks_project_status
    ON scout.project_tasks(project_id, status);
CREATE INDEX IF NOT EXISTS idx_project_tasks_owner_due
    ON scout.project_tasks(owner_family_member_id, due_date)
    WHERE owner_family_member_id IS NOT NULL;

-- ============================================================================
-- 5. project_milestones — named checkpoints
-- ============================================================================
CREATE TABLE IF NOT EXISTS scout.project_milestones (
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id                      UUID NOT NULL REFERENCES scout.projects(id) ON DELETE CASCADE,
    name                            TEXT NOT NULL,
    target_date                     DATE NOT NULL,
    is_complete                     BOOLEAN NOT NULL DEFAULT false,
    completed_at                    TIMESTAMPTZ,
    order_index                     INTEGER NOT NULL DEFAULT 0,
    notes                           TEXT,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_project_milestones_project_target
    ON scout.project_milestones(project_id, target_date);

-- ============================================================================
-- 6. project_budget_entries — line-item spend ledger
-- ============================================================================
CREATE TABLE IF NOT EXISTS scout.project_budget_entries (
    id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id                      UUID NOT NULL REFERENCES scout.projects(id) ON DELETE CASCADE,
    project_task_id                 UUID REFERENCES scout.project_tasks(id) ON DELETE SET NULL,
    amount_cents                    INTEGER NOT NULL,
    kind                            TEXT NOT NULL
        CHECK (kind IN ('estimate','expense','refund')),
    vendor                          TEXT,
    notes                           TEXT,
    recorded_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
    recorded_by_family_member_id    UUID NOT NULL REFERENCES public.family_members(id) ON DELETE CASCADE,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_project_budget_entries_project
    ON scout.project_budget_entries(project_id, recorded_at DESC);

-- ============================================================================
-- 7. personal_tasks → project_tasks linkage (one-way, promotion-only)
-- ============================================================================
ALTER TABLE public.personal_tasks
    ADD COLUMN IF NOT EXISTS source_project_task_id UUID
        REFERENCES scout.project_tasks(id) ON DELETE SET NULL;

-- Unique where not null: a given project task can be promoted at most once.
CREATE UNIQUE INDEX IF NOT EXISTS uq_personal_tasks_source_project_task
    ON public.personal_tasks(source_project_task_id)
    WHERE source_project_task_id IS NOT NULL;

-- ============================================================================
-- 8. Permission keys + tier grants
-- ============================================================================
-- Post-migration-034 canonical tier names are UPPERCASE. Migration 024's
-- lowercase names (admin/parent_peer/teen/child/kid) were deleted in 034 and
-- every override row re-pointed at the UPPERCASE row. The sprint spec uses
-- the lowercase spellings as shorthand but the DB stores UPPERCASE.

INSERT INTO scout.permissions (permission_key, description) VALUES
    ('projects.create',                 'Create a new family project'),
    ('projects.manage_own',             'Edit projects you own (primary_owner_family_member_id)'),
    ('projects.manage_any',             'Edit any project in the family'),
    ('projects.view',                   'View projects and project tasks'),
    ('project_tasks.update_assigned',   'Update status and notes for project tasks assigned to you'),
    ('project_templates.manage',        'Create, edit, and remove family project templates'),
    ('project_templates.view',          'View family project templates')
ON CONFLICT (permission_key) DO NOTHING;

-- projects.create, project_tasks.update_assigned → PRIMARY_PARENT + PARENT + TEEN.
-- (CHILD and YOUNG_CHILD can still complete tasks assigned to them via
-- project_tasks.update_assigned.)
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM public.role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('PRIMARY_PARENT','PARENT','TEEN')
  AND p.permission_key = 'projects.create'
ON CONFLICT DO NOTHING;

-- projects.manage_own → every tier that can create OR be assigned as owner.
-- Phase 3 keeps this broad so teens owning a project can edit it.
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM public.role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('PRIMARY_PARENT','PARENT','TEEN','CHILD','YOUNG_CHILD')
  AND p.permission_key = 'projects.manage_own'
ON CONFLICT DO NOTHING;

-- projects.manage_any, project_templates.manage → admin / parent_peer only.
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM public.role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('PRIMARY_PARENT','PARENT')
  AND p.permission_key IN ('projects.manage_any','project_templates.manage')
ON CONFLICT DO NOTHING;

-- projects.view, project_templates.view, project_tasks.update_assigned → all tiers.
INSERT INTO scout.role_tier_permissions (role_tier_id, permission_id)
SELECT rt.id, p.id
FROM public.role_tiers rt
CROSS JOIN scout.permissions p
WHERE rt.name IN ('PRIMARY_PARENT','PARENT','TEEN','CHILD','YOUNG_CHILD')
  AND p.permission_key IN ('projects.view','project_templates.view','project_tasks.update_assigned')
ON CONFLICT DO NOTHING;
