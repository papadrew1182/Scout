# Scout parallel session 2 — canonical household model, connectors, sync, and read models

## How to use this document

This file is the full context packet for one parallel coding/chat session. Open it in its own chat and treat it as the authoritative charter for the backend, data, and connector lane.

This session must reconcile against these master artifacts at the start and end of each work block:

- `scout_external_data_roadmap.md`
- `Scout_Session1_Handoff (2).md`
- `family_chore_system.md`
- `Building a weekly meal staples list - Claude.pdf` when work touches meal-planning context
- `scout_session_3_operating_surface_and_control_plane.md`

This lane maps to the master roadmap primarily across:
- Phase 0 — foundation reset and connector platform
- Phase 1 — Scout-native chores and routines engine, data layer
- Phase 2 — Google Calendar connector and Hearth display lane
- Phase 4 — Greenlight connector and payout settlement
- Phase 5 — Rex inbound connector
- Phase 6 — YNAB connector
- Phase 8 — Google Maps travel-time enrichment
- Phase 9 — Apple Health and Nike Run Club
- control-plane and read-model support for all later phases

## Program context you should assume

Scout is not a Hearth chore wrapper.

Current product boundary:
- Scout is the source of truth for chores, routines, task generation, task completion, standards of done, reminders, Daily Win scoring, and allowance logic.
- Google Calendar is the scheduling spine.
- Hearth is display only, fed by Scout through the calendar lane.
- Greenlight is the payout-facing rail, not the rules engine.
- Rex is inbound only.
- YNAB remains the financial engine.
- Apple Health and Nike Run Club are read-only context feeds in v1.
- Google Maps is an enrichment service, not a system of record.
- Exxir is decision-gated and should not be built unless it adds a signal Rex does not already provide.

Known family context that matters to this lane:
- Parents: Andrew and Sally
- Kids: Sadie (13), Townes (10), River (8)
- Household rules already defined in the family file must be encoded into Scout-native data structures:
  - one owner per task
  - finishable lists
  - explicit standards of done
  - quiet enforcement
  - one reminder max
- Current routine/chore system includes:
  - morning, after-school, and evening routines
  - ownership chores
  - odd/even rotating Common Area Closeout
  - Sadie-led dog walk system with Townes/River odd-even assistant rule
  - Saturday Power 60
  - Backyard Poop Patrol with 8-week owner/assistant rotation
  - Daily Win scoring and allowance outcomes

Session 1 already established the first foundation tables that must exist:
- `families`
- `family_members`
- `user_accounts`
- `sessions`
- `role_tiers`
- `role_tier_overrides`
- `connector_mappings`
- `connector_configs`

This lane extends that foundation so Scout can actually run the household and normalize external signals cleanly.

## Lane mission

Build the data foundation that lets Scout become a native family operating system with maintainable external connectors.

This lane owns:
- the foundational ERD and migration plan
- Scout-native household tables
- role tiers and access model
- connector registry and connector account state
- sync jobs, sync cursors, event logs, and freshness tracking
- normalized internal objects
- Google Calendar publication model
- Greenlight settlement ledger and approval state
- inbound work, budget, activity, and travel context models
- curated `scout.v_*` read models for the UI and AI layers
- identity, context, household-summary, rewards, and connector-health endpoints
- connector adapter scaffolding and repository structure
- audit trail and resync / repair support

This lane does not own:
- final mobile or web UI layout
- widget rendering
- Siri Shortcut implementation
- notification copy and delivery UX
- chat assistant rendering
- final meal-planning prompt orchestration
- direct Hearth task logic
- writeback into Rex

## Branch and ownership boundary

Recommended branch name:

`feat/scout-canonical-household-connectors`

Do not take ownership of:
- frontend operating-surface components
- widget chrome
- lock-screen UI
- assistant conversation rendering
- direct Greenlight parent-approval UI
- rich notification UX

You can expose the contracts those surfaces need, but do not permanently redefine frontend-owned interfaces from this lane.

## Canonical schema split

This is the locked pattern for Scout.

### Product schema
Use `scout` for canonical product data and operational metadata.

`scout` contains:
- identity and access
- families and family members
- household rules
- routine and task templates
- task occurrences and completions
- standards of done
- reward rules and allowance results
- calendar exports
- connector registry and sync metadata
- normalized external context
- read models
- later: second-brain memory, actions, notifications, and planning artifacts

### Connector schemas
Use source-specific schemas for raw or staged source data when the source warrants persistent staging:

- `connector_google_calendar`
- `connector_rex`
- `connector_ynab`
- `connector_greenlight`
- `connector_apple_health`
- `connector_nike_run_club`
- `connector_exxir` if and only if the Exxir decision gate is cleared

### Special cases
Do not overbuild these:

- Hearth does not need a source-data schema. It is a display endpoint reached through calendar publication.
- Google Maps can be modeled as a service integration rather than a full raw staging schema unless usage patterns prove otherwise.
- Apple Health may be mediated by platform-native permissions or aggregators. Keep the contract clean and avoid premature staging complexity.

## Suggested canonical role-tier seed set

`role_tiers` should be extensible. A recommended seed set is:

- `PRIMARY_PARENT`
- `PARENT`
- `TEEN`
- `CHILD`
- `YOUNG_CHILD`
- `DISPLAY_ONLY`

Notes:
- Do not make raw age the only permission system.
- Use role tiers for permissions and age-band metadata for presentation.
- Support per-user and per-family overrides in `role_tier_overrides`.
- Keep kid safety and edit boundaries data-driven.

## Core data model this lane should create

### Foundation and identity
Required foundation tables from Session 1:
- `scout.families`
- `scout.family_members`
- `scout.user_accounts`
- `scout.sessions`
- `scout.role_tiers`
- `scout.role_tier_overrides`
- `scout.connector_mappings`
- `scout.connector_configs`

Recommended additional identity / access tables:
- `scout.permissions`
- `scout.role_tier_permissions`
- `scout.user_family_memberships`
- `scout.user_preferences`
- `scout.device_registrations`

### Household operating system
Recommended tables:
- `scout.household_rules`
- `scout.standards_of_done`
- `scout.routine_templates`
- `scout.routine_steps`
- `scout.task_templates`
- `scout.task_assignment_rules`
- `scout.task_occurrences`
- `scout.task_completions`
- `scout.task_exceptions`
- `scout.task_notes`
- `scout.time_blocks`
- `scout.calendar_exports`
- `scout.notification_rules`
- `scout.delivery_events`

### Rewards and allowance
Recommended tables:
- `scout.reward_policies`
- `scout.daily_win_results`
- `scout.allowance_periods`
- `scout.allowance_results`
- `scout.reward_extras_catalog`
- `scout.reward_ledger_entries`
- `scout.settlement_batches`
- `scout.greenlight_exports`

### Connector registry and sync ops
Recommended tables:
- `scout.connectors`
- `scout.connector_accounts`
- `scout.sync_jobs`
- `scout.sync_runs`
- `scout.sync_cursors`
- `scout.connector_event_log`
- `scout.stale_data_alerts`

### Normalized external context
Recommended canonical tables:
- `scout.external_calendar_events`
- `scout.work_context_events`
- `scout.budget_snapshots`
- `scout.bill_snapshots`
- `scout.activity_events`
- `scout.travel_estimates`
- `scout.meal_plan_runs`
- `scout.meal_plans`
- `scout.grocery_lists`

### Source-link / mapping model
Use `scout.connector_mappings` as the only durable source-ID registry.

Recommended columns:
- `id uuid primary key`
- `connector_key text not null`
- `external_object_type text not null`
- `external_id text not null`
- `internal_table text not null`
- `internal_id uuid not null`
- `family_id uuid null`
- `user_account_id uuid null`
- `metadata jsonb not null default '{}'::jsonb`

Recommended uniqueness:
- unique on `(connector_key, external_object_type, external_id)`

Do not place connector-native IDs directly on household domain tables unless a later exception is explicitly documented.

## Internal normalized objects

Regardless of source, Scout should normalize into these internal objects:

- person
- family member
- household event
- time block
- routine block
- task occurrence
- completion event
- reward ledger entry
- calendar export
- budget snapshot
- bill snapshot
- work-pressure signal
- activity / workout event
- travel estimate
- meal plan
- grocery list

The UI and AI layers should read these normalized objects or curated views, not connector-specific tables.

## Curated read models this lane should expose

These are the initial views the operating-surface lane and the AI layer should target:

- `scout.v_household_today`
- `scout.v_household_week`
- `scout.v_rewards_current_week`
- `scout.v_calendar_publication`
- `scout.v_budget_context`
- `scout.v_work_context`
- `scout.v_activity_context`
- `scout.v_meal_planning_context`
- `scout.v_control_plane`

### Purpose of each view

`scout.v_household_today`
- current date context
- due blocks
- routine and task occurrences
- late / completed / blocked state
- active child summaries
- Daily Win eligibility hints

`scout.v_household_week`
- weekly recurrence expansion
- Power 60 and poop-patrol rotation state
- child workload rollups
- anchor blocks that should publish to calendar

`scout.v_rewards_current_week`
- baseline allowance
- completed Daily Wins
- projected payout
- miss reasons
- extras
- approval and export state

`scout.v_calendar_publication`
- Google Calendar exportable blocks
- source object references
- export freshness
- Hearth-display relevance

`scout.v_budget_context`
- grocery category status
- upcoming bills
- savings-plan progress
- category balances needed for weekly planning

`scout.v_work_context`
- inbound Rex load summary
- hard work blocks
- meeting clusters
- deadline pressure
- family-impact signal

`scout.v_activity_context`
- workouts
- recent activity volume
- simple readiness hints

`scout.v_meal_planning_context`
- dinner complexity by night
- budget pressure
- guest flags
- calendar load
- future pantry hooks

`scout.v_control_plane`
- connector status
- freshness
- sync errors
- export lag
- stale-data warnings

## Connector adapter contract

Define a clean adapter interface under `backend/services/connectors/`.

Suggested package structure:

```text
backend/
  services/
    connectors/
      base.py
      registry.py
      sync_service.py
      google_calendar/
        adapter.py
        mapper.py
        client.py
      greenlight/
        adapter.py
        mapper.py
        client.py
      rex/
        adapter.py
        mapper.py
        client.py
      ynab/
        adapter.py
        mapper.py
        client.py
      apple_health/
        adapter.py
        mapper.py
      nike_run_club/
        adapter.py
        mapper.py
        client.py
      google_maps/
        service.py
      exxir/
        adapter.py
        mapper.py
        client.py
      hearth_display/
        publisher.py
```

### Base concepts every connector should support
- `health_check()`
- `get_account_summary()`
- `backfill(scope, cursor=None)`
- `incremental_sync(cursor=None)`
- `map_to_internal_objects(records)`
- `list_supported_entities()`
- `get_freshness_state()`
- `disable()`
- `reconnect()`

### Connector-specific expectations

Google Calendar:
- read calendar list
- read selected events
- create/update/delete Scout-managed blocks
- track imported versus Scout-generated objects
- handle recurrence and exceptions

Greenlight:
- read account / balance visibility if feasible
- stage approved payout exports
- return export result or export error state
- do not own reward logic

Rex:
- read only
- fetch meetings, work blocks, deadlines, and pressure signals
- do not write back
- do not mirror all Rex objects just because they exist

YNAB:
- read only in v1
- fetch grocery categories, key category balances, upcoming bills, savings-plan progress

Apple Health and Nike Run Club:
- read only
- normalize into one activity layer
- avoid unnecessary duplicate ingestion if two sources provide the same signal

Google Maps:
- request/response travel estimates
- cache reasonably
- do not turn it into a fake source of truth

Exxir:
- define the adapter contract now if needed
- do not implement beyond a narrow decision-cleared use case

## Identity and context endpoints owned by this lane

The frontend lane should build directly against these contracts or mock-compatible versions of them.

### `GET /api/me`

```json
{
  "user": {
    "id": "uuid",
    "email": "andrew@example.com",
    "full_name": "Andrew Roberts",
    "role_tier_key": "PRIMARY_PARENT",
    "family_member_id": "uuid",
    "feature_flags": {
      "calendar_publish": true,
      "greenlight_settlement": true,
      "meal_planning": false
    }
  },
  "family": {
    "id": "uuid",
    "name": "Roberts Family",
    "timezone": "America/Chicago"
  }
}
```

### `GET /api/family/context/current`

```json
{
  "family": {
    "id": "uuid",
    "name": "Roberts Family",
    "timezone": "America/Chicago"
  },
  "date": "2026-04-15",
  "active_time_block": {
    "id": "uuid",
    "label": "After School",
    "starts_at": "2026-04-15T15:30:00-05:00",
    "ends_at": "2026-04-15T17:30:00-05:00",
    "status": "upcoming"
  },
  "kids": [
    {"family_member_id": "uuid-1", "name": "Sadie", "age": 13, "role_tier_key": "TEEN"},
    {"family_member_id": "uuid-2", "name": "Townes", "age": 10, "role_tier_key": "CHILD"},
    {"family_member_id": "uuid-3", "name": "River", "age": 8, "role_tier_key": "YOUNG_CHILD"}
  ],
  "household_rules": {
    "one_owner_per_task": true,
    "one_reminder_max": true
  }
}
```

### `GET /api/household/today`

```json
{
  "date": "2026-04-15",
  "summary": {
    "due_count": 18,
    "completed_count": 6,
    "late_count": 1
  },
  "blocks": [
    {
      "block_key": "morning",
      "label": "Morning Routine",
      "due_at": "2026-04-15T07:25:00-05:00",
      "exported_to_calendar": true,
      "assignments": [
        {
          "routine_instance_id": "uuid",
          "family_member_id": "uuid-1",
          "member_name": "Sadie",
          "status": "complete",
          "steps": [
            {"task_occurrence_id": "uuid", "label": "Make bed", "status": "complete"}
          ]
        }
      ]
    }
  ],
  "standalone_chores": [
    {
      "task_occurrence_id": "uuid",
      "template_key": "dog_walks",
      "label": "Dog Walks",
      "owner_family_member_id": "uuid-1",
      "owner_name": "Sadie",
      "due_at": "2026-04-15T19:30:00-05:00",
      "status": "open"
    }
  ],
  "weekly_items": [
    {
      "task_occurrence_id": "uuid",
      "label": "Power 60",
      "due_at": "2026-04-18T10:00:00-05:00",
      "status": "upcoming"
    }
  ]
}
```

### `POST /api/household/completions`

```json
{
  "task_occurrence_id": "uuid",
  "completed_by_family_member_id": "uuid",
  "completed_at": "2026-04-15T17:04:00-05:00",
  "completion_mode": "manual",
  "notes": null
}
```

Response:

```json
{
  "task_occurrence_id": "uuid",
  "status": "complete",
  "daily_win_recomputed": true,
  "reward_preview_changed": false
}
```

### `GET /api/rewards/week/current`

```json
{
  "period": {
    "id": "uuid",
    "start_date": "2026-04-13",
    "end_date": "2026-04-17"
  },
  "members": [
    {
      "family_member_id": "uuid-1",
      "name": "Sadie",
      "baseline_allowance": 12,
      "daily_wins": 4,
      "payout_percent": 0.8,
      "projected_payout": 9.6,
      "miss_reasons": ["Common Area Closeout missed on Wednesday"]
    }
  ],
  "approval": {
    "state": "draft"
  }
}
```

### `GET /api/connectors`

```json
{
  "items": [
    {
      "connector_key": "google_calendar",
      "label": "Google Calendar",
      "status": "connected",
      "last_sync_at": "2026-04-15T12:00:00Z"
    },
    {
      "connector_key": "greenlight",
      "label": "Greenlight",
      "status": "configured",
      "last_sync_at": null
    }
  ]
}
```

### `GET /api/connectors/health`

```json
{
  "items": [
    {
      "connector_key": "google_calendar",
      "healthy": true,
      "freshness_state": "live",
      "last_success_at": "2026-04-15T12:00:00Z",
      "last_error_at": null,
      "last_error_message": null
    }
  ]
}
```

### `GET /api/calendar/exports/upcoming`

```json
{
  "items": [
    {
      "calendar_export_id": "uuid",
      "label": "Evening Reset",
      "starts_at": "2026-04-15T20:00:00-05:00",
      "ends_at": "2026-04-15T20:30:00-05:00",
      "source_type": "routine_block",
      "source_id": "uuid",
      "target": "google_calendar",
      "hearth_visible": true
    }
  ]
}
```

### `GET /api/control-plane/summary`

```json
{
  "connectors": {
    "healthy_count": 2,
    "stale_count": 1,
    "error_count": 0
  },
  "sync_jobs": {
    "running_count": 1,
    "failed_count": 0
  },
  "calendar_exports": {
    "pending_count": 0,
    "failed_count": 0
  },
  "rewards": {
    "pending_approval_count": 1
  }
}
```

## Connector and control-plane status vocabulary

Use backend-defined status values. Recommended baseline vocabulary:

Connector `status`
- `disconnected`
- `configured`
- `connected`
- `syncing`
- `stale`
- `error`
- `disabled`
- `decision_gated`

Freshness `freshness_state`
- `live`
- `lagging`
- `stale`
- `unknown`

Do not let the frontend invent parallel status systems.

## Implementation sequence

### Work packet A — migration scaffold
- create the migration files needed for the first foundation and connector pass
- establish naming patterns
- document ownership and dependencies per migration

### Work packet B — identity and access
- create foundation tables from Session 1
- add permissions, role-tier permission joins, family memberships, preferences, and devices
- seed role tiers and permission mappings
- document any role-tier ambiguity instead of hiding it

### Work packet C — household operating schema
- create standards-of-done, routine, task, assignment-rule, occurrence, completion, and exception tables
- encode the household rule primitives needed for:
  - morning / after-school / evening routines
  - ownership chores
  - odd/even rotating chores
  - dog-walk assistant logic
  - Saturday Power 60
  - 8-week poop-patrol rotation
- build Daily Win computation inputs directly on top of Scout-owned completion data

### Work packet D — connector registry and sync
- create connectors, connector accounts, sync jobs, sync runs, sync cursors, connector event log, and stale-data alerts
- create `connector_configs` and `connector_mappings` enforcement
- add audit metadata and repair hooks

### Work packet E — Google Calendar lane
- create Google Calendar connector scaffolding
- support calendar discovery and selection
- support imported-events normalization
- support Scout-managed block publication
- separate imported events from Scout-generated exports
- support recurrence and exceptions

### Work packet F — rewards and Greenlight settlement
- create reward policies, Daily Win results, allowance periods/results, extras, ledger entries, settlement batches, and export records
- keep Greenlight as settlement rail only
- expose approval/export state cleanly

### Work packet G — inbound work and money context
- create Rex read-only context tables and normalization
- create YNAB budget and bill snapshots
- keep both scoped to family-planning relevance, not source completeness

### Work packet H — activity and travel enrichment
- create activity-event and travel-estimate models
- add Apple Health, Nike Run Club, and Google Maps service scaffolding
- keep duplicate and privacy handling explicit

### Work packet I — read models and endpoints
- build `scout.v_*` views
- implement `GET /api/me`
- implement `GET /api/family/context/current`
- implement `GET /api/household/today`
- implement `POST /api/household/completions`
- implement `GET /api/rewards/week/current`
- implement `GET /api/connectors`
- implement `GET /api/connectors/health`
- implement `GET /api/calendar/exports/upcoming`
- implement `GET /api/control-plane/summary`

### Work packet J — tests and hardening
At minimum:
- migration sanity tests
- role-tier seed tests
- connector-mapping uniqueness tests
- recurrence-expansion tests
- odd/even assignment tests
- 8-week rotation tests
- Daily Win calculation tests
- Google Calendar export smoke tests
- endpoint contract tests
- stale-data / sync-state tests

## Non-goals for this session

Do not spend time on:
- final operating-surface polish
- widget UI
- Siri Shortcut plumbing
- assistant chat rendering
- rich reminder copy
- direct Hearth task APIs
- broad Exxir work unless the decision gate is explicitly cleared
- turning YNAB or Greenlight into replicated source systems

## Cross-lane dependencies

### Session 3 depends on this lane for
- family identity and role tiers
- current family context
- household-today read model
- rewards current-week payload
- connector health
- calendar-export preview data
- control-plane summary data

To unblock Session 3 quickly:
- stabilize API shapes early
- allow mock-backed implementations until migrations and sync are complete
- do not churn route names or payload keys casually

### Session 1 continuity
This lane is a direct continuation of the Session 1 handoff. If this lane changes the foundation model, update:
- this session doc
- `scout_external_data_roadmap.md`
- the next session handoff
- `scout_session_3_operating_surface_and_control_plane.md`

## Merge gates for this lane

### Gate A — foundation freeze
- foundation tables from Session 1 exist
- household tables exist
- connector mappings and configs are the sole source of external IDs and connector config

### Gate B — connector-platform freeze
- connector registry exists
- sync runs and cursors exist
- stale-data detection exists
- Google Calendar scaffolding exists
- no product logic depends on Hearth task state

### Gate C — contract freeze
- published endpoint shapes exist
- read models are stable enough for UI work
- no frontend lane is forced to read connector tables directly

### Gate D — rewards and context freeze
- Daily Win and allowance results are DB-backed
- Greenlight remains settlement-only
- Rex remains inbound-only
- YNAB remains budget-source-only

## Definition of done for the first pass

This lane is considered done for the first merge if all of these are true:

- the Session 1 foundation tables exist in workable form
- Scout-native household tables exist in workable form
- connector registry, accounts, sync jobs, sync runs, and cursors exist
- Google Calendar connector scaffolding exists
- reward and allowance tables exist
- starter context models for Rex and YNAB exist
- `scout.v_household_today`, `scout.v_rewards_current_week`, `scout.v_calendar_publication`, and `scout.v_control_plane` exist
- `GET /api/me`, `GET /api/family/context/current`, `GET /api/household/today`, `POST /api/household/completions`, `GET /api/rewards/week/current`, `GET /api/connectors`, and `GET /api/connectors/health` work
- no UI or AI logic is forced to read connector tables directly
- Hearth remains display-only in the architecture and in code

## Reconciliation checklist against the master roadmap

At the start and end of each work block, explicitly verify:

1. Is the implementation still aligned to:
   - Phase 0
   - Phase 1 data layer
   - Phase 2 connector layer
   - Phase 4 settlement layer
   - later Phase 5 / 6 / 8 / 9 prep

2. Has any schema choice violated the locked pattern?
   - `scout` for canonical product data
   - connector schemas only for source-native or staged data
   - Hearth display-only, not a chore source of truth
   - external IDs only via `connector_mappings`

3. Did any code reintroduce old structural mistakes?
   - Scout depending on Hearth for task logic
   - Greenlight owning reward rules
   - Rex writeback
   - YNAB clone behavior
   - connector-specific IDs stored on household tables

4. If a contract changed, was the change reflected in:
   - this session doc
   - `scout_external_data_roadmap.md`
   - the next handoff
   - `scout_session_3_operating_surface_and_control_plane.md`

## Suggested end-of-session status note

Use this template in the parallel chat when closing a work block:

```md
### Scout Session 2 status
Completed:
- ...

In progress:
- ...

Blocked by Session 3:
- ...

Contracts changed:
- ...

Roadmap reconciliation:
- Still aligned to Phase 0 / 1-data / 2 / 4 / later 5-6-8-9 prep
- Drift introduced: yes/no
- If yes, updated docs: yes/no
```
