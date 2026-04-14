# Scout External Data and Connector Roadmap

Version: v1.0  
Status: Working roadmap  
Owner: Scout product  
Scope: Connector foundation, external data feeds, and the first dependent capabilities they unlock

## Architecture update that overrides earlier language

A prior handoff described Hearth as an always-on display and kids chore terminal. That is no longer the operating model.

Current product boundary:
- Scout is the system of record for chores, routines, task generation, task completion, standards of done, reminders, Daily Win scoring, and allowance logic.
- Google Calendar is the scheduling spine.
- Hearth is display only, via the calendar lane.
- Rex is inbound only.
- YNAB remains the financial engine.
- Greenlight is the payout and allowance-facing rail, not the rules engine.
- Apple Health and Nike Run Club are read-only context feeds in v1.
- Google Maps is an enrichment service.
- Exxir is decision-gated and should not be built unless it adds a signal Rex does not already provide.

## Why this roadmap exists

Scout should become the orchestration and intelligence layer for the family. The external systems around it should keep doing the jobs they already do well:
- Google Calendar for time
- Hearth for wall display
- Rex for work context
- YNAB for money context
- Greenlight for settlement and allowance visibility
- Apple Health and Nike Run Club for activity context
- Google Maps for travel-time realism

Scout should not become a second copy of each of those systems. It should normalize their signals, combine them with Scout-native household logic, and turn that into useful actions.

## Program-level goals

By the end of this roadmap, Scout should be able to:
1. Own the household operating system for chores and routines.
2. Publish household schedule blocks to Google Calendar for family visibility and Hearth display.
3. Compute Daily Wins and weekly allowance outcomes directly from Scout completion data.
4. Become work-aware through Rex and budget-aware through YNAB.
5. Use those signals to power smarter weekly planning, meal planning, and logistics.
6. Surface all of this through iOS-native delivery: push notifications, Shortcuts, widgets, and lock-screen style actions.

## Source-of-truth map

### Scout-native domains
Scout is the source of truth for:
- Families and family members
- Household rules
- Routine templates and routine steps
- Chore templates and task occurrences
- Completion history
- Standards of done
- Reward policies and Daily Win logic
- Allowance calculation results
- Notification logic
- Meal-planning outputs

### External systems
External systems remain the source of truth for:
- Google Calendar: calendar events and shared time surfaces
- Hearth: passive family display via calendar sync
- Rex: work obligations and work urgency inputs
- YNAB: budget categories, balances, targets, and bills context
- Greenlight: payout-facing visibility and balance destination
- Apple Health: health/activity records
- Nike Run Club: workout records and run-specific detail
- Google Maps: travel-time estimates
- Exxir: optional work signal if later justified

## Principles for every connector

A connector is not complete when authentication works. A connector is complete when it has:
- account linking
- backfill
- ongoing sync
- freshness tracking
- retry and repair paths
- disable and reconnect controls
- normalized internal objects
- at least one meaningful end-user outcome in Scout

Every connector must also declare:
- sync direction
- entity coverage
- cadence
- conflict policy
- provenance rules
- access model
- owner of final truth when data conflicts

## Connector tiers

### Tier 1: build first
- Google Calendar
- iCal / Hearth display lane
- Greenlight

### Tier 2: build after household core is live
- Rex
- YNAB

### Tier 3: enrichment after time and money are stable
- Google Maps
- Apple Health
- Nike Run Club

### Tier 4: decision gate
- Exxir

## Foundational platform work that must exist before connector sprawl

### Data foundation
The initial foundation should include the previously named tables:
- families
- family_members
- user_accounts
- sessions
- role_tiers
- role_tier_overrides
- connector_mappings
- connector_configs

Scout then needs native household tables on top of that foundation:
- household_rules
- routine_templates
- routine_steps
- task_templates
- task_assignment_rules
- task_occurrences
- task_completions
- standards_of_done
- reward_policies
- allowance_periods
- allowance_results
- calendar_exports
- sync_jobs
- notification_rules
- delivery_events

### Connector platform requirements
The connector platform should provide:
- OAuth and credential storage abstraction
- connector registry
- sync orchestration jobs
- external ID mapping through connector_mappings
- per-connector config in connector_configs
- normalization pipelines
- stale-data detection
- observability and audit trail
- manual resync tools
- connector-level feature flags

### Internal normalized objects
Regardless of source, Scout should normalize into:
- person
- household event
- time block
- routine block
- task occurrence
- completion event
- reward ledger entry
- budget snapshot
- meal plan
- grocery list
- workout / activity event
- travel estimate

## 24-week roadmap

---

## Phase 0: Weeks 1 to 2
## Foundation reset and connector platform

### Objective
Create the data model and connector platform that let Scout own chores natively while keeping all external integrations clean and maintainable.

### Deliverables
- Foundation + Connectors ERD
- Scout-native household ERD extension
- connector registry spec
- normalized object contract
- connector lifecycle states
- sync job framework
- audit trail model
- stale-data model

### Required implementation details
- Follow the existing Rex-style convention of keeping external IDs out of domain tables and inside connector_mappings.
- Add per-connector configuration records in connector_configs.
- Establish role and permissions boundaries before any user-specific or kid-specific delivery flows are built.
- Create the first live connector skeleton against Google Calendar, even if it initially syncs a small subset of event data.

### Dependencies
None. This is the prerequisite for nearly everything else.

### Exit criteria
- One family can be created with family members and roles.
- One connector account can be linked and stored safely.
- One external object can be mapped to an internal normalized object.
- One sync job can run end to end and record freshness.

---

## Phase 1: Weeks 3 to 5
## Scout-native chores and routines engine v1

### Objective
Build the household operating system inside Scout so chores no longer depend on Hearth task logic.

### Functional scope
Model and generate:
- morning routines
- after-school routines
- evening routines
- ownership chores
- odd/even rotating chores
- dog-walk rules
- Saturday Power 60
- weekly rotation logic for backyard cleanup assignments
- standards of done
- completion timestamps
- late / missed logic

### Product rules to encode
- one owner per task
- finishable lists
- explicit standards of done
- quiet enforcement
- one reminder max per task block unless manually escalated

### Deliverables
- routine template engine
- task template engine
- recurrence and rule engine
- completion tracking UI
- parent household dashboard
- kid-friendly task surfaces in Scout
- Daily Win computation pipeline

### Dependencies
Phase 0 completed.

### Exit criteria
- Scout can generate a full week of chores and routines for all children.
- Scout can record completions and misses.
- Scout can compute Daily Wins from real completion data.
- Hearth is no longer required for chore logic.

---

## Phase 2: Weeks 6 to 7
## Google Calendar connector and Hearth display lane

### Objective
Use Google Calendar as the family schedule spine and the publication path for Hearth display.

### Scope
Build Google Calendar read and write support for:
- calendar discovery and selection
- Scout-managed calendar creation
- event normalization
- recurring events and exceptions
- all-day events
- locations
- event ownership
- imported vs Scout-generated event separation

### Publication strategy
Do not publish every micro-task as a standalone calendar event.
Publish household anchor blocks such as:
- Morning Routine
- After School Closeout
- Dog Walk Window
- Evening Reset
- Power 60
- family summary blocks if useful

This keeps the calendar readable and allows Hearth to act as an ambient household display instead of a cluttered task dump.

### Deliverables
- Google Calendar OAuth
- calendar selection flow
- event normalization service
- calendar export service for Scout-generated blocks
- iCal-compatible publication path for Hearth consumption
- conflict detection for Scout-generated time blocks

### Dependencies
Phase 0 and Phase 1 completed.

### Exit criteria
- Scout can read the family’s key calendar surfaces.
- Scout can publish a full week of household time blocks.
- Hearth can display Scout-managed calendar blocks with no manual entry.

---

## Phase 3: Weeks 8 to 9
## Notifications, actions, widgets, and operating surface

### Objective
Make Scout usable as the family’s day-to-day operating surface on iOS.

### Scope
Build:
- daily agenda widget
- what-is-next widget
- parent overdue summary
- bedtime completion summary
- push notifications for active blocks
- Siri Shortcut for household status
- one-tap mark-complete actions
- parent review action for missed items

### Dependencies
Phase 1 and Phase 2 completed.

### Exit criteria
- A parent can run the household from Scout without needing Hearth for task interaction.
- Daily summary and completion flows are usable from lock screen, widgets, or Shortcuts.

---

## Phase 4: Weeks 10 to 11
## Greenlight connector and payout settlement

### Objective
Keep the reward rules in Scout and use Greenlight as the payout rail or allowance-facing endpoint.

### Scope
Scout should compute:
- baseline allowance outcomes
- Daily Win percentages
- weekly payout amounts
- missed-requirement explanations
- extras and one-off jobs
- grading-period school rewards

Greenlight integration should support, depending on API feasibility:
- balance visibility
- approved payout sync
- payout export or manual review queue if direct sync is weak

### Deliverables
- reward policy engine
- weekly settlement calculation
- parent approval workflow
- Greenlight connector spike or production connector
- settlement ledger inside Scout

### Dependencies
Phase 1 completed. Phase 2 preferred but not strictly required.

### Exit criteria
- Scout can calculate exactly what each child earned for a week.
- A parent can approve or review payouts.
- Greenlight is either integrated or bridged through a workable operational path.

---

## Phase 5: Weeks 12 to 14
## Rex inbound connector and work-aware planning

### Objective
Make Scout aware of work load so it can plan family operations around real constraints.

### Hard rule
Rex is inbound only in v1.

### Scope
Pull only the fields needed for family planning:
- meetings
- work blocks
- deadline clusters
- travel-affecting commitments
- urgency indicators
- optional summarized project pressure signal

### What not to do
- do not mirror all Rex objects into Scout
- do not write back to Rex
- do not make Scout a second work-management app

### Deliverables
- Rex connector
- work-load normalization layer
- family-planning impact rules
- protected-family-window logic
- overloaded-evening detection

### Dependencies
Phase 0 completed. Calendar integration strongly preferred.

### Exit criteria
- Scout recommendations change when Rex work pressure changes.
- Heavy work days cause different household timing suggestions than light work days.

---

## Phase 6: Weeks 15 to 17
## YNAB connector and budget-aware household planning

### Objective
Make Scout money-aware without replacing YNAB.

### Scope
Pull:
- grocery category status
- upcoming bills
- category balances relevant to household planning
- savings-plan progress
- monthly targets if needed
- discretionary room for optional spending

### What Scout should do with it
- adjust grocery planning
- surface bill-aware reminders
- flag spending-sensitive weeks
- inform home maintenance timing
- influence extras / reward decisions if desired

### Deliverables
- YNAB connector
- budget snapshot model
- bill reminder logic
- budget-aware planning prompts
- category-based household insight cards

### Dependencies
Phase 0 completed.

### Exit criteria
- Scout can support weekly planning without the user opening YNAB for routine household questions.
- Grocery and bill awareness are visible inside Scout.

---

## Phase 7: Weeks 18 to 19
## Meal-planning engine powered by connected data

### Objective
Use calendar and budget context to generate a weekly meal plan, Sunday prep plan, and store-split grocery list.

### This is not a connector, but it depends on connectors
Meal planning should consume:
- calendar load from Google Calendar
- budget constraints from YNAB
- future pantry input if added later
- household preferences and guest constraints

### Output standard
Every weekly meal-planning run should produce:
- dinners by night
- breakfast plan
- lunch plan
- snacks
- Sunday batch cook plan for a 2 to 3 hour window
- grocery list split by Costco vs secondary store

### Deliverables
- weekly meal-planning workflow
- clarifying-question flow before plan generation
- plan approval loop
- grocery-list generator
- calendar-aware dinner complexity rules

### Dependencies
Calendar and YNAB should both be live.

### Exit criteria
- Scout can generate a full weekly meal package that matches the required output format.
- The plan changes intelligently when the family calendar changes.

---

## Phase 8: Weeks 20 to 21
## Google Maps travel-time enrichment

### Objective
Make Scout’s schedule realistic by accounting for travel.

### Scope
- leave-by time calculation
- pickup and dropoff buffer estimates
- work-to-home transition timing
- route-aware alerts
- location-based timing adjustments for family logistics

### Deliverables
- Google Maps connector / service integration
- travel estimate model
- leave-by notification rules
- transition-aware schedule suggestions

### Dependencies
Calendar events must already carry reliable time and location data.

### Exit criteria
- Scout can produce accurate leave-by notifications for recurring family logistics.
- Timing recommendations become more realistic and reduce schedule misses.

---

## Phase 9: Weeks 22 to 23
## Apple Health and Nike Run Club

### Objective
Add read-only activity context so Scout can make better planning recommendations.

### Scope
Normalize into one internal fitness context layer:
- workouts completed
- activity volume
- run details where useful
- simple recovery-aware hints
- family challenge support later if desired

### Guardrails
- do not build a medical dashboard
- do not lead with quantified-self complexity
- use only the amount of activity context needed to improve scheduling and recommendations

### Deliverables
- Apple Health connector
- Nike Run Club connector
- fitness normalization layer
- workout-aware planning prompts
- optional family challenge scaffolding

### Dependencies
None technically, but these should land after time and money context are stable.

### Exit criteria
- Scout makes different timing suggestions based on recent activity or workouts.
- Workout data has at least one meaningful effect on family planning.

---

## Phase 10: Week 24
## Exxir decision gate and optional narrow connector

### Objective
Decide whether Exxir adds unique signal beyond Rex and Google Calendar.

### Decision test
Only build Exxir if it adds one or more of the following that materially improve Scout:
- communication pressure not visible in Rex
- delegated-work urgency not visible in Rex
- inbox-driven interruption signal
- another unique planning signal that changes family recommendations

### What not to do
- do not build Exxir because it exists
- do not duplicate Rex scope
- do not expand the roadmap with ambiguous work context

### Deliverables
Either:
- a written decision to defer Exxir from v1

or
- a narrow Exxir connector with one specific use case and one specific user-facing outcome

### Exit criteria
- Exxir is either clearly cut from v1 or clearly justified with a bounded implementation plan.

---

## Connector-by-connector implementation notes

## Google Calendar
### Role in system
Scheduling spine and publication rail.

### Sync direction
Read and write.

### Internal objects affected
household event, time block, calendar export.

### First user-facing wins
- family agenda view
- household time blocks on calendar
- Hearth display lane
- schedule conflict detection

### Main risks
- recurrence complexity
- duplicate events
- unclear ownership between imported events and Scout-generated events

## Hearth
### Role in system
Display only.

### Sync direction
No chore logic sync. Calendar-fed display lane only.

### Internal objects affected
None as a system of record. It is a presentation endpoint.

### First user-facing wins
- ambient wall display of Scout-generated household blocks

### Main risks
- calendar clutter if Scout exports too many micro-events

## Greenlight
### Role in system
Payout rail and allowance-facing surface.

### Sync direction
Likely Scout to Greenlight plus optional balance/status read.

### Internal objects affected
allowance results, settlement ledger.

### First user-facing wins
- weekly payout preview
- approval flow
- child-facing earned amount visibility

### Main risks
- API limitations
- settlement edge cases

## Rex
### Role in system
Inbound work context.

### Sync direction
Read only.

### Internal objects affected
work-pressure summary, scheduling constraints.

### First user-facing wins
- better evening planning
- family-block protection
- overload warnings

### Main risks
- importing too much
- overfitting Scout to work detail it does not need

## YNAB
### Role in system
Budget context.

### Sync direction
Read only in v1.

### Internal objects affected
budget snapshot, bill awareness, savings context.

### First user-facing wins
- grocery awareness
- bill reminders
- budget-aware weekly planning

### Main risks
- turning Scout into a budget clone
- category mapping complexity

## Google Maps
### Role in system
Travel-time enrichment.

### Sync direction
Request/response service use.

### Internal objects affected
travel estimate.

### First user-facing wins
- leave-by alerts
- pickup timing
- realistic transition planning

### Main risks
- poor location quality in calendar events
- over-notification

## Apple Health
### Role in system
General activity and health context.

### Sync direction
Read only.

### Internal objects affected
activity event, readiness hints.

### First user-facing wins
- workout-aware planning
- light recovery-aware prompts

### Main risks
- privacy expectations
- doing too much too early

## Nike Run Club
### Role in system
Run-specific workout context.

### Sync direction
Read only.

### Internal objects affected
workout event.

### First user-facing wins
- post-run timing suggestions
- training-aware planning

### Main risks
- duplicate overlap with Apple Health

## Exxir
### Role in system
Optional work signal beyond Rex.

### Sync direction
TBD, likely read only.

### Internal objects affected
Only if a unique signal is found.

### First user-facing wins
None until a concrete use case is defined.

### Main risks
- duplicate scope with Rex
- roadmap creep

## Release plan

### Release 1: End of Week 7
Scout Household Core
- Scout-native chores and routines engine
- Google Calendar connector
- Hearth display lane

### Release 2: End of Week 11
Scout Daily Operations and Rewards
- widgets and push-based operating surface
- Daily Win logic
- allowance calculation
- Greenlight payout path

### Release 3: End of Week 17
Scout Context-Aware Planning
- Rex inbound connector
- YNAB connector
- work-aware and budget-aware planning

### Release 4: End of Week 24
Scout Family OS v1
- meal planning
- Google Maps enrichment
- Apple Health and Nike Run Club
- Exxir decision resolved

## Critical path

The critical path is:
1. Foundation and connector platform
2. Scout-native chores engine
3. Google Calendar publication
4. iOS operating surface
5. Greenlight settlement
6. Rex and YNAB context
7. meal planning and logistics enrichment

Anything that delays the first five items delays the product more than any later enrichment work.

## What should not happen early

Do not:
- rebuild Hearth task logic
- make Hearth two-way
- write back to Rex
- rebuild YNAB inside Scout
- build health dashboards before time and money context are stable
- integrate Exxir before proving unique value
- export every micro-task to calendar

## Immediate next sprint

### Sprint objective
Lock the corrected architecture and get the first live connector path running.

### Sprint deliverables
- revised ERD with Scout-native chores ownership
- connector registry and mapping strategy
- Google Calendar connector skeleton
- first routine templates in Scout
- first generated household week inside Scout

### Sprint acceptance criteria
- Scout owns chores in the data model and in the product flow.
- One family can generate a week of routines and tasks.
- One Google Calendar can connect and receive Scout-generated household blocks.
- Hearth can be treated as a downstream display surface rather than a task engine.

## Open decisions to resolve early

- exact Google Calendar topology: one shared family calendar vs multiple overlays
- how much Greenlight automation is actually possible through API or operational bridge
- whether kid-facing completion happens only in Scout or also through limited shared views
- whether meal planning should remain parent-review only or support direct edits inside Scout
- whether Apple Health and Nike Run Club should be merged into one visible fitness layer or stay hidden as context signals

## Success metrics

By the end of this roadmap, the product should be measurably better on:
- percent of household tasks completed on time
- number of parent reminders needed per day
- percent of weeks with auto-generated chore schedules
- percent of weeks with auto-calculated allowance results
- family calendar accuracy for household blocks
- meal-plan completion rate
- reduction in avoidable schedule misses caused by travel-time blind spots
- number of planning recommendations altered by real work or budget context

## Final recommendation

If tradeoffs are needed, protect the following sequence at all costs:
1. Scout-native chores and routines
2. Google Calendar and Hearth display lane
3. iOS daily operating surface
4. Greenlight settlement
5. Rex and YNAB
6. everything else

That order gets Scout to a real household operating system fastest.
