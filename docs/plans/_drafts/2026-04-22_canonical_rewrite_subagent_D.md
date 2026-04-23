# Slice D plan: identity, permissions, connectors, framework

**Date:** 2026-04-22
**Author:** Subagent D (planning; no code/schema changes)
**Scope:** Foundation slice. Tables listed in the spec under "Your slice".
**Status:** Proposal. Subject to synthesis review.

Slice D owns the authentication and tenant-boundary tables (`families`,
`family_members`, `user_accounts`, `sessions`), the permission registry
(`role_tiers`, `role_tier_overrides`, `scout.role_tier_permissions`,
`scout.permissions`, `scout.user_family_memberships`), the
connector platform (`scout.connectors`, `scout.connector_accounts` and
the shim pair `public.connector_configs` / `public.connector_mappings`),
a small set of active legacy tables that lack canonical homes
(`public.parent_action_items`, `public.purchase_requests`,
`public.scout_scheduled_runs`, `public.member_config`), and the
framework-level migration ledger (`public._scout_migrations`).

Every other slice (A, B, C) FKs at least one Slice D table. The slice's
PR ordering therefore defines the sprint critical path. Section 5
contains the blocking graph.

---

## Section 1. Slice inventory

Row counts are drawn from the 2026-04-22 audit
(`docs/plans/2026-04-22_schema_canonical_audit.md:5, 23-25, 29, 33`).
File:line citations below are from grep runs performed during this
plan's preparation; if a specific line no longer matches, the file
still contains the referenced symbol.

### 1.1 public.families
- **Rows:** 1
- **Model:** `backend/app/models/foundation.py:11` (`Family`)
- **Migration of origin:** `backend/migrations/001_foundation_connectors.sql:28`
- **Route files that reference Family or `families` table:**
  `backend/app/routes/families.py`, `backend/app/routes/auth.py`,
  `backend/app/routes/canonical.py`, `backend/app/routes/admin/permissions.py`,
  `backend/app/routes/admin/config.py`, `backend/app/routes/admin/chores.py`,
  `backend/app/routes/admin/allowance.py`, `backend/app/routes/ai.py`,
  `backend/app/routes/projects.py`, `backend/app/routes/push.py`.
- **Services:** nearly every service under `backend/app/services/`
  imports `Family` or FKs `families.id` indirectly via `family_id`.
- **Views over it:** `scout.families` shim
  (`backend/migrations/022_session2_canonical.sql:183`); `scout.v_household_today`,
  `scout.v_rewards_current_week`, `scout.v_calendar_publication`,
  `scout.v_control_plane` all join rows owned by a `family_id`.
- **Shim view usage:** grep shows no backend code reads from
  `scout.families` (all reads go through ORM against the public table).
  The shim is migration-era scaffolding only.

### 1.2 public.user_accounts
- **Rows:** 5
- **Model:** `backend/app/models/foundation.py:53` (`UserAccount`)
- **Routes:** `backend/app/routes/auth.py` (login, bootstrap, me,
  password, sessions, accounts management). Also referenced in
  `backend/app/routes/canonical.py` for control-plane payloads.
- **Services:** `backend/app/services/auth_service.py` (login/logout,
  session resolution, password change).
- **Shim view:** `scout.user_accounts`
  (`backend/migrations/022_session2_canonical.sql:185`). Not read by code.

### 1.3 public.family_members
- **Rows:** 8
- **Model:** `backend/app/models/foundation.py:26` (`FamilyMember`)
- **Routes:** ~10 files, including `families.py`, `canonical.py`,
  `ai.py`, `projects.py`, `push.py`, `admin/config.py`,
  `admin/chores.py`, `admin/allowance.py`, `admin/permissions.py`,
  `auth.py`.
- **Services:** `auth_service.py`, `permissions.py`,
  `nudges_service.py`, `ai_personality_service.py`, most admin surface
  services. FK'd by almost every scope-bearing table in the schema.
- **Shim view:** `scout.family_members`
  (`backend/migrations/022_session2_canonical.sql:184`).
- **Used by views:** `scout.v_household_today:768-781` (assigned-to
  lookup), `scout.v_rewards_current_week:813-814`. Both shim views,
  when consulted, resolve via `public.family_members` under the hood.

### 1.4 public.sessions (framework auth)
- **Rows:** 172 - every active user's bearer token.
- **Model:** `backend/app/models/foundation.py:71` (`Session`)
- **Service:** `backend/app/services/auth_service.py` (lines 20, 100,
  124-125, 137-138, 209-230 - all session CRUD).
- **Routes:** `backend/app/routes/auth.py` uses `Session` via service
  for login/logout/list/revoke paths. No route touches the table
  outside of this service.
- **Shim view:** `scout.sessions`
  (`backend/migrations/022_session2_canonical.sql:186`). Not read by
  code; would only matter if a future canonical read model needed
  session joins.
- **Cross-boundary risk:** HIGHEST in the entire sprint. 172 live
  tokens translate to 172 active logins. Any migration that renames,
  moves, or truncates this table logs users out.

### 1.5 public.role_tiers
- **Rows:** 6 (PRIMARY_PARENT, PARENT, TEEN, CHILD, YOUNG_CHILD,
  DISPLAY_ONLY - after the `022` widening).
- **Model:** `backend/app/models/access.py:30` (`RoleTier`)
- **Service:** `backend/app/services/permissions.py:39-98`
  (`resolve_effective_permissions`) reads this table then joins
  `scout.role_tier_permissions` → `scout.permissions`.
- **Routes:** `backend/app/routes/admin/permissions.py` references
  `RoleTier`.
- **Shim view:** `scout.role_tiers`
  (`backend/migrations/022_session2_canonical.sql:187`,
  re-created at `024_permissions_and_config.sql:42`). Not read by code.

### 1.6 public.role_tier_overrides
- **Rows:** 7
- **Model:** `backend/app/models/access.py:42` (`RoleTierOverride`)
- **Service:** `backend/app/services/permissions.py:59-66`
  (override lookup is step 1 of the resolver).
- **Routes:** `backend/app/routes/admin/permissions.py` (PATCH
  endpoint for per-member overrides).
- **Shim view:** `scout.role_tier_overrides`
  (`022_session2_canonical.sql:188`, re-created at
  `024_permissions_and_config.sql:87`). Not read by code.

### 1.7 scout.role_tier_permissions (canonical)
- **Rows:** populated by `022_session2_canonical.sql:898-929` seed.
- **Table defined at:** `022_session2_canonical.sql:203`.
- **Service:** read by `permissions.py:79-87` in the SELECT that joins
  `scout.permissions`.
- **No ORM model file** (permissions service uses raw SQL via
  `sqlalchemy.text`). This is a gap worth noting but not load-bearing.
- **Bridge correctness:** confirmed. Audit Section 4 marks
  this pair WELL-BRIDGED.

### 1.8 scout.permissions (canonical, flagged UNCLEAR)
- **Table defined at:** `022_session2_canonical.sql:196`.
- **Seed at:** `022_session2_canonical.sql:880-894`.
- **Verified use:** `permissions.py:79-87` joins this table. This is
  the permission registry consumed by every `require_permission()` call
  in the backend. UNCLEAR label from audit Section 3 is wrong in
  practice - the table is canonical and active. Recommendation:
  reclassify as CANONICAL in a future audit pass.

### 1.9 scout.user_family_memberships (flagged UNCLEAR)
- **Table defined at:** `022_session2_canonical.sql:212`.
- **Only reference in backend code:** a comment in
  `backend/app/routes/canonical.py:62` that says resolution will come
  from this table "once identity write paths are wired." No writes
  today.
- **Recommendation:** keep-and-plan. Not load-bearing yet, but it is
  the designed home for multi-household / teen-with-two-households
  scenarios. Do not consolidate; do not expand in Slice D. Flag for
  Session 4 planning.

### 1.10 public.member_config (ARCHITECTURE.md Layer 1)
- **Rows:** 1.
- **Model:** `backend/app/models/access.py:55` (`MemberConfig`).
- **Service:** `backend/app/services/permissions.py:186-255`
  (get/set/delete helpers).
- **Routes:** `backend/app/routes/admin/config.py` (set/get),
  `backend/app/routes/affirmations.py`,
  `backend/app/services/ai_personality_service.py`,
  `backend/app/services/nudges_service.py`.
- **ARCHITECTURE.md alignment:** `docs/architecture/ARCHITECTURE.md:21`
  calls `member_config` the Layer 1 table and the authoritative home
  for self-scoped member data. The parallel `family_config` was
  retired in migration 035 and replaced by
  `scout.household_rules`
  (`backend/app/services/permissions.py:113`). By symmetry,
  `member_config` should live in `scout` (ARCHITECTURE.md does not
  prescribe schema, only role).
- **Shim view status:** none exists today. If we move to
  `scout.member_config`, we must add a `public.member_config` view
  during the cutover window.

### 1.11 scout.connectors (canonical)
- **Rows:** 9.
- **Table defined at:** `022_session2_canonical.sql:572`. Seed at
  `022_session2_canonical.sql:933-948`.
- **Model:** `backend/app/models/canonical.py` (`Connector`, line 92).
- **Used by:** `backend/services/connectors/registry.py`,
  `backend/services/connectors/sync_service.py`,
  `backend/services/connectors/sync_persistence.py`,
  `backend/app/services/integrations_canonical.py`,
  `backend/app/routes/canonical.py`, and migration 038.

### 1.12 scout.connector_accounts (canonical)
- **Rows:** 6.
- **Table defined at:** `022_session2_canonical.sql:588`.
- **Used by:** `scout.v_control_plane:839-859`; sync_service and
  sync_persistence files (all under `backend/services/connectors/`);
  `integrations_canonical.py`; `app/routes/canonical.py`; migration
  038 (`038_integrations_connections_to_canonical.sql`) rewrites a
  legacy JSONB blob in `scout.household_rules` into rows here.

### 1.13 public.connector_configs (legacy / shim) and public.connector_mappings (legacy / shim)
- **Tables defined at:** `001_foundation_connectors.sql:169` and
  `:229`. Constraints widened at
  `022_session2_canonical.sql:88-178`.
- **Models:** `backend/app/models/connectors.py:11` (`ConnectorConfig`),
  `:29` (`ConnectorMapping`).
- **Routes/services actually writing them:** grep for `ConnectorConfig`
  in `backend/app/services/` returned no matches. The ORM class exists
  but nothing in the current backend code writes to
  `connector_configs`. Writes are happening through the canonical
  `scout.connector_accounts` + `scout.connectors` path instead
  (migration 038 is the migration that moved them).
  `ConnectorMapping` is referenced only at the model layer.
- **Intent in ARCHITECTURE.md / migration 022:** `connector_mappings`
  is the global external-ID bridge
  (`001_foundation_connectors.sql:223-253`) and intentionally
  polymorphic; migration 022 widened the unique constraint
  (`:169-178`) to allow the same external id across multiple
  `external_object_type` values.
- **Shim views in scout:** `scout.connector_configs` and
  `scout.connector_mappings`
  (`022_session2_canonical.sql:189-190`). Not read by code.

### 1.14 public.parent_action_items (ACTIVE, no canonical yet)
- **Rows:** 33.
- **Migration of origin:** `backend/migrations/012_parent_action_items.sql`.
- **Model:** `backend/app/models/action_items.py:11`
  (`ParentActionItem`).
- **Routes writing it:** `backend/app/routes/task_instances.py:10`
  (chore-override creation), `backend/app/routes/dashboard.py:96, 139`
  (list/resolve).
- **Services writing it:** `backend/app/services/grocery_service.py`
  (20, 41, 42, 64-68, 389, 392-395),
  `backend/app/services/dashboard_service.py` (13, 157-160),
  `backend/app/ai/orchestrator.py:351-358` (AI-created items),
  `backend/app/ai/anomalies.py:50, 344-349` (dedupe on pending items).
- **No canonical home yet.** This is the largest missing-canonical gap
  in Slice D.

### 1.15 public.purchase_requests (ACTIVE, no canonical yet)
- **Rows:** 1.
- **Model:** `backend/app/models/grocery.py:36`.
- **Routes:** `backend/app/routes/grocery.py:118-180` (list, create,
  approve, deny).
- **FK'd by:** `grocery_items.purchase_request_id`
  (`grocery.py:26`). Deferred FK - listed as `use_alter=True`.
- **No canonical home yet.**

### 1.16 public.scout_scheduled_runs (ACTIVE, intent unclear)
- **Rows:** 48 (dedupe + audit for scheduler jobs).
- **Model:** `backend/app/models/scheduled.py:13` (`ScheduledRun`).
- **Origin migration:** `backend/migrations/016_tier1_proactive.sql`.
- **Referenced in:** `backend/app/scheduler.py:12, 45, 247, 294, 311,
  429, 438, 593, 771, 801`. The unique index on `(job_name, family_id,
  member_id, run_date)` is used as a mutex.
- **Intent:** framework-level dedupe for AI-triggered scheduled work.
  It is not household content, it is operator state - similar in
  character to `sessions`.

### 1.17 public.scout_mcp_tokens (0 rows, live model)
- **Model:** `backend/app/models/tier5.py:101`.
- **Routes:** `backend/app/routes/mcp_http.py:6`.
- **Origin migration:** `021_tier5.sql`.
- **Status:** live code, no data yet. Treated as "parked feature" -
  safe to leave in public, not load-bearing for any current slice.

### 1.18 public.scout_anomaly_suppressions (0 rows)
- **Model:** `backend/app/models/tier5.py:66`.
- **Status:** similar to 1.17 - parked. Leave alone.

### 1.19 public._scout_migrations (framework, 53 rows)
- **Created inline by:** `backend/migrate.py:24-29`.
- **Read/write by:** `backend/migrate.py` only.
- **Status:** touching this table breaks the migration runner itself.
  Absolute do-not-touch.

### 1.20 Views reading from Slice D
- **Shim views (8):** `scout.families`, `scout.family_members`,
  `scout.user_accounts`, `scout.sessions`, `scout.role_tiers`,
  `scout.role_tier_overrides`, `scout.connector_configs`,
  `scout.connector_mappings`. Grep across `backend/` for `from scout\.`
  and the specific view names shows zero direct reads - the views are
  defined in 022 but never consulted by code. Safe to keep for now
  (zero cost), but we can drop them once consolidation is complete
  (Slice D PR Dn).
- **Purpose-built views:** `scout.v_control_plane`
  (`022_session2_canonical.sql:839`) reads `scout.connector_accounts`
  and `scout.connectors` - both already canonical; no change needed.
  `scout.v_household_today`, `scout.v_rewards_current_week`, and
  `scout.v_calendar_publication` join `public.family_members` directly.
  If Slice D ever consolidates `family_members` into scout, those views
  need updating. Today they are fine - family_members stays put.

---

## Section 2. Per-table recommended action

For each table: action (CONSOLIDATE, KEEP+BRIDGE, DEPRECATE, LEAVE),
brief justification, and whether I am validating or pushing back on
the audit's recommendation.

| Table | Action | Audit | My stance |
|-------|--------|-------|-----------|
| `public.families` | KEEP+BRIDGE | KEEP (foundation) | Validated. 1 row, FK'd by hundreds of columns. Cost of rename is astronomical; benefit is cosmetic. Keep in public, keep the `scout.families` shim view for name-surface continuity. |
| `public.user_accounts` | KEEP+BRIDGE | KEEP | Validated. Same reasoning as `families` and `sessions` - auth foundation. |
| `public.family_members` | KEEP+BRIDGE | KEEP | Validated. Auth + tenancy foundation. Every other scope-bearing table FKs this. Cost/benefit identical to `families`. |
| `public.sessions` | KEEP, DO-NOT-TOUCH | KEEP | Validated + hardened: I recommend we mark this as "no touch" in the PR ordering - **not even a view refresh**. 172 live tokens. Migration risk is not worth it. |
| `public.role_tiers` | KEEP+BRIDGE | KEEP | Validated. The public seed + `scout.role_tier_permissions` registry pair is an intentional well-designed split (ARCHITECTURE.md:29-42). Leave it. |
| `public.role_tier_overrides` | KEEP+BRIDGE | (implicit KEEP) | Audit did not explicitly call this out; the override row is FK'd to `family_members` (cascade delete) and to `role_tiers` (restrict). Must stay with its parents → KEEP in public. |
| `scout.role_tier_permissions` | KEEP CANONICAL | (canonical) | No change. Add an ORM model (currently raw SQL - minor tidy, Sx.6). |
| `scout.permissions` | KEEP CANONICAL (reclassify from UNCLEAR) | UNCLEAR | **PUSH BACK.** This is actively consumed by `permissions.py:83`. Audit's UNCLEAR rating is a miscategorization. Add ORM model, flag future audit correction. |
| `scout.user_family_memberships` | LEAVE (future feature) | UNCLEAR | Validated UNCLEAR → defer. Not consumed by any code path today (`canonical.py:62` comment only). Ship Slice D without relying on this; revisit in Session 4. |
| `public.member_config` | CONSOLIDATE to `scout.member_config` | CONSOLIDATE | Validated. Symmetry with `scout.household_rules` (the Layer 3 half, moved in migration 035). Layer 1 should live in scout too. 1 row; tiny migration. |
| `scout.connectors` | KEEP CANONICAL | (canonical) | No change. |
| `scout.connector_accounts` | KEEP CANONICAL | (canonical) | No change. |
| `public.connector_configs` | DEPRECATE (no active writes) | (shim-backed) | **PUSH BACK to audit** - audit calls this a shim, but it is really a legacy table that no backend writes to. Migration 038 migrated the one legacy use case (`integrations.connections`) into `scout.connector_accounts`. Drop after a one-release parking period. |
| `public.connector_mappings` | KEEP (polymorphic external-ID bridge) | (shim-backed) | Keep. The charter in 022 intentionally widens this as the global external-ID store. Physical home in public is fine; backfill rows if / when Slice A's task_occurrences need mapping. |
| `public.parent_action_items` | CONSOLIDATE to `scout.parent_action_items` | CONSOLIDATE | Validated. 33 live rows. 5 services + 2 routes write it. Largest effort in Slice D. |
| `public.purchase_requests` | CONSOLIDATE to `scout.purchase_requests` | CONSOLIDATE | Validated. 1 row, narrow surface (`grocery.py` only), but FK'd by `grocery_items.purchase_request_id`. Still worth moving for coherence. |
| `public.scout_scheduled_runs` | KEEP in public (framework) | unclear | **Recommend KEEP.** Rationale: operator-state, not household content. Same character as `sessions`. Moving it into scout offers no consumer benefit and creates a scheduler-downtime risk. If we ever need a scout read-model over it, add a view. |
| `public.scout_mcp_tokens` | LEAVE (parked) | (zero-row LEGACY) | No-op. |
| `public.scout_anomaly_suppressions` | LEAVE (parked) | (zero-row LEGACY) | No-op. |
| `public._scout_migrations` | ABSOLUTE DO-NOT-TOUCH | n/a | Framework. |
| 8 shim views in scout | LEAVE now, DROP in Dn | n/a | Zero code reads. Removing them is trivial once Slice D is done; no-harm to leave meanwhile. |

---

## Section 3. Proposed canonical target shape

Only tables marked CONSOLIDATE in Section 2 get a target shape here.

### 3.1 scout.member_config (target)

Columns preserved verbatim from `public.member_config` with one
improvement: rename `key`/`value` to `config_key`/`config_value` to
avoid reserved-word collisions and match `scout.household_rules.rule_key`.
Alternative: keep `key`/`value` for minimal-code-churn migration. I
lean toward minimal churn - **keep `key`/`value`**.

```
CREATE TABLE scout.member_config (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_member_id  uuid        NOT NULL
        REFERENCES public.family_members (id) ON DELETE CASCADE,
    key               text        NOT NULL,
    value             jsonb       NOT NULL,
    updated_by        uuid        REFERENCES public.family_members (id)
                                  ON DELETE SET NULL,
    created_at        timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at        timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT uq_member_config UNIQUE (family_member_id, key)
);

CREATE INDEX idx_member_config_family_member
    ON scout.member_config (family_member_id);
```

ORM change: `backend/app/models/access.py:55` - add
`__table_args__ = {"schema": "scout"}`. Service
(`permissions.py:186-255`) is unchanged since it uses the ORM.

### 3.2 scout.parent_action_items (target)

Preserve the existing shape from
`012_parent_action_items.sql:7-33`. Verified columns below. Action
types set narrow: current code uses `grocery_review`, `purchase_request`,
`chore_override`, `general`; preserve the CHECK. Status: `pending`,
`resolved`, `dismissed`.

```
CREATE TABLE scout.parent_action_items (
    id                   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id            uuid        NOT NULL
        REFERENCES public.families (id) ON DELETE CASCADE,
    created_by_member_id uuid        NOT NULL
        REFERENCES public.family_members (id) ON DELETE CASCADE,
    action_type          text        NOT NULL,
    title                text        NOT NULL,
    detail               text,
    entity_type          text,
    entity_id            uuid,
    status               text        NOT NULL DEFAULT 'pending',
    resolved_by          uuid        REFERENCES public.family_members (id)
                                     ON DELETE SET NULL,
    resolved_at          timestamptz,
    created_at           timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at           timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT chk_pai_action_type CHECK (action_type IN (
        'grocery_review', 'purchase_request',
        'chore_override', 'general'
    )),
    CONSTRAINT chk_pai_status CHECK (status IN (
        'pending', 'resolved', 'dismissed'
    ))
);

CREATE INDEX idx_scout_pai_family_status
    ON scout.parent_action_items (family_id, status);
CREATE INDEX idx_scout_pai_entity
    ON scout.parent_action_items (entity_type, entity_id);
-- new vs legacy: second index helps the
-- grocery_service.get_pending_action_item lookup (lines 64-68).

CREATE TRIGGER trg_scout_pai_updated_at
    BEFORE UPDATE ON scout.parent_action_items
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

ORM change: `backend/app/models/action_items.py:11` - add
`__table_args__ = {"schema": "scout"}` and update FK string
references to `public.families.id` etc. (SQLAlchemy requires
fully-qualified FK for cross-schema references).

### 3.3 scout.purchase_requests (target)

Preserve shape from `models/grocery.py:36-56`. Small surface.

```
CREATE TABLE scout.purchase_requests (
    id                      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id               uuid        NOT NULL
        REFERENCES public.families (id) ON DELETE CASCADE,
    requested_by_member_id  uuid        NOT NULL
        REFERENCES public.family_members (id) ON DELETE CASCADE,
    type                    text        NOT NULL DEFAULT 'grocery',
    title                   text        NOT NULL,
    details                 text,
    quantity                numeric,
    unit                    text,
    preferred_brand         text,
    preferred_store         text,
    urgency                 text,
    status                  text        NOT NULL DEFAULT 'pending',
    linked_grocery_item_id  uuid,  -- see cross-slice note below
    reviewed_by_member_id   uuid        REFERENCES public.family_members (id)
                                        ON DELETE SET NULL,
    reviewed_at             timestamptz,
    review_note             text,
    created_at              timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at              timestamptz NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT chk_pr_status CHECK (status IN (
        'pending', 'approved', 'denied', 'fulfilled'
    ))
);

CREATE INDEX idx_scout_pr_family_status
    ON scout.purchase_requests (family_id, status);
```

**Cross-slice note (grocery_items):** the legacy FK
`grocery_items.purchase_request_id` (`models/grocery.py:26`) is
already `use_alter=True`. When Slice B (grocery / life management)
moves `grocery_items` into scout, that FK will need to re-point to
`scout.purchase_requests`. **This is a tight coupling point - Slice
D PR Dp (`purchase_requests` consolidation) must land before Slice B
touches grocery_items FK.** Alternative: drop the FK on
grocery_items entirely (it is already ON DELETE SET NULL) and carry
the relationship application-side. Flagged in Section 5.

---

## Section 4. Data migration plan

This is the section where the sprint's critical-path risk lives.
Slice D touches auth and tenant-scoping tables. I separate each move
into *leave-alone*, *copy-then-rewire*, or *live-data move* and
sequence accordingly.

### 4.1 Leave alone (no migration)
- `public.families`, `public.user_accounts`, `public.family_members`,
  `public.sessions`, `public.role_tiers`, `public.role_tier_overrides`,
  `public.scout_scheduled_runs`, `public.scout_mcp_tokens`,
  `public.scout_anomaly_suppressions`, `public._scout_migrations`.
- `scout.connectors`, `scout.connector_accounts`,
  `scout.role_tier_permissions`, `scout.permissions`,
  `scout.user_family_memberships`.

### 4.2 Live-data moves

#### 4.2.1 member_config (1 row) → scout.member_config
Sketch SQL (pseudocode):

```
BEGIN;

CREATE TABLE scout.member_config (...);  -- as Section 3.1

INSERT INTO scout.member_config
    (id, family_member_id, key, value, updated_by,
     created_at, updated_at)
SELECT id, family_member_id, key, value, updated_by,
       created_at, updated_at
FROM   public.member_config;

-- Replace old table with a forwarding view so any un-migrated
-- reader still sees rows (defense-in-depth; grep confirmed nothing
-- reads public.member_config by name, but the view is cheap):
ALTER TABLE public.member_config RENAME TO member_config_legacy;
CREATE VIEW public.member_config AS
    SELECT * FROM scout.member_config;

COMMIT;
```

Dual-write window: none needed (1 row, single code path via
`permissions.py:186-255`). Cutover is ORM-schema flip +
immediate deploy.

Drop legacy in a follow-up (D+N) once a release cycle confirms no
regressions.

#### 4.2.2 parent_action_items (33 rows) → scout.parent_action_items
This is the largest data move in Slice D. **Dual-write window
required** because 5 services + 2 routes currently write to the legacy
table, and a single-deploy atomic cutover would cross a Railway restart.

**Dual-write plan:**
1. PR Dn: create `scout.parent_action_items` (table + indexes +
   trigger). No ORM changes. Data: copy all 33 rows. Add a forwarding
   view `public.parent_action_items_v2_view` or a trigger that mirrors
   inserts from legacy → scout. Verify row counts match.
2. PR Dn+1: ORM flips `ParentActionItem.__tablename__` to scout via
   `__table_args__`. Writes now land in scout. Legacy has a
   scout-side mirror trigger removed; legacy keeps its trigger-mirror
   from scout for the duration of one deploy cycle.
3. PR Dn+2: rename `public.parent_action_items` →
   `public.parent_action_items_legacy`, replace with a view over
   `scout.parent_action_items`. Drop triggers.
4. PR Dn+3 (later release): drop legacy table.

Alternative (simpler, slight downtime risk): single atomic migration
with service code already updated in the same PR. Given 33 rows and
single-app backend, this is actually defensible. Choose A if Railway
has zero-downtime rolling deploy; choose B if not. **Default to B
(atomic).** Critical-path timing is shorter.

Atomic sketch (B):

```
BEGIN;

CREATE TABLE scout.parent_action_items (...);  -- Section 3.2

INSERT INTO scout.parent_action_items SELECT * FROM public.parent_action_items;

-- Rename old out of the way (keep for 1 release cycle).
ALTER TABLE public.parent_action_items RENAME TO parent_action_items_legacy;

CREATE VIEW public.parent_action_items AS
    SELECT * FROM scout.parent_action_items;

COMMIT;
```

ORM change in the same PR: add `__table_args__ = {"schema": "scout"}`
to `ParentActionItem`. FK strings in the model need the `public.`
prefix (already uses bare `families.id` / `family_members.id`, which
resolves via search_path - the cross-schema FK at the Postgres level
is OK because `scout` and `public` share the same search_path in
the connection; SQLAlchemy will still issue the correct DDL when
autoreflecting - verify locally before merge).

**Preserved columns:** all 14. **Dropped:** none. **New indexes:**
`(entity_type, entity_id)` for the grocery-service dedupe query.

#### 4.2.3 purchase_requests (1 row) → scout.purchase_requests
Identical pattern to 4.2.2. 1 row, narrow surface (grocery.py), FK
from grocery_items (`use_alter=True`, nullable).

Sketch:

```
BEGIN;
CREATE TABLE scout.purchase_requests (...);
INSERT INTO scout.purchase_requests SELECT * FROM public.purchase_requests;
-- Drop the grocery_items FK (re-established in Slice B migration).
ALTER TABLE public.grocery_items DROP CONSTRAINT fk_grocery_items_purchase_request;
ALTER TABLE public.purchase_requests RENAME TO purchase_requests_legacy;
CREATE VIEW public.purchase_requests AS SELECT * FROM scout.purchase_requests;
COMMIT;
```

The FK drop is the coupling point with Slice B. Slice B's grocery
consolidation re-adds the FK pointing at `scout.purchase_requests`.

### 4.3 Shape-only deprecations (no data move needed)

#### 4.3.1 public.connector_configs → drop view + table (deferred)
Grep confirmed no backend writes. If rows exist today they are pre-038
artifacts.

Steps: in PR Dc (final cleanup), `DROP VIEW scout.connector_configs;
DROP TABLE public.connector_configs;`. No data to preserve (or, to be
safe, `INSERT INTO scout.connector_accounts` any orphan row first).
Low priority - can slip to Session 4.

#### 4.3.2 scout.* shim views (families / family_members / etc.)
Zero readers. Drop in PR Dc. `DROP VIEW scout.families; ...` (one
statement per view). No code impact.

### 4.4 Cutover sequence (summary)

1. `scout.member_config` (PR D3) - 1 row, narrow.
2. `scout.parent_action_items` (PR D4) - 33 rows, broader surface.
3. `scout.purchase_requests` (PR D5) - 1 row, but Slice B FK coupling.
4. Connector-configs cleanup + shim-view drops (PR Dc, last).

---

## Section 5. Dependencies and CRITICAL-PATH definition

### 5.1 Dependency map (who FKs what)

```
families (public)
    ← family_members (public)
        ← user_accounts (public)
            ← sessions (public)
        ← role_tier_overrides (public)
        ← member_config (public → scout in D3)
        ← parent_action_items (public → scout in D4)
        ← purchase_requests (public → scout in D5)
        ← [scout.* canonical] task_occurrences, task_templates,
          task_completions, reward_policies, allowance_results,
          ledger, routine_templates, etc. (owned by Slice A/C)
        ← [public.* legacy] grocery_items, task_instances, routines,
          chore_templates, daily_wins, events, event_attendees, etc.
          (owned by Slice B/A)
    ← role_tiers (public)
        ← scout.role_tier_permissions
            → scout.permissions
    ← scout.connectors (registry; no family FK)
        ← scout.connector_accounts (family FK)
```

### 5.2 Critical path: ordered list of Slice D PRs that unlock other slices

**PR D0 (pre-req, non-blocking doc-only PR):**
No-code documentation of the "do-not-touch" list: `sessions`,
`family_members`, `families`, `user_accounts`, `role_tiers`,
`role_tier_overrides`, `_scout_migrations`, `scout_scheduled_runs`.
Publish in `docs/atr tasks/open_items.md` so every sibling slice knows
not to schema-alter these.

**PR D1 (MUST LAND FIRST - blocks Slices A, B, C):**
Add ORM model for `scout.role_tier_permissions` and formalize the
`scout.permissions` registry class. No schema change; ORM-only PR.
Motivation: Slices A/B/C are going to add permission keys as they
consolidate features (chore.*, grocery.*, meal_plan.*, allowance.*).
Having a stable ORM class makes their migrations declarative rather
than "raw SQL into scout.permissions." Low risk, high unblock.

**PR D2 (MUST LAND BEFORE Slice A's task consolidation):**
Add `scout.permissions` seed entries for any key Slice A plans to
introduce when it folds `chore_templates` / `task_instances` into
canonical. Essentially a "pre-seed" migration. Alternative: ship the
permission keys inside each slice's migration - fine if they
coordinate. Make the choice explicit in synthesis.

**PR D3 (unlocks nothing - but low risk; land early):**
`scout.member_config` consolidation (Section 4.2.1). Doesn't block
other slices, but is the ARCHITECTURE.md Layer 1 alignment. Serves
as a dry-run for PR D4.

**PR D4 (unlocks NOTHING downstream - Slice B can proceed in
parallel):**
`scout.parent_action_items` consolidation. The grocery service, AI
orchestrator, and dashboard service all write to this table, so
Slice B's grocery work could collide if grocery-service churn lands
mid-flight. Coordinate: PR D4 merges on a quiet window, Slice B
PRs pause-on-hold.

**PR D5 (MUST LAND BEFORE Slice B's grocery_items consolidation):**
`scout.purchase_requests` consolidation. Slice B will re-home
`grocery_items`; the FK `grocery_items.purchase_request_id` must
either be dropped (Slice D5 handles this) and re-added by Slice B
after its grocery consolidation, or be repointed at
`scout.purchase_requests` in Slice B's same migration. Either way,
D5 must land first.

**PR Dc (cleanup, last):**
Drop 8 shim views, drop `public.connector_configs`, rename legacy
tables to `*_legacy`, final indexes audit. No blocking dependencies.

### 5.3 What Slices A / B / C must *not* do while Slice D is in flight

- Do not alter `public.families`, `public.family_members`,
  `public.user_accounts`, `public.sessions`, `public.role_tiers`, or
  `public.role_tier_overrides` - ever, not during this sprint.
- Do not write to `scout.permissions` directly via raw SQL once D1
  lands - use the ORM model.
- Slice B must wait for D5 before touching `grocery_items.purchase_request_id`.
- Slice A must wait for D1 (permissions model) before seeding new
  chore/task permission keys.

---

## Section 6. Proposed PR count and ordering

Six PRs plus a docs PR. Mid estimate: 6 code PRs + 1 doc.

| # | PR title | Migration? | Unlocks |
|---|----------|-----------|---------|
| D0 | docs(slice-d): publish do-not-touch list for sessions/family_members/etc. | No | Clarity for sibling slices |
| D1 | chore(orm): add ORM models for scout.permissions + scout.role_tier_permissions | No | Slices A/B/C can add permission keys declaratively |
| D2 | chore(seeds): pre-seed permission keys for upcoming Slice A/B/C consolidations | Yes (one `INSERT` migration, idempotent) | Slices A/B/C migration ergonomics |
| D3 | feat(scout): move member_config to scout.member_config | Yes (copy + view) | ARCHITECTURE.md Layer 1 alignment |
| D4 | feat(scout): move parent_action_items to scout.parent_action_items | Yes (copy + view, 33 rows) | Consolidation coherence |
| D5 | feat(scout): move purchase_requests to scout.purchase_requests + drop grocery_items FK | Yes (copy + FK drop) | Slice B grocery consolidation |
| Dc | chore(cleanup): drop unused shim views + public.connector_configs | Yes (drops) | Final tidy |

Total: 7 PRs. Realistic range: 5 to 8 depending on whether we split
D4 into the two-step dual-write variant (section 4.2.2 plan A).

### 6.1 Ordering rationale

D0 is docs-only, merges first. D1 is ORM-only, no schema impact, safe
early merge. D2 is a tiny idempotent INSERT migration. D3 (member_config)
is the smallest live-data move - good rehearsal. D4 is the largest.
D5 must land before any Slice B grocery work. Dc is the janitor PR.

---

## Section 7. Per-PR risk rating

| PR | Risk | Reason |
|----|------|--------|
| D0 | low | Docs only. |
| D1 | low | ORM model only; no schema change; no route change. |
| D2 | low | Idempotent INSERTs into scout.permissions with `WHERE NOT EXISTS`. |
| D3 | low-medium | 1 row; simple table; view forwarding; verified by permissions tests. Ping ai_personality_service + nudges_service + affirmations (all read member_config) in smoke. |
| D4 | **medium-high** | 33 live rows; 5 services + 2 routes write the table; AI orchestrator writes it asynchronously; a missed code path means an AI-generated action item silently vanishes. Extra pre-deploy step: grep pass against `ParentActionItem` to confirm no stale reference to the legacy schema. |
| D5 | medium | Only 1 row, but the grocery_items FK is a coupling point with Slice B; a mis-sequenced merge corrupts grocery state. |
| Dc | low | Drops; verify CASCADE behaviour before running. |

No PR in Slice D touches `sessions` or `family_members`. **Any PR that
does touches those is automatic HIGH and must be rejected at review.**

---

## Section 8. Per-PR rollback plan

### D0
- Revert the docs PR. No code state.

### D1
- Revert the branch (ORM class removal). No schema change means no
  forward-migration undo step.

### D2
- Down-migration: `DELETE FROM scout.permissions WHERE permission_key
  IN (...)` targeting the keys seeded in D2. Only executes if no
  `scout.role_tier_permissions` row references them; else the cascade
  RESTRICT fires and rollback aborts. This is desirable: it forces a
  manual decision.

### D3
- Down-migration:
  `BEGIN; DROP VIEW public.member_config; ALTER TABLE public.member_config_legacy RENAME TO member_config; DROP TABLE scout.member_config; COMMIT;`
- Data recovery: `member_config_legacy` preserves the pre-migration
  row. Zero risk.

### D4
- Down-migration (atomic variant): symmetric to D3 - drop
  `scout.parent_action_items`, restore legacy table from
  `parent_action_items_legacy` rename. 33 rows intact.
- Recovery window: **30 days** on the legacy-rename table before the
  final Dc-phase drop. Anyone rolling back after that window must
  restore from point-in-time backup.

### D5
- Down-migration: rename legacy back; re-add the grocery_items FK
  (`ALTER TABLE ... ADD CONSTRAINT fk_grocery_items_purchase_request
  FOREIGN KEY ...`). 1 row of data to preserve.

### Dc
- Undoing shim-view drops: replay the `CREATE OR REPLACE VIEW`
  statements from `022_session2_canonical.sql:183-190`. Since the
  views are zero-content, this is safe.

### Sessions-related rollback (required by spec even though no PR touches it)
- Slice D explicitly does not modify `public.sessions`. If an
  out-of-scope change does end up there and must be rolled back: the
  only safe restore is a point-in-time replica. **Do not let a
  session-touching PR ship without DBA sign-off.**

---

## Section 9. Smoke test strategy

### 9.1 Existing coverage that catches Slice D regressions

- `smoke-tests/tests/auth.spec.ts` (5 tests: adult login, child login,
  bad password, sign out, invalid token). Any break in `sessions` or
  `user_accounts` paths fails these immediately. Path checked:
  `scout-ui/lib/api.ts` → `/auth/login` → `auth_service.login`.
- `backend/tests/test_auth.py` - backend-unit coverage for the same
  endpoints.
- `backend/tests/test_canonical_session2*.py` - three files
  (block1, block2, block3) exercising scout.permissions,
  role_tier_permissions, connector_accounts.
- `backend/tests/test_tenant_isolation.py` - verifies
  cross-family access is rejected.

### 9.2 New coverage required per PR

| PR | New smoke test |
|----|----------------|
| D1 | `backend/tests/test_permissions_orm.py` - assert ORM model matches DB schema (one-row reflection). |
| D2 | extend `test_canonical_session2_block3` to assert that the newly seeded keys are in the registry. |
| D3 | extend `test_auth.py` or add `test_member_config_scout.py` - set a member_config value, read it back, verify a downstream consumer (affirmations or ai_personality) still works. Playwright: add to `smoke-tests/tests/ai-personality.spec.ts` a check that member personality notes persist. |
| D4 | new `backend/tests/test_parent_action_items.py` covering: create via grocery_service path; anomaly dedupe lookup; dashboard_service list; ai/orchestrator creation path. Playwright: add to `smoke-tests/tests/chore-ops.spec.ts` a check that chore_override action items appear in the action inbox. |
| D5 | extend `test_grocery.py` to cover the purchase-request end-to-end after the move; assert FK integrity when grocery_items is later linked to a request. |
| Dc | no new test; run full suite. |

### 9.3 "No user gets logged out" gate for sessions

Before merging **any** PR in this sprint (D or sibling), confirm the
session table row count against a fresh snapshot. If a session row
count drops unexpectedly in a preview deploy, halt.

---

## Section 10. Known gotchas and stop-conditions

1. **`public.sessions` is live-user auth state (172 rows).** Do not
   run any DDL on this table. Do not rename it. Do not drop the shim
   view over it (the shim doesn't hurt). If a future feature genuinely
   needs `scout.sessions`, do it as a fresh read-model, not a move.
2. **`public._scout_migrations` is the migration tracker.**
   `migrate.py:24-29` creates and owns it. Touching this table
   breaks the entire migration runner in place. Absolute do-not-touch.
3. **`public.scout_scheduled_runs` has 48 live rows and is framework
   state, not household data.** The unique index
   `(job_name, family_id, member_id, run_date)` is being used as a
   **mutex** by `backend/app/scheduler.py` (lines 247, 311, 438, 593,
   801). Moving or recreating the table mid-scheduler-tick would
   collapse the mutex and cause duplicate AI runs.
   **Consequence of keeping:** mild naming inconsistency (public table
   with a `scout_` name prefix); zero operational cost.
   **Consequence of migrating:** scheduler downtime, potential
   duplicate jobs on the cutover tick, re-issuing of AI billing.
   **Recommendation: KEEP. Strong.**
4. **`scout.user_family_memberships`** is in the schema as a promise
   (`022_session2_canonical.sql:212`) but not populated. If a sibling
   slice proposes to use it, stop and coordinate - the write-path is
   missing and will need a full sub-plan.
5. **`public.connector_mappings` is polymorphic.** It is intentionally
   not FK'd to `connector_configs`. If Slice A or Slice B adds new
   `internal_table` values to the mapping ingest, make sure the
   `uq_connector_mappings_canonical` index
   (`022_session2_canonical.sql:174`) tolerates them (it does -
   keyed on `connector_name`, `external_object_type`, `external_id`).
6. **ORM cross-schema FKs.** When moving a table into scout (D3, D4,
   D5) and the FK points at `public.family_members(id)`, SQLAlchemy
   needs the fully qualified FK string `public.family_members.id` at
   model time. The shim ORM models use bare names
   (`"family_members.id"`), which rely on search_path. Verify in
   dev before shipping D4; a failed autoreflect on the migrated
   ORM class would break the whole backend.
7. **Dual-write windows vs. atomic cutovers.** For 1-row tables (D3,
   D5) atomic is strictly safer. For the 33-row table (D4), atomic is
   still defensible given a single-app-server backend with ~3-second
   restart. Only adopt dual-write if Railway preview deploys show any
   write during the deploy window. Decide in synthesis.
8. **`public.parent_action_items` writes come from an AI code path.**
   `app/ai/orchestrator.py:351-358` inserts items via the ORM. If the
   ORM class is flipped to scout but an in-flight AI request holds a
   reference to the legacy table, the insert throws. Mitigation: in
   D4, drain scheduler jobs before rolling the deploy (standard
   Railway procedure) OR keep the legacy table as a view.
9. **`connector_mappings`** retained on public is fine but the
   audit's "shim" label is misleading. It is a first-class table, not
   a view. Flag for audit correction.
10. **Shim-view cosmetic change risk.** If at any point someone adds
    a schema change to `public.role_tiers` without re-running the
    `CREATE OR REPLACE VIEW scout.role_tiers` statement, the shim
    view goes stale. Migration 024 already demonstrates this pattern
    (`024_permissions_and_config.sql:42, 87`). Every slice's
    migration must repeat the view-refresh pattern.

### Stop-conditions for synthesis

Synthesis should **not** bundle Slice D work together with any of the
following without re-planning:

- Any PR altering `public.sessions` (even cosmetic).
- Any PR altering `public.family_members` columns (renaming, adding
  CHECK constraints, index changes - not row-level data).
- Any PR altering `public._scout_migrations`.
- Any PR that adds a new migration 0NN *before* the existing highest
  number without double-checking `migrate.py` ordering (numeric sort).
- Slice B PRs touching `grocery_items.purchase_request_id` shipping
  before Slice D PR D5.
- Slice A PRs seeding permission keys directly via raw SQL before
  Slice D PR D1 lands the ORM model.

---

## Open questions

1. **scout.user_family_memberships:** Who owns wiring this in Session
   4? It's referenced by the ARCHITECTURE model but nothing writes to
   it today. If the answer is "Slice D in a future sprint," noting it
   here but deferring is fine. If it's "Slice A is about to start
   using it," then D needs to add it to D1/D2.
2. **Dual-write vs. atomic for D4:** Railway preview deploy behaviour
   for a single-app backend - does the previous pod keep serving
   writes during the overlap? If yes, atomic is still safe (pod
   restart means in-flight writes fail-fast, not silent corruption).
   Confirm with ops before choosing.
3. **Eventual consolidation of family_members, etc. into scout:** Is
   the long-term target to keep them in public forever, or to migrate
   them in a later session once cascade risk is lower? My plan treats
   them as "never move" - if ops has a different plan, tell me.
4. **Audit re-classification:** does the Synthesis agent want me to
   file a patch to the audit document reclassifying `scout.permissions`
   as CANONICAL (instead of UNCLEAR) and `public.connector_configs`
   as LEGACY-NO-ACTIVE-WRITE? I'd propose yes.
5. **`_scout_migrations` table ownership:** the migrate.py file is the
   only thing that touches this table; there is no ORM model and no
   test. Should Slice Dc add a read-only audit view
   `scout.v_migrations` for visibility? Nice-to-have, not required.

---

Plan completed: 2026-04-22
Author: Subagent D (planning, no code or schema changes)
Evidence: citations drawn from `backend/` grep runs;
see Section 1 for file:line anchors.
