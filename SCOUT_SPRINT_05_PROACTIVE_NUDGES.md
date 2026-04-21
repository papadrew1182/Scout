> **Implementation plan:** `docs/plans/2026-04-21-sprint-05-plan.md`
> (revised after external review; supersedes the original Phase 1 plan).

---
# Scout Sprint 05 — Proactive Nudges Engine

**Ref commit:** latest `main` at time of execution (post-Sprint 04 P2 merge `16325d3f`).
**Prepared:** 2026-04-21
**Intended audience:** Claude Code running against the Scout monorepo
**Precondition:** Sprint 04 Phases 1 + 2 merged to `main` (they are).
**Scope decided via brainstorming in the interactive session on 2026-04-21.**

## 1. Why this sprint exists

Scout today only acts when asked. The `morning_brief` job already fires daily summaries, but everything else is on-demand: a family member has to open the app, go find an overdue task, notice an upcoming event. Sprint 04 Phase 2 shipped a `proactivity` setting per member (quiet / balanced / forthcoming) that does nothing yet.

Sprint 05 makes Scout reach out at the right moment — across Inbox and push — respecting per-member proactivity, quiet hours, and digest batching, with optional personalized copy and admin-configurable custom rules.

## 2. Scope

All items listed below are in scope. The sprint is split into five phases that MUST ship in order. Phases 1–3 are the engine; Phase 4 is the admin rule surface; Phase 5 is AI-driven discovery. Each phase lands as its own PR so review + deploy stay tractable.

### Phase 1 — Core engine (built-in triggers + Inbox + push)

Three built-in trigger scanners, Action Inbox delivery, push delivery when a device exists, proactivity gate, de-duplication.

### Phase 2 — Quiet hours + batching

Time-of-day gate per family (and optional per-member override). Dispatch batching inside a 10-minute window so multiple triggers collapse into one Inbox / push item.

### Phase 3 — Personalized copy

Use the member's personality preamble (Sprint 04 Phase 2) to compose the nudge message via the existing AI orchestrator. Fall back to fixed templates when AI is unavailable, over cost cap, or moderation-blocked.

### Phase 4 — Admin rule engine

CRUD for custom trigger rules (`when X, nudge Y at Z lead time`). Extends the scanner to read rule rows in addition to the built-in triggers.

### Phase 5 — AI-driven trigger discovery

A scheduled AI analysis pass that proposes new nudges beyond the hardcoded + admin-configured rules. Rate-limited, cost-capped, dedupes against the built-in scanners.

## 3. Operating constraints

Inherited from Sprint 04 plan § Operating constraints. Specifically:

- `scout.*` schema, UUID PKs, `timestamptz`, `is_`/`has_` booleans, no external IDs on core tables.
- Never edit existing migrations. New migrations land at `backend/migrations/NNN_*.sql` mirrored to `database/migrations/`.
- Every mutating endpoint calls `actor.require_permission("feature.action")`. Public endpoints annotated `# noqa: public-route`.
- Role tiers are UPPERCASE (`PRIMARY_PARENT / PARENT / TEEN / CHILD / YOUNG_CHILD`, plus `DISPLAY_ONLY` excluded from user-facing grants by convention).
- Use the existing in-process scheduler at `backend/app/scheduler.py`. Add a new job; do not start a second scheduler.
- SQL params `$1` / `$2` asyncpg style where asyncpg is used; SQLAlchemy `text(":name")` binds where the rest of the route code uses SQLAlchemy.
- No em dashes in produced content.
- `node scripts/architecture-check.js` runs at end of each phase. New WARNs are blockers.

## 4. Phases in detail

### Phase 1 — Core engine

Migration `049_nudge_engine.sql`:

- `scout.nudge_dispatches`
  - `id uuid PK`
  - `family_member_id uuid FK` → `family_members(id)`
  - `trigger_kind text` CHECK IN (`overdue_task`, `upcoming_event`, `missed_routine`, `custom_rule`, `ai_suggested`)
  - `trigger_entity_kind text` — source row kind (e.g., `personal_task`)
  - `trigger_entity_id uuid` — source row id
  - `proactivity_at_dispatch text` — snapshot of the member's setting
  - `lead_time_minutes int`
  - `scheduled_for timestamptz`
  - `dispatched_at timestamptz nullable`
  - `parent_action_item_id uuid FK nullable`
  - `push_delivery_id uuid FK nullable`
  - `delivered_channels jsonb default '[]'::jsonb` — e.g. `["inbox","push"]`
  - `dedupe_key text` — `{member_id}:{trigger_kind}:{trigger_entity_id}:{scheduled_for::date}`
  - `severity text` CHECK IN (`low`,`normal`,`high`) default `normal`
  - `suppressed_reason text nullable` — e.g. `quiet`, `quiet_hours`, `deduped`
  - `created_at, updated_at timestamptz`
  - UNIQUE `(dedupe_key)`
  - INDEX `(family_member_id, scheduled_for DESC)`
  - INDEX `(scheduled_for) WHERE dispatched_at IS NULL`
- Permission key `nudges.view_own` for all user tiers (`YOUNG_CHILD`, `CHILD`, `TEEN`, `PARENT`, `PRIMARY_PARENT`).

`backend/app/services/nudges_service.py`:

- `scan_triggers(db, now_utc)` — calls the three scanners, returns a list of `NudgeProposal` dataclasses.
- `scan_overdue_tasks(db, now_utc)`
- `scan_upcoming_events(db, now_utc, lead_by_proactivity)`
- `scan_missed_routines(db, now_utc)`
- `apply_proactivity(proposals, now_utc)` — maps `quiet` → drop, `balanced` → default lead, `forthcoming` → 2× earlier lead.
- `dispatch(db, proposals, now_utc)` — for each proposal: compute `dedupe_key`; upsert `nudge_dispatches` row; compose body (fixed template in Phase 1); call `push_service.send_push` if member has an active device; write `parent_action_items` row with `route_hint`.
- Idempotent on repeat ticks via `dedupe_key` unique constraint. Rows already marked `dispatched_at` are never re-sent.

Scheduler wiring in `backend/app/scheduler.py`:

- Add `_run_nudge_scan(db, now_utc)` that calls `scan_triggers` → `apply_proactivity` → `dispatch`.
- Runs each tick alongside `_run_morning_brief` and `_run_anomaly_scan` guarded by `try/except` with `logger.exception` so one nudge failure doesn't kill the tick.

Fixed template copy for Phase 1:

```
overdue_task    → "Reminder: {task_title} was due at {due_time}."
upcoming_event  → "Heads up: {event_title} at {start_time}."
missed_routine  → "{routine_name} wasn't checked off this morning."
```

Acceptance:

- [ ] Migration applied, permission key registered for all user tiers.
- [ ] Scheduler registers `nudge_scan` and it runs on the tick without affecting existing jobs.
- [ ] Scanners return proposals for overdue / upcoming / missed matching fixtures.
- [ ] Proactivity `quiet` suppresses; `forthcoming` produces lead 2× earlier.
- [ ] First dispatch writes an Inbox row and a push_delivery row when a device exists.
- [ ] Second tick for the same trigger does NOT re-dispatch (dedupe holds).
- [ ] Smoke spec asserts the dispatch shape via API.
- [ ] Arch check clean.

### Phase 2 — Quiet hours + batching

Migration `050_nudge_quiet_hours_and_batching.sql`:

- `scout.quiet_hours_family`
  - `id uuid PK`
  - `family_id uuid FK UNIQUE`
  - `start_local_minute int` — minutes from local midnight; default 22*60
  - `end_local_minute int` — default 7*60
  - `created_at, updated_at`
- Optional per-member override stored as `member_config['nudges.quiet_hours']` (JSON `{start_local_minute, end_local_minute}`).
- Extend `nudge_dispatches.delivered_channels` usage — batched dispatches point at a single Inbox row; each `nudge_dispatches` row still records its own dedupe.

Service updates:

- `should_suppress_for_quiet_hours(member, now_utc, family)` — compute local time from `family.timezone` (pytz). If inside window: low severity → drop with `suppressed_reason='quiet_hours'`; high severity → deliver anyway (safety-critical); normal severity → hold until window end.
- `batch_proposals(proposals, window_minutes=10)` — groups proposals per `family_member_id` within the window; emits one composite dispatch per group with a summary body (`"You have 3 items to check: {title_1}, {title_2}, and 1 more."`), plus individual `nudge_dispatches` rows all pointing at the same Inbox row id.

New route `GET /api/nudges/me` (auth only, needs `nudges.view_own`) — last 20 dispatches for the caller. Used by a `/settings/ai` Nudges section.

New route `GET /api/admin/family-config/quiet-hours` + `PUT` — needs `quiet_hours.manage` (PARENT + PRIMARY_PARENT). Permission key introduced in this migration.

Frontend:

- `/settings/ai` gains a Recent nudges section reading `GET /api/nudges/me`.
- `/admin/scout-ai` gains a Quiet hours control (start / end inputs, family-wide).

Acceptance:

- [ ] Nudge scheduled inside the family quiet window with `normal` severity is held and fires at window end.
- [ ] `low` severity inside window is dropped with `suppressed_reason='quiet_hours'`.
- [ ] `high` severity inside window is delivered anyway.
- [ ] Three triggers for one member within a 10-min window collapse into one Inbox item and one push message.
- [ ] Per-member `quiet_hours` override in `member_config` takes precedence over family default.
- [ ] `/settings/ai` Recent nudges section shows the latest dispatches.
- [ ] `/admin/scout-ai` Quiet hours control saves and reads the family row.

### Phase 3 — Personalized copy

No migration.

Service update:

- `compose_body(db, proposal, resolved_personality)` in `nudges_service.py`.
- For each proposal (or batch summary), call `orchestrator.generate_nudge_body(resolved_personality, trigger_context)` — a thin wrapper around the existing `orchestrator.chat` path with a short system prompt including the member's personality preamble and a templated user turn describing the trigger context.
- Fallback to the Phase 1 fixed template when:
  - `settings.ai_available` is false
  - Current family has hit the weekly AI soft cap (reuse `build_usage_report` sentinel)
  - Moderation rejects the output
  - AI call raises or times out in < 3 seconds

Cap the AI call to ~80 output tokens; low-cost model (use `SCOUT_AI_CLASSIFICATION_MODEL` or a cheaper sibling).

Acceptance:

- [ ] Personalized copy is written into the Inbox + push body when AI is available.
- [ ] Fallback to the fixed template is exercised by a test that mocks an AI failure.
- [ ] Dispatched body respects member tone / vocabulary per a fixture test (assert substrings).
- [ ] Total AI token usage per tick is bounded (soft cap test).

### Phase 4 — Admin rule engine

Migration `051_nudge_rules.sql`:

- `scout.nudge_rules`
  - `id uuid PK`
  - `family_id uuid FK`
  - `name text`
  - `is_active boolean default true`
  - `source_kind text` CHECK IN (`sql_template`, `predicate`) — Phase 4 ships only `sql_template` (parameterized SQL that returns (`member_id`, `entity_id`, `entity_kind`, `scheduled_for`) rows). `predicate` is reserved for future Python predicates.
  - `template_sql text` — the parameterized query
  - `template_params jsonb` — binds available to the query (e.g., `now_utc`)
  - `trigger_kind text default 'custom_rule'`
  - `default_lead_time_minutes int default 0`
  - `severity text` CHECK IN (`low`,`normal`,`high`)
  - `created_by_family_member_id uuid FK`
  - `created_at, updated_at`
- Permission key `nudges.configure` for PARENT + PRIMARY_PARENT.

Scanner extension:

- `scan_rule_triggers(db, now_utc)` iterates active `nudge_rules`, runs each `template_sql` with `template_params`, emits proposals with `trigger_kind='custom_rule'`. SQL is only executable if it passes a safety check: SELECT-only, must reference one whitelisted table set, max rows capped at 200 per rule.
- Results flow through the same `apply_proactivity` → `dispatch` path.

Safety rails: rule SQL is validated by a small whitelist parser (sqlglot or a hand-rolled allowlist). Reject any `INSERT/UPDATE/DELETE/DDL/`function-call outside the allowlist.

Routes:

- `GET /api/admin/nudges/rules` — list family's rules.
- `POST /api/admin/nudges/rules` — create.
- `PATCH /api/admin/nudges/rules/{id}`
- `DELETE /api/admin/nudges/rules/{id}`
- All require `nudges.configure`.

Admin screen `scout-ui/app/admin/ai/nudges.tsx`:

- Lists rules; tap to edit.
- Textarea for `template_sql`, key/value rows for `template_params`, severity dropdown, default lead time.
- Saves on blur; shows a preview count of rows the rule would match right now (backend runs the SQL and returns a count).

Acceptance:

- [ ] Active rule's SQL template runs each tick and produces proposals matching the live state.
- [ ] Rule SQL validator rejects non-SELECT statements, writes to forbidden tables, and calls to forbidden functions (unit tested).
- [ ] Admin CRUD works; preview count endpoint returns sane numbers.
- [ ] Non-admin (TEEN) receives 403 on `/api/admin/nudges/rules`.
- [ ] Disabling a rule stops it firing on the next tick.

### Phase 5 — AI-driven trigger discovery

No migration.

Service:

- `backend/app/services/nudge_ai_discovery.py` — `propose_nudges(db, family_id, now_utc)` collects a compact family-state digest (upcoming events today, overdue items, recent chore misses) and calls the orchestrator with a prompt asking "what, if anything, is worth a nudge right now, and to whom".
- Output parsed into a bounded list of proposals with `trigger_kind='ai_suggested'`. Each proposal's `trigger_entity_id` can be `NULL` (AI-driven proposals may not correspond to a single row); in that case `dedupe_key` uses a hash of the composed body.
- Rate limit: one AI-discovery call per family per hour. Cost-cap: respect the weekly AI soft cap; skip discovery once the cap is hit.
- Proposals flow through `apply_proactivity` → `batch_proposals` → `dispatch` (so AI suggestions get batched, quiet-hours-gated, and personalized just like built-in ones).

Scheduler: `nudge_ai_discovery_tick` runs hourly, not on the 5-min tick.

Acceptance:

- [ ] AI discovery runs once per hour per family; a second call in the same hour is skipped.
- [ ] Discovery proposals are deduplicated against built-in scanner proposals (same trigger_entity_id on the same day doesn't double-fire).
- [ ] Discovery skips when weekly soft-cap hit.
- [ ] Output schema is validated (pydantic). Malformed AI output is dropped, not dispatched.
- [ ] Smoke test: mock discovery returns a known proposal; assert it lands in Inbox with `trigger_kind='ai_suggested'`.

## 5. Out of scope

Not in this sprint:

- Quiet-hours UI for kids editing their own override (admin only ships the family-wide control; per-member override editable only via direct `member_config` write or `/admin`).
- Custom nudge copy per rule (Phase 3 personalizes based on the member, not the rule).
- Email / SMS delivery channels. Inbox + push only.
- Rich push (images, action buttons).
- Snooze / reschedule actions from within the notification itself.
- Historical analytics (engagement rate per trigger kind, etc.).

## 6. Risks and trade-offs

- **AI cost.** Phase 3 (personalized copy) + Phase 5 (discovery) are the cost drivers. Both respect the existing weekly soft cap; both fall back to template / skip when capped.
- **Rule-engine SQL injection.** Phase 4 is a real concern. The SELECT-only whitelist parser is the critical safety control; reject rules that don't parse cleanly. Rule audit log is written to the standard audit surface.
- **Tick contention.** Adding nudge_scan to the 5-min tick increases per-tick work. Acceptance tests should include a tick under realistic family size (say 50 personal_tasks, 20 events) to confirm <10s tick time.
- **Personalized copy drift.** AI-composed bodies can subtly contradict member preferences over time. Mitigation: the composer receives the full preamble; tests assert substrings for a matrix of personalities.
- **Dedupe across Phase 5 and Phase 1.** AI discovery can propose a nudge for an entity already scanned by the built-in scanner. Mitigation: both paths write to the same `nudge_dispatches` table and share the `dedupe_key` unique constraint.

## 7. Amendments for Claude Code

If any body text above conflicts with this section, this section wins.

- Role tiers are UPPERCASE. `admin / parent_peer / teen / child / kid` are legacy aliases.
- Migration numbering: Phase 1 = 049, Phase 2 = 050, Phase 4 = 051. Phase 3 and Phase 5 have no migrations.
- Permission keys added across phases: `nudges.view_own` (P1), `quiet_hours.manage` (P2), `nudges.configure` (P4).
- Phase 2 starts only after Phase 1 is merged to `main` and Railway + Vercel deploys are green.
- Phase 3 starts only after Phase 2 is merged + deployed.
- Phase 4 starts only after Phase 3 is merged + deployed.
- Phase 5 starts only after Phase 4 is merged + deployed.
- Every phase opens a PR. No auto-merge. Andrew reviews and merges.
- Every phase has a smoke spec under `smoke-tests/tests/nudges-*.spec.ts`.
- Every phase has a handoff doc at `docs/handoffs/YYYY-MM-DD_sprint_05_phase_{N}_*.md`.
- Never compose the AI-generated nudge body using the ScoutSheet streaming path. Use a dedicated thin orchestrator entry point so chat and nudge traffic don't share conversation rows.
- Rule SQL whitelist: reject any keyword in `{INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, GRANT, REVOKE, CALL}` and any reference to `pg_*`, `information_schema`, or `\copy`.
- AI discovery prompt must NOT see message content from `ai_messages` (member conversations are private even from Scout's discovery pass). State digest only uses structured domain tables.
