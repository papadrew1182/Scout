# Scout parallel session 3 — operating surface, daily household UI, rewards UI, and control plane

## How to use this document

This file is the full context packet for one parallel coding/chat session. Open it in its own chat and treat it as the authoritative charter for the frontend and operating-surface lane.

This session must reconcile against these master artifacts at the start and end of each work block:

- `scout_external_data_roadmap.md`
- `Scout_Session1_Handoff (2).md`
- `family_chore_system.md`
- `Building a weekly meal staples list - Claude.pdf` when work touches meal-planning surfaces
- `scout_session_2_canonical_household_and_connectors.md`

This lane maps to the master roadmap primarily across:
- Phase 1 — Scout-native chores and routines engine, UI and interaction layer
- Phase 2 — Google Calendar connector and Hearth display lane, preview and visibility layer
- Phase 3 — notifications, actions, widgets, and operating surface
- Phase 4 — Greenlight connector and payout approval surface
- later support for Phase 5 through Phase 9 surfaces

## Program context you should assume

Scout is the product and Scout owns the household workflow.

Current product boundary:
- Scout is the system of record for chores, routines, task generation, completion, reminders, Daily Win scoring, and allowance logic.
- Hearth is display only and should be treated as an ambient calendar-fed display, not an interaction surface for task logic.
- Google Calendar is the scheduling spine and publication path for household anchor blocks.
- All family members are on iOS.
- Delivery matters as much as data: push notifications, Siri Shortcuts, widgets, and lock-screen style actions are core product surfaces.
- There is no internal messaging domain. Operational action surfaces replace it.
- Scout serves Andrew and Sally as the parents, and it must also support age-appropriate kid-facing flows for Sadie, Townes, and River.

Known household behavior that must show up in the UI:
- morning, after-school, and evening routines with due times
- ownership chores
- odd/even rotating Common Area Closeout
- Sadie-led dog walks with Townes/River assistant rule
- Saturday Power 60
- Backyard Poop Patrol with 8-week rotation
- standards of done
- quiet enforcement and one-reminder-max behavior
- Daily Win and weekly payout preview

Do not reintroduce Hearth as the place where chores are completed. That boundary is closed.

## Lane mission

Build the operating surface that turns Scout into a usable family OS day to day.

This lane owns:
- the app shell or navigation shell for Scout
- the Today view and household board
- kid-appropriate and parent-appropriate task surfaces
- routine and chore completion flows
- standards-of-done and detail presentation
- Daily Win progress and rewards UI
- calendar publication preview and Hearth-display confirmation surfaces
- connector health and control-plane starter surfaces
- notification-preference and action-entry starter surfaces
- mock-compatible frontend hooks and state so work can continue in parallel with backend implementation

This lane does not own:
- backend migrations
- connector sync implementations
- reward-calculation logic
- Google Calendar write logic
- Greenlight export internals
- Rex / YNAB / Health normalization logic
- Siri Shortcut plumbing on the native side unless the repo already supports it
- final push delivery infrastructure

## Branch and ownership boundary

Recommended branch name:

`feat/scout-operating-surface`

Do not take ownership of:
- database design
- connector adapters
- sync runners
- payout export internals
- reward rules
- backend-only read models

You can mock or adapt to those interfaces until Session 2 lands, but do not permanently redefine data contracts from the UI lane.

## Product shell guidance

Scout should be built mobile-first. Do not inherit desktop-first assumptions from the Rex sidebar shell just because the session format is similar.

If the client repo is React Native / Expo:
- use tabs, stacks, or a bottom-sheet assistant
- make Today the default entry point
- make completion actions reachable in one tap from the primary surface

If the client repo is React web:
- use a durable shell with clear route structure
- preserve the same information architecture
- do not let web routing force desktop-only UX decisions that conflict with the iOS-first product

Recommended top-level feature boundaries, regardless of framework:

```text
client/
  app/
    Shell
    Navigation
    AppContext
  today/
    TodayHome
    HouseholdBoard
    BlockCard
    ChoreList
    CompletionSheet
  rewards/
    RewardsHome
    DailyWinCard
    WeeklyPayoutCard
    ApprovalSheet
  calendar/
    CalendarPreview
    HouseholdBlocksPreview
  controlPlane/
    ControlPlaneHome
    ConnectorHealthPanel
    SyncStatusPanel
    PublicationStatusPanel
  notifications/
    NotificationPreferences
    ActionCenter
  assistant/
    ScoutAssistEntry
    SuggestionChips
  hooks/
    useMe
    useFamilyContext
    useHouseholdToday
    useRewardsWeek
    useConnectorsHealth
    useControlPlaneSummary
  lib/
    api
    formatters
```

You do not have to use these exact names, but the boundaries should stay clear.

## Primary UI goals

### 1. Today-first household operating surface
The primary surface should answer:
- what is active now
- what is due next
- who still has work left
- what can be completed in one tap
- what is blocked or late
- whether today is still a Daily Win candidate for each child

### 2. Completion flows that are fast enough to use in real life
Completion should support:
- one-tap completion where possible
- standards-of-done detail when needed
- clear ownership
- explicit due-time context
- quick parent review for missed items
- no clutter that makes the system harder to use than the chores themselves

### 3. Parent dashboard and kid-appropriate views
Parents need:
- household summary
- late / open / complete views
- payout preview
- export / approval state
- connector and calendar status

Kids need:
- simple personal view
- what is due now
- what is next
- progress toward done
- minimal cognitive load

### 4. Calendar-publication awareness
The UI should show:
- which household anchor blocks are being exported to Google Calendar
- what Hearth will effectively display
- whether exports are healthy or stale
- a preview that prevents calendar clutter mistakes

### 5. Control plane starter surfaces
Because connectors and sync are core to Scout, expose:
- connector health
- sync status
- export status
- reward approval status
- stale-data warnings
- future placeholders for meal-planning, budget, and work context

## UI contracts consumed by this lane

Do not invent alternate contracts unless the team explicitly agrees and all docs are updated.

### `GET /api/me`

Use this shape:

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

Use this shape:

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

Use this shape:

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

Use this request shape:

```json
{
  "task_occurrence_id": "uuid",
  "completed_by_family_member_id": "uuid",
  "completed_at": "2026-04-15T17:04:00-05:00",
  "completion_mode": "manual",
  "notes": null
}
```

Response shape:

```json
{
  "task_occurrence_id": "uuid",
  "status": "complete",
  "daily_win_recomputed": true,
  "reward_preview_changed": false
}
```

### `GET /api/rewards/week/current`

Use this shape:

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

Use this shape:

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

Use this shape:

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

Use this shape:

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

Use this shape:

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

## UI state model

Use a small, clear state architecture. Recommended global state buckets:

- `me`
- `familyContext`
- `householdToday`
- `completionMutations`
- `rewardsWeek`
- `connectors`
- `connectorsHealth`
- `calendarExports`
- `controlPlaneSummary`
- `uiState`
  - selected member or household mode
  - parent vs kid view mode
  - current date
  - expanded task details
  - pending completion sheet
  - active tab or route

Avoid scattering the only copy of household status inside leaf components. The Today surface is global product state.

## Surface responsibilities

### `Shell`
- app chrome or tab shell
- primary route / tab state
- global loading and error boundaries
- entry point into Today, Rewards, Calendar, Control Plane, and Assist

### `TodayHome`
- overall household summary for the day
- what is active now
- due-next summary
- quick access to completion

### `HouseholdBoard`
- render routine blocks and chores grouped by time block
- allow switching between household-wide and per-child view
- surface late / open / complete state clearly

### `BlockCard`
- render a single anchor block such as Morning Routine, After School, Evening Reset, or Power 60
- show due time
- show export-to-calendar state
- show child assignments and progress

### `ChoreList`
- render task occurrences within a block or standalone chores
- display owner, due time, and completion state
- keep the list fast and scannable

### `CompletionSheet`
- one-tap complete where possible
- standards-of-done detail when needed
- optional notes
- recompute and refetch reward preview after completion

### `RewardsHome`
- current week Daily Win progress
- baseline allowance
- payout preview
- missed-item explanations
- extras and approval placeholder

### `CalendarPreview`
- preview the household anchor blocks being exported
- make Hearth-display implications visible
- show stale or failed export state

### `ControlPlaneHome`
- connector health
- sync status
- export status
- pending reward approvals
- stale-data warnings

### `NotificationPreferences`
- starter settings surface
- quiet hours
- summary preferences
- parent vs kid notification routing placeholders

### `ScoutAssistEntry`
- lightweight assist affordance, not necessarily a desktop sidebar
- entry point to ask Scout what is next, what is overdue, or why a payout changed
- can start as a thin launcher or bottom sheet

## Recommended implementation sequence

### Work packet A — shell foundation
- replace placeholder or fragmented entry UI with a real product shell
- make Today the default landing surface
- support a clean navigation path to Rewards, Calendar, and Control Plane
- keep layout adaptable for mobile-first usage

### Work packet B — household Today surface
- build `TodayHome`
- build `HouseholdBoard`
- render morning / after-school / evening blocks
- render standalone chores and weekly items
- support household and per-child views

### Work packet C — completion UX
- build fast completion actions
- add standards-of-done detail presentation
- add loading, disabled, success, and error states
- make reward preview refresh after completion

### Work packet D — rewards UI
- build current-week payout preview
- surface Daily Win state
- explain misses cleanly
- add parent-only approval placeholder if backend is not ready yet

### Work packet E — calendar publication preview
- render exported anchor blocks
- show what Hearth will display
- surface stale or failed publication status
- keep preview focused on anchor blocks, not micro-task clutter

### Work packet F — control plane starter
- add connector health
- add sync status
- add reward approval count
- add stale-data warnings
- add future placeholders for work context, budget context, and meal planning

### Work packet G — notifications and action-entry starter
- create notification-preferences screen
- create action-center starter surface
- create a minimal assist entry that can answer household-status style questions later
- do not block on full native delivery plumbing

### Work packet H — mock clients and contract hardening
Before backend endpoints are fully live:
- create mock `useMe`
- create mock `useFamilyContext`
- create mock `useHouseholdToday`
- create mock `useRewardsWeek`
- create mock `useConnectorsHealth`
- create mock `useCalendarExports`
- create mock `useControlPlaneSummary`

This lets the UI lane move immediately and swap to live data later.

### Work packet I — hardening
- loading states
- empty states
- error states
- refresh / retry affordances
- optimistic completion only where safe
- narrow-width and large-text behavior
- basic accessibility and keyboard / assistive compatibility where applicable

## What to lift vs what to rewrite

### Lift directly from the product requirements
Lift from `family_chore_system.md`:
- routine and chore structure
- due times
- odd/even assignment logic presentation
- Power 60 and poop-patrol visibility
- Daily Win and payout framing
- standards-of-done detail

Lift from `scout_external_data_roadmap.md`:
- Hearth is display only
- Google Calendar is the scheduling spine
- rewards are computed in Scout
- connector health and control-plane visibility matter

Lift from the Rex session-doc pattern:
- full context packet format
- cross-lane dependency discipline
- merge gates
- reconciliation checklist

### Rewrite for Scout
- do not use a desktop right-rail assistant as the default assumption
- do not treat task completion as a separate admin page
- do not use Hearth task metaphors as the primary interaction model
- do not hardcode age as permission logic
- do not let calendar preview become the main task surface

## Status vocabulary

Use backend-defined values. Recommended baseline display mapping:

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

Do not invent parallel UI-only states unless the docs are updated.

## Non-goals for this session

Do not spend time on:
- backend migrations
- sync internals
- reward-calculation rules
- full Siri Shortcut plumbing if the repo is not ready
- deep meal-planning UX before household core is stable
- designing around Hearth as an interactive task app
- final design-system perfection
- broad health dashboards

## Cross-lane dependencies

### Session 2 dependencies
Need:
- `/api/me`
- `/api/family/context/current`
- `/api/household/today`
- `/api/rewards/week/current`
- `/api/connectors`
- `/api/connectors/health`
- `/api/calendar/exports/upcoming`
- `/api/control-plane/summary`

Until Session 2 lands:
- use mock hooks and sample payloads from this doc
- do not freeze a different contract in UI code
- keep the swap from mocks to live data trivial

### Session 1 continuity
This lane should still respect the Session 1 foundation direction. If UI work reveals a contract issue, update:
- this session doc
- `scout_external_data_roadmap.md`
- the next session handoff
- `scout_session_2_canonical_household_and_connectors.md`

## Merge gates for this lane

### Gate A — shell freeze
- the app has a real operating surface
- Today is the default entry point
- mocks can drive the UI before backend completion

### Gate B — household-ops freeze
- morning / after-school / evening blocks render clearly
- standalone chores and weekly items render clearly
- completion flows are usable
- the UI no longer depends on Hearth for task interaction

### Gate C — contract freeze
- published API shapes are consumed as documented
- no frontend-only alternate contract has been introduced
- role-tier logic is backend-driven where permissions matter

### Gate D — demo readiness
- a parent can see household status
- a child can see what is due next
- a task can be completed through Scout
- rewards preview updates
- calendar-publication preview exists
- control-plane starter surfaces exist

## Definition of done for the first pass

This lane is considered done for the first merge if all of these are true:

- a real Scout shell or navigation structure exists
- Today is a usable household operating surface
- routine blocks render
- chores render
- completion UI exists
- rewards current-week UI exists
- calendar publication preview exists
- connector-health / control-plane starter surfaces exist
- mockable hooks exist for all published contracts
- no UI depends on Hearth as an interaction layer
- the structure can later absorb work context, budget context, meal planning, and travel-time surfaces without re-architecture

## Reconciliation checklist against the master roadmap

At the start and end of each work block, explicitly verify:

1. Is the implementation still aligned to:
   - Phase 1 UI layer
   - Phase 2 publication visibility
   - Phase 3 operating surface
   - Phase 4 rewards UI
   - later support for Phase 5 through Phase 9

2. Has any UI decision violated the locked boundary?
   - Scout owns task logic
   - Hearth is display only
   - Google Calendar is publication spine
   - Greenlight is payout-facing only
   - task completion happens in Scout

3. Did any code reintroduce structural mistakes?
   - Hearth as the task app
   - calendar preview as the only household UI
   - age-only permissions
   - desktop-first layout assumptions overriding iOS reality

4. If a contract changed, was the change reflected in:
   - this session doc
   - `scout_external_data_roadmap.md`
   - the next handoff
   - `scout_session_2_canonical_household_and_connectors.md`

## Suggested end-of-session status note

Use this template in the parallel chat when closing a work block:

```md
### Scout Session 3 status
Completed:
- ...

In progress:
- ...

Blocked by Session 2:
- ...

Contracts changed:
- ...

Roadmap reconciliation:
- Still aligned to Phase 1-UI / 2 / 3 / 4 / later 5-9 support
- Drift introduced: yes/no
- If yes, updated docs: yes/no
```
