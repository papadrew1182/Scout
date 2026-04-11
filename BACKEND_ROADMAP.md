# Scout Backend Roadmap

## Status Legend
- DONE
- PARTIAL
- NEXT
- PLANNED
- BLOCKED

## 0. Foundation
Status: DONE

Includes:
- families
- family_members
- user_accounts
- sessions
- role_tiers
- role_tier_overrides
- connector_configs
- connector_mappings

Completed:
- schema
- migrations
- seeds
- backend scaffolding
- tests

## 1. Life Management
Status: DONE

Includes:
- routines
- routine_steps
- chore_templates
- task_instances
- task_instance_step_completions
- daily_wins
- allowance_ledger

Completed:
- schema
- migrations
- seeds
- backend scaffolding
- tests
- step completion rollup

Notes:
- currently the most complete vertical slice in Scout

## 2. Calendar / Scheduling
Status: DONE

Includes:
- events
- event_attendees

Completed in this package:
- schema (events + event_attendees)
- migration: 003_calendar.sql
- seed: 003_calendar_seed.sql
- ORM models
- Pydantic schemas
- service layer (CRUD + recurrence instance overrides)
- routes (events + attendees)
- recurrence handling via RRULE text field (application-side expansion)
- recurrence_parent_id edited-instance behavior with unique override constraint
- source tracking (scout | google_cal | ical) via CHECK constraint
- is_hearth_visible flag
- optional task_instance_id linkage
- connector_mappings pattern preserved (events use internal_table='events')
- minimal test scaffold

Notes:
- Recurrence expansion is intentionally NOT in the database. Application code
  expands RRULE strings and applies edited-instance overrides at query time.
- iCal connector support resolved by package 2.1 (migration 004).

## 2.1 Connector iCal Support (follow-up to Calendar)
Status: DONE

Completed in this package:
- migration: 004_connector_ical_support.sql
- extended connector_configs.connector_name CHECK to include 'ical'
- extended connector_mappings.connector_name CHECK to include 'ical'
- updated 003_calendar_seed.sql to insert the previously deferred iCal mapping
- regression test: tests/test_connector_ical.py

Notes:
- No ORM, schema, or service code changes required — both models use plain
  String fields with no Python-side enum. CHECK enforcement is database-only.

## 3. Meals
Status: DONE

Includes:
- meal_plans
- meals
- dietary_preferences

Completed in this package:
- schema (meal_plans + meals + dietary_preferences)
- migration: 005_meals.sql
- seed: 005_meals_seed.sql
- ORM models
- Pydantic schemas
- service layer (meal plans CRUD, meals CRUD with date/range filtering, dietary preferences CRUD)
- routes (/meal-plans, /meals, /members/{id}/dietary-preferences)
- weekly plan structure with Monday week_start CHECK
- meal_type CHECK in ('breakfast', 'lunch', 'dinner', 'snack')
- one-meal-per-type-per-day uniqueness
- meals can exist with or without a parent plan
- minimal test scaffold

Notes:
- Recipes, grocery lists, and nutrition tracking are intentionally out of scope.
- dietary_preferences is a thin hook table not yet referenced by meals.
  Future packages can add nutritional/restriction logic on top.
- "What are we eating today?" is a single indexed query:
  GET /families/{id}/meals?meal_date={today}

## 4. Parent Rewards / Allowance Management
Status: PARTIAL

What exists:
- daily_wins
- allowance_ledger
- payout endpoint
- parent UI shell

What’s missing on backend:
- school rewards / bonus / penalty backend actions if needed later

## 5. Personal Task Layer
Status: DONE

Includes:
- personal_tasks

Completed in this package:
- schema (personal_tasks)
- migration: 006_personal_tasks.sql
- seed: 006_personal_tasks_seed.sql
- ORM models
- Pydantic schemas
- service layer (CRUD, top-N, due-today, complete transition)
- routes (/personal-tasks with /top, /due-today, /{id}/complete)
- status CHECK ('pending', 'in_progress', 'done', 'cancelled')
- priority CHECK ('low', 'medium', 'high', 'urgent')
- completed_at consistency CHECK (set iff status = done)
- optional event_id linkage to calendar events
- "Top 5 Tasks" query: incomplete + priority-then-due ordering
- minimal test scaffold

Notes:
- Intentionally separate table from task_instances. Routines/chores remain
  the child execution model; personal_tasks serves adult/general use.
- No subtasks, dependencies, or project hierarchy. Out of scope.
- The Top N service supports any limit (default 5) and any assigned member.

## 6. Second Brain
Status: DONE

Includes:
- notes

Completed in this package:
- schema (notes)
- migration: 007_second_brain.sql
- seed: 007_second_brain_seed.sql
- ORM models
- Pydantic schemas
- service layer (CRUD, recent, ILIKE search, archive/unarchive)
- routes (/notes with /recent, /search, /{id}/archive, /{id}/unarchive)
- title-not-blank CHECK
- per-member ownership + family scoping
- optional category text field
- minimal test scaffold

Notes:
- Search is ILIKE on title + body. No full-text index, no vector store.
- No tags, no inter-note links, no attachments. Intentionally minimal.
- is_archived enables soft retirement without deletion.
- Archived notes are excluded from default list and recent queries unless
  explicitly requested via include_archived=true.

## 7. Finance
Status: DONE

Includes:
- bills

Completed in this package:
- schema (bills)
- migration: 008_finance.sql
- seed: 008_finance_seed.sql
- ORM models
- Pydantic schemas
- service layer (CRUD, upcoming/overdue/unpaid helpers, pay/unpay transitions)
- routes (/bills with /upcoming, /overdue, /unpaid, /{id}/pay, /{id}/unpay)
- status CHECK ('upcoming', 'paid', 'overdue', 'cancelled')
- source CHECK ('scout', 'ynab') for future YNAB connector compatibility
- amount_cents non-negative CHECK
- title-not-blank CHECK
- paid_at consistency CHECK (set iff status = paid)
- minimal test scaffold
- example connector_mappings rows linking YNAB-sourced bills to YNAB scheduled txn ids

Notes:
- No budget engine. No account reconciliation. No recurring expansion —
  a recurring monthly bill is multiple one-off bill rows.
- External IDs (e.g., YNAB transaction ids) live in connector_mappings only.
- Overdue retrieval surfaces both bills explicitly flagged 'overdue' and
  bills still 'upcoming' whose due_date has passed.

## 8. Health / Fitness
Status: DONE

Includes:
- health_summaries
- activity_records

Completed in this package:
- schema (health_summaries + activity_records)
- migration: 009_health_fitness.sql
- seed: 009_health_fitness_seed.sql
- ORM models
- Pydantic schemas
- service layer (CRUD, latest summary, recent activity, list filters)
- routes (/health/summaries with /latest, /health/activity with /recent)
- source CHECK ('scout', 'apple_health', 'nike_run_club') for both tables
- activity_type CHECK ('run','walk','bike','swim','strength','yoga','other')
- ended_at >= started_at CHECK on activity_records
- non-negative numeric CHECKs on steps, active_minutes, resting_heart_rate,
  sleep_minutes, weight_grams, duration_seconds, distance_meters, calories
- one-summary-per-member-per-date uniqueness
- minimal test scaffold
- example connector_mappings row linking an Apple Health summary

Notes:
- All metric columns are nullable so partial data from a single source is fine.
- No workout-program engine. No nutrition tracking. No goals/streaks logic.
- No sync engines yet — source field is for future connector compatibility only.
- A future package can add rollups (weekly/monthly summaries) and aggregate
  family-level views without changing this schema.

## 9. Integrations
Status: PARTIAL

Includes:
- shared upsert helper (services/integrations/base.py)
- Google Calendar v1 ingestion
- YNAB v1 ingestion
- Apple Health stub (501)
- Nike Run Club stub (501)
- Internal ingestion routes

Completed in this package:
- generic ingestion entry point (upsert_via_mapping) backed by connector_mappings
- source-of-truth enforcement (SourceConflictError when external sync targets a scout row)
- Google Calendar payload schema + ingest_event + ingest_events_batch
- YNAB payload schema + ingest_scheduled_transaction + batch
- POST /integrations/google-calendar/ingest
- POST /integrations/ynab/ingest
- duplicate prevention via existing uq_connector_mappings_external constraint
- mapping-orphan recovery (mapping points at deleted internal_id → fresh create)
- YNAB ingestion preserves Scout-side state (status, paid_at) on re-ingestion
- minimal test scaffold (Google Calendar create / update / source conflict / dedup,
  YNAB create / update preserving paid status / dedup, tenant isolation)

What remains (intentionally not built):
- real OAuth flows for any connector
- real API clients (Google API, YNAB API)
- webhook receivers
- background sync schedulers / queues
- delta sync (incremental fetch since last sync)
- conflict resolution beyond source-of-truth (e.g., concurrent edit merging)
- Apple Health full ingestion
- Nike Run Club full ingestion (also requires connector_mappings CHECK extension)
- iCal feed parsing
- Hearth bridge
- batch error handling (currently each payload is independent; one bad payload
  in a batch raises and rolls back that single ingestion)
- audit log of ingestion operations
- rate limiting / retry logic
- credential rotation handling

## 10. Intelligence Layer
Status: DONE

Includes:
- ai_conversations
- ai_messages
- ai_tool_audit

Completed in this package:
- schema (ai_conversations + ai_messages + ai_tool_audit)
- migration: 010_ai_orchestration.sql
- ORM models (AIConversation, AIMessage, AIToolAudit)
- Anthropic provider abstraction with tool-use support
- Role-aware context loader (adult/child/parent surface differentiation)
- System prompt assembly with prompt injection resistance
- 17-tool registry wrapping existing services (no domain logic duplication)
- Tool permission enforcement by role + surface
- Write confirmation enforcement for shared-data-affecting tools
- One-tool-at-a-time execution with bounded 5-round loop
- Full audit logging for every tool execution (success/error/denied/confirmation)
- Chat orchestration engine with conversation persistence
- Daily brief, weekly plan, and staple meal suggestion endpoints
- Pydantic request/response schemas
- Routes: POST /api/ai/chat, POST /api/ai/brief/daily, POST /api/ai/plans/weekly,
  POST /api/ai/meals/staples, GET /api/ai/conversations, GET /api/ai/conversations/{id}/messages,
  GET /api/ai/audit
- Tests: tool permissions, execution, confirmation, family isolation, audit logging,
  context loading, prompt assembly, conversation state

Notes:
- Provider is Anthropic-first. Abstraction is clean enough for a second provider.
- Tool execution is synchronous, one call at a time, max 5 rounds per chat turn.
- Child surface is read-only (no write tools allowed).
- External text in notes/events/connectors is treated as DATA in the prompt, not instructions.
- Notification delivery is logged but not yet implemented (send_notification_or_create_action).
- No background jobs, no autonomous loops, no real-time streaming in v1.

## Suggested Build Order
1. Foundation
2. Life Management
3. Calendar / Scheduling
4. Meals
5. Parent reward-management backend refinements if needed
6. Personal task layer
7. Second Brain
8. Finance
9. Health / Fitness
10. Integration engines
11. Intelligence layer orchestration

## Update Rules
After each backend package:
- update the status of the affected section
- add a short “Completed in this package” bullet list
- move the next backend package to Status: NEXT
- do not rewrite unrelated sections
- preserve history and clarity
- keep this roadmap practical, not aspirational
