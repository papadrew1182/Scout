# Canonical rewrite plan, Slice C: AI chat, nudges, affirmations, push

**Author:** subagent C (proposing only, not deciding)
**Date:** 2026-04-22
**Status:** draft for synthesis
**Baseline audit:** `docs/plans/2026-04-22_schema_canonical_audit.md`
**Sprint 05 reference:** `docs/plans/2026-04-21-sprint-05-plan.md`

---

## 0. Big-picture finding up front

The single most load-bearing question for this slice is: **are the `public.ai_*` tables being superseded by canonical `scout.ai_*` tables, or are they the current truth and `scout` has no canonical equivalent yet?**

Evidence (grep-based, 2026-04-22):

1. There is **no `scout.ai_*` table anywhere** in `backend/migrations/` or `database/migrations/`. `Grep "scout\.ai_"` returns only documentation and plan text that referenced the scout prefix aspirationally in sprint 04 planning.
2. The actual production-active ORM models (`backend/app/models/ai.py:12`, `:35`, `:62`) set `__tablename__ = "ai_conversations" / "ai_messages" / "ai_tool_audit"` with **no** `__table_args__ = {"schema": "scout"}`. They resolve to `public` via the default search path.
3. The handoff `docs/handoffs/2026-04-21_phase_1_ai_resume.md:115` explicitly records: "The plan referenced the `scout.` prefix. Actual table lives in the default (public) schema; the migration does not qualify with `scout.`." That is the definitive trail.
4. Every production AI feature shipped through sprint 04 (`046b_ai_conversation_resume.sql`, `045_ai_message_metadata.sql`) continued to ALTER `ai_conversations` / `ai_messages` in public. Sprint 05 (`049`-`051`) created `scout.nudge_*` and `scout.quiet_hours_family`, but deliberately did **not** touch or migrate the AI chat tables.

**Conclusion (proposal):** `public.ai_conversations` and `public.ai_messages` are **the current canonical truth** for chat state. There is no separate scout.* equivalent they need to merge with. The audit's LEGACY label (§3) is a category error for this subset: these tables pre-date migration 022 but they are the only persistence layer Scout AI has. They should be promoted to CANONICAL-in-place rather than migrated to scout.*.

That reframing shapes every recommendation below. If Andrew instead decides the dual-surface architecture requires scout.* to hold AI chat state too, Section 2 changes from "LEAVE + promote" to "CONSOLIDATE to scout.ai_*", and the PR count roughly doubles because of the live-data migration work.

---

## 1. Slice inventory

Row counts are the audit's 2026-04-21 production snapshot. File paths use `file:line` citations.

### 1.1 public.ai_conversations (30 rows, ACTIVE)

| Field | Value |
|-------|-------|
| Schema | public |
| Rows | 30 |
| Migration origin | `backend/migrations/010_ai_orchestration.sql:11-33` |
| Subsequent migrations | `015_ai_conversation_kind.sql:23-44`, `019_tier3.sql:33-37`, `046b_ai_conversation_resume.sql:26-69` |
| ORM model | `backend/app/models/ai.py:12` |
| Routes | `backend/app/routes/ai.py:19,459-498,565`, conversation mutations in `ai_conversation_service.py` |
| Services | `backend/app/services/ai_conversation_service.py:33,71,130,154,183,253` |
| Tests | `backend/tests/test_ai_conversation_resume.py` (615 lines), `test_ai_routes.py` (624 lines), `test_ai_observability.py` |
| Views | None |
| Permissions | `ai.manage_own_conversations`, `ai.clear_own_history` (046b) |

### 1.2 public.ai_messages (118 rows, ACTIVE)

| Field | Value |
|-------|-------|
| Schema | public |
| Rows | 118 |
| Migration origin | `backend/migrations/010_ai_orchestration.sql:39-55` |
| Subsequent migrations | `017_ai_messages_clock_timestamp.sql`, `019_tier3.sql:61-62` (index), `045_ai_message_metadata.sql` (metadata JSONB), `046b_ai_conversation_resume.sql:43-59` (backfill from title) |
| ORM model | `backend/app/models/ai.py:35` (note: column `metadata` remapped to attribute `attachment_meta` at `:49`) |
| Routes | `backend/app/routes/ai.py:19,473,496` |
| Services | `backend/app/ai/orchestrator.py:34,146,197,325,603`, `backend/app/ai/pricing.py`, `ai_conversation_service.py:205` (pagination) |
| Tests | `test_ai_routes.py`, `test_ai_conversation_resume.py`, `test_ai_provider_retry.py`, `test_ai_provider_caching.py`, `test_ai_observability.py`, `test_tier3.py` |
| Views | None |
| Notes | 118 rows is genuine audit trail. Every chat, tool call, tool result, attachment reference is here. Retention policy unwritten but de facto "keep forever". |

### 1.3 public.ai_tool_audit (52 rows, ACTIVE)

| Field | Value |
|-------|-------|
| Schema | public |
| Rows | 52 |
| Migration origin | `010_ai_orchestration.sql:61-85` |
| Subsequent | `014_family_ai_chat.sql:34-38` (adds `moderation_blocked` status) |
| ORM model | `backend/app/models/ai.py:62` |
| Routes | `backend/app/routes/ai.py:710-715`, `mcp_http.py` |
| Services | orchestrator writes this; read by observability endpoints and MCP proxy |
| Tests | `test_ai_observability.py`, `test_ai_tools.py` |
| Views | None |
| Notes | Compliance-grade log. Every AI tool execution, every denial, every moderation block. Retention: indefinite. |

### 1.4 public.ai_daily_insights (2 rows)

| Field | Value |
|-------|-------|
| Schema | public |
| Rows | 2 |
| Migration origin | `016_tier1_proactive.sql:53-70` |
| ORM model | `backend/app/models/scheduled.py:39` |
| Services | `backend/app/ai/insights.py` |
| Tests | indirect via tier 1 coverage |
| Notes | Cache of AI-generated "what's off track today" per family per day. Constraint: `insight_type IN ('off_track')` only. |

### 1.5 public.ai_homework_sessions (1 row)

| Field | Value |
|-------|-------|
| Schema | public |
| Rows | 1 |
| Migration origin | `018_tier2_retro_and_homework.sql:17-48` |
| ORM model | `backend/app/models/homework.py:13` |
| Services | `backend/app/ai/homework.py` |
| Tests | `test_tier3.py` |
| Notes | Per-child homework activity log. Subject auto-classified from kid's chat messages. Row count low because feature is recent and Robert family has one kid of homework age. |

### 1.6 scout.nudge_dispatches (canonical, sprint 05 P1)

| Field | Value |
|-------|-------|
| Schema | scout |
| Migration origin | `049_nudge_engine.sql:27-59` |
| ORM model | `backend/app/models/nudges.py:11` |
| Routes | `backend/app/routes/nudges.py:14-38` (self-scoped list), admin read only via `quiet_hours` / `nudge_rules` admin files |
| Services | `backend/app/services/nudges_service.py` (1438 lines) |
| Tests | `test_nudges.py` (4148 lines), `test_nudge_composer.py` |
| Notes | Parent row for one delivered Inbox entry plus at most one push. FK to `scout.push_deliveries.id` (046a). |

### 1.7 scout.nudge_dispatch_items (canonical, sprint 05 P1)

| Field | Value |
|-------|-------|
| Schema | scout |
| Migration origin | `049_nudge_engine.sql:65-88` |
| ORM model | `backend/app/models/nudges.py:51` |
| Services | same as dispatches |
| Tests | same |
| Notes | Source-level provenance. `UNIQUE (source_dedupe_key)` is the authoritative dedupe boundary. `trigger_kind` CHECK list is the contract the P4 whitelist validator must match. |

### 1.8 scout.quiet_hours_family (canonical, sprint 05 P2)

| Field | Value |
|-------|-------|
| Schema | scout |
| Migration origin | `050_nudge_quiet_hours_and_batching.sql:32-52` |
| ORM model | `backend/app/models/quiet_hours.py:11` |
| Routes | `backend/app/routes/admin/quiet_hours.py` |
| Services | `nudges_service.should_suppress_for_quiet_hours`, `resolve_deliver_after` |
| Tests | `test_nudges.py` quiet-hours sections |
| Notes | Dedicated table by design. Sprint 05 plan Section 2 paragraph 4 documents this as an intentional exception to the family_config convention. |

### 1.9 scout.nudge_rules (canonical, sprint 05 P4)

| Field | Value |
|-------|-------|
| Schema | scout |
| Migration origin | `051_nudge_rules.sql:32-72` |
| ORM model | `backend/app/models/nudge_rules.py:11` |
| Routes | `backend/app/routes/admin/nudge_rules.py` |
| Services | `nudges_service.scan_rule_triggers`, `nudge_rule_validator.validate_rule_sql`, `nudges_service.execute_validated_rule_sql` |
| Tests | `test_nudge_rule_validator.py` (318 lines) SQL attack suite, `test_nudges.py` rule engine sections |
| Notes | `canonical_sql` re-serialized at write time. Scheduler executes canonical, never raw template. |

### 1.10 scout.affirmations / affirmation_feedback / affirmation_delivery_log

| Field | Value |
|-------|-------|
| Schema | scout |
| Migration origin | `039_affirmations.sql:18-58` |
| Seed | 25 starter affirmations inserted at `039_affirmations.sql:75-108` |
| ORM model | `backend/app/models/affirmations.py:11,31,43` |
| Routes | `backend/app/routes/affirmations.py` (user), `backend/app/routes/admin/affirmations.py` (admin) |
| Services | `backend/app/services/affirmation_engine.py:1-425` |
| Tests | `test_affirmations.py` (214 lines) |
| Notes | Already canonical in scout.*. Not LEGACY; the audit's UNCLEAR label reflects "not audited yet", not a schema problem. |

### 1.11 scout.push_devices / push_deliveries

| Field | Value |
|-------|-------|
| Schema | scout |
| Migration origin | `046a_push_notifications.sql:7-60` |
| ORM model | `backend/app/models/push.py:26,55` |
| Routes | `backend/app/routes/push.py` (252 lines) |
| Services | `backend/app/services/push_service.py` (426 lines) |
| Tests | `test_push_notifications.py` (452 lines), smoke `push-notifications.spec.ts` |
| Notes | Already canonical in scout.*. Name rationalization in `052_normalize_046_collision.sql` resolved the 046a/046b filename conflict. |

### 1.12 Related but not-strictly-in-slice

- `public.parent_action_items` (33 rows, ACTIVE) - nudges write here at `nudges_service.py:948-958`. Owned by Slice A or a future "inbox" slice, but its `chk_parent_action_items_action_type` CHECK list (`050_nudge_quiet_hours_and_batching.sql:80-103`) is now a **nudges contract**. Any consolidation affecting it must go through this slice.
- `public.scout_scheduled_runs` (48 rows, ACTIVE) - `016_tier1_proactive.sql:22-43`, `backend/app/models/scheduled.py:13`. Scheduler dedupe for the daily brief, weekly retro, anomaly scan, and (in 049-051) the nudge scan + discovery jobs. Audit flags it UNCLEAR; this slice is the primary user.

---

## 2. Per-table recommended action

| Table | Action | One-line justification |
|-------|--------|------------------------|
| public.ai_conversations | **LEAVE + promote label to CANONICAL-in-public** | No scout.* counterpart exists; 30 live rows; 11 migrations of accumulated contract; sprint 04 shipped new features against this table name. Migrating to scout.* is pure cost, no benefit. |
| public.ai_messages | **LEAVE + promote label to CANONICAL-in-public** | Same rationale. 118 audit rows. Column rename landmine (`metadata` vs `attachment_meta`) makes any migration risky. |
| public.ai_tool_audit | **LEAVE + promote label to CANONICAL-in-public** | Audit trail, indefinite retention, 52 rows. Cross-references conversation_id. Moving these without moving the conversations breaks foreign keys. |
| public.ai_daily_insights | **LEAVE + promote** | 2 rows, small table, `insight_type` CHECK is extensible in-place. |
| public.ai_homework_sessions | **LEAVE + promote** | 1 row, FKs to public.ai_conversations (migration 018 line 22). Moves only make sense with the conversations move, which we are not doing. |
| scout.nudge_dispatches | **KEEP canonical** | Already correct shape; Sprint 05 P1 design is the target. |
| scout.nudge_dispatch_items | **KEEP canonical** | Same. |
| scout.quiet_hours_family | **KEEP canonical** | Documented intentional exception to `family_config` convention. |
| scout.nudge_rules | **KEEP canonical** | Same. Paired with the whitelist validator. |
| scout.affirmations (+feedback+delivery_log) | **KEEP canonical + mark audited** | Shipped canonical in 039. Audit's UNCLEAR is a gap in the audit, not a real ambiguity. |
| scout.push_devices / push_deliveries | **KEEP canonical + mark audited** | Same. |
| public.parent_action_items | **Slice dependency, not owned here** | Slice A / inbox slice decides fate. This slice's only stake is that the `action_type` CHECK list stays additive. |
| public.scout_scheduled_runs | **Slice dependency, audit owes it a decision** | This slice relies on it working. Recommend keep in public until a dedicated scheduler slice. |

**No table in Slice C is a CONSOLIDATE.** That is the surprising conclusion, but it is evidence-based. All nudge/affirmation/push tables are already canonical in scout.*; all AI chat tables have no canonical counterpart to consolidate with.

---

## 3. Proposed canonical target shape

Because Section 2 produced no CONSOLIDATE actions, the shape work is narrower than a typical slice. Two labeling and one contract-capture change are proposed.

### 3.1 Promote the public.ai_* set to CANONICAL-in-public

Write a short architectural note (not a migration) that amends ARCHITECTURE.md to allow `public.*` to be the canonical home of a feature when that feature predates migration 022 and has no scout.* counterpart. Explicit list: `public.ai_conversations`, `public.ai_messages`, `public.ai_tool_audit`, `public.ai_daily_insights`, `public.ai_homework_sessions`, `public.scout_scheduled_runs`, `public.parent_action_items`.

This closes the audit's definitional gap without touching data.

### 3.2 Formalize the parent_action_items.action_type CHECK as a shared contract

Currently the enum lives in migration 020 plus 050 additions. Every slice that wants to write a new action_type adds-via-migration (chores/tasks, meals, nudges, projects). Propose a lightweight convention: each slice's ALTER lives in a migration whose comment cites `action_type` ownership. No schema change proposed. Pure documentation.

### 3.3 Whitelist validator schema contract

See Section 10. The target shape for `_ALLOWED_TABLES` is: keep the current public.* list AND add `scout.task_occurrences`, `scout.task_completions`, `scout.task_templates`, `scout.routine_templates`. The `_is_disallowed_schema` guard at `nudge_rule_validator.py:224` currently rejects `scout`; that must flip to allow it for the allowlisted tables only. Shape proposal:

```
_ALLOWED_TABLE_QUALIFIED = frozenset({
    "public.personal_tasks",
    "public.events",
    "public.event_attendees",
    "public.task_instances",
    "public.routines",
    "public.chore_templates",
    "public.family_members",
    "public.families",
    "public.bills",
    "scout.task_occurrences",
    "scout.task_completions",
    "scout.task_templates",
    "scout.routine_templates",
})
```

This is a shape proposal only; the PR plan (Section 6) schedules the real change.

---

## 4. Data migration plan

Because no table in this slice is CONSOLIDATE, there is no bulk data migration to plan. The live-data work reduces to three small, surgical items.

### 4.1 ai_messages retention policy capture (no migration)

Add a one-paragraph comment to `010_ai_orchestration.sql` (via a new documentation migration comment block OR by adding a comment to the ORM model docstring; no DDL required). Content: "ai_messages is the audit trail for every Scout AI tool call and chat turn. Retention is indefinite. Any future archival strategy must preserve the conversation_id -> messages linkage and the tool_calls/tool_results JSON intact." This is paperwork, not a migration.

### 4.2 Preserved vs dropped columns audit for ai_messages

If a future slice ever does move ai_messages to scout.ai_messages (not proposed here), the preservation list must include:

- `id`, `conversation_id`, `role`, `content`, `tool_calls`, `tool_results`, `model`, `token_usage`, `created_at`, `metadata` (all 10 columns).
- Drop candidates: **none**. Every column is referenced by existing code.
- The column attribute/column-name split (`attachment_meta` Python name, `metadata` SQL name at `backend/app/models/ai.py:49`) must survive rename. This is the primary landmine.

Captured here so the decision is not re-litigated.

### 4.3 FK re-pointing strategy (conditional)

If the chat tables ever migrate, the following FKs must re-point:

- `public.ai_tool_audit.conversation_id` -> scout.ai_conversations(id)
- `public.ai_homework_sessions.conversation_id` -> scout.ai_conversations(id)
- `public.planner_bundle_applies.conversation_id` -> scout.ai_conversations(id) (migration 021 line 25)
- `public.family_memories.source_conversation_id` -> scout.ai_conversations(id) (migration 021 line 111)

All four are `ON DELETE SET NULL` today, so a phased rename is tolerable. Out of scope for this slice's PR plan.

### 4.4 Affirmations, push, nudges

All already canonical in scout.*. No data migration needed. Row counts at 2026-04-21 are 25 (seed affirmations), 0 (push_devices, push_deliveries, nudge_dispatches, nudge_dispatch_items, nudge_rules, quiet_hours_family, affirmation_feedback, affirmation_delivery_log) - post-sprint-05, these tables are new empty canonical tables.

### 4.5 Cutover

Not applicable given the no-move recommendation. If Andrew overrides, the cutover would be: freeze orchestrator writes, run ALTER TABLE SET SCHEMA on the five public.ai_* tables in a single migration transaction (not a data copy, just a schema relocation), update ORM __table_args__, redeploy backend. Estimated downtime under 30 seconds on the current 203-row combined footprint.

---

## 5. Dependencies on other slices

### 5.1 Slice A (chores, tasks, routines) - two hard dependencies

**5.1.a Nudge rule validator whitelist.** The validator at `backend/app/services/nudge_rule_validator.py:58-70` whitelists public.* tables including `task_instances`, `routines`, `chore_templates`. The audit §4 flags this. If Slice A deprecates `public.task_instances` without first updating this whitelist to add `scout.task_occurrences`, every nudge rule using `task_instances` breaks silently. Slice A owns the Slice C blocker: the whitelist update **must land before any Slice A migration that renders public.task_instances non-authoritative**.

Proposed handshake: Slice A opens a PR that changes the whitelist BEFORE it opens the PR that stops writing to public.task_instances. Slice C PR 3 (Section 6) is a joint PR with Slice A if schedules line up, or Slice A owns the whitelist edit with Slice C as required reviewer.

**5.1.b Built-in scanner SQL.** `nudges_service.scan_missed_routines` at `nudges_service.py:193-206` reads `FROM task_instances ti JOIN routines r`. `scan_overdue_tasks` reads `FROM personal_tasks`. `scan_upcoming_events` reads `FROM events JOIN event_attendees`. None of these go through the validator; they are hardcoded SQL. Same silent-break risk as above. Slice A owns the source-of-truth switch for these tables; Slice C must port the scanner SQL to match, in the same deploy window.

### 5.2 Slice B (meals, grocery, home) - no hard dependencies

AI chat orchestrator reads meals and grocery through tool calls, not through schema joins. No cross-slice migration needed. If Slice B renames `public.meal_plans` or similar, the orchestrator picks it up through its tool registry, not through the ai_* tables.

### 5.3 Slice D (identity, permissions, connectors) - one soft dependency

Permissions added in this slice (`nudges.view_own`, `nudges.configure`, `quiet_hours.manage`, `affirmations.manage_config`, `push.*`, `ai.edit_own_personality`, `ai.edit_any_personality`, `ai.manage_own_conversations`, `ai.clear_own_history`) all land via `scout.permissions` + `scout.role_tier_permissions`, already the canonical pattern (audit §4 "well-bridged"). No blocking dependency.

Slice D's membership tables (`scout.user_family_memberships`, migration 022) are referenced through the existing bridge. Slice C does not read them directly.

### 5.4 scheduler slice (implicit)

`public.scout_scheduled_runs` (48 rows) is used by the nudge scan job and the AI discovery tick. If a future slice migrates this to scout.*, Slice C's scheduler registrations need to update. Tracked but not blocking.

---

## 6. Proposed PR count and ordering

**Total: 5 PRs.** Serial except where marked parallel-safe.

### PR C1 - Audit label correction for public.ai_* set

- Scope: documentation only. Amend ARCHITECTURE.md and the audit's §3 LEGACY list to mark the public.ai_* set as CANONICAL-in-public. Add the ai_messages retention policy note.
- Migrations: none.
- Parallel-safe: yes (no code impact).
- Target branch: main direct.

### PR C2 - Nudge rule validator: extend whitelist to scout.* table subset

- Scope: `backend/app/services/nudge_rule_validator.py` schema allow-list changes. Replace `_ALLOWED_SCHEMA = "public"` with a per-table qualified whitelist that includes four scout.* tables (`task_occurrences`, `task_completions`, `task_templates`, `routine_templates`). Update `_is_disallowed_schema` + `_validate_table` accordingly. Extend `test_nudge_rule_validator.py` to cover scout-schema positive and negative cases.
- Migrations: none.
- **BLOCKER for Slice A's task_instances deprecation PR.** Must merge before Slice A's cutover.
- Rollback: single-file revert; no DB state.

### PR C3 - Built-in scanner SQL: dual-read bridge for task_instances + routines

- Scope: modify `scan_missed_routines` and `scan_overdue_tasks` in `nudges_service.py` to read from scout.task_occurrences when present, falling back to public.task_instances. Add feature flag `scout.task_occurrences.canonical` read from `family_config`. Smoke tests + unit tests for both paths.
- Migrations: none (feature flag lives in family_config).
- Must merge after PR C2 (order) but can be parallel-authored.
- Rollback: feature flag toggle; no schema state.

### PR C4 - Affirmations / push / scout_scheduled_runs audit labels

- Scope: documentation only. Mark `scout.affirmations`, `scout.affirmation_feedback`, `scout.affirmation_delivery_log`, `scout.push_devices`, `scout.push_deliveries`, and `public.scout_scheduled_runs` as explicitly audited in the audit doc. Adds one-paragraph shape notes.
- Migrations: none.
- Parallel-safe with everything.

### PR C5 - parent_action_items.action_type contract capture

- Scope: add a single migration `NNN_action_type_contract.sql` whose ONLY content is a comment block above the existing CHECK constraint explaining that additions must cite their slice ownership. No DDL change; this is a traceability checkpoint. Optional: accompany with a README in `backend/migrations/` describing the pattern.
- Migrations: one no-op migration (COMMENT ON CONSTRAINT only).
- Can merge last. Low urgency.

### Ordering summary

```
PR C1 (docs)           <- anytime
PR C4 (docs)           <- anytime, parallel with C1
PR C2 (whitelist)      <- before Slice A task_instances deprecation
PR C3 (scanner bridge) <- after C2, before Slice A cutover
PR C5 (contract note)  <- anytime after C1
```

If Slice A runs ahead of schedule, C2 + C3 could bundle into a single PR for atomicity (both would need to land together anyway on the cutover day).

---

## 7. Per-PR risk rating

| PR | Risk | Reason |
|----|------|--------|
| PR C1 | **low** | Documentation only. |
| PR C2 | **high** | Whitelist change in a security-critical SQL validator. A wrong allow-entry opens a cross-tenant read hole. Attack-suite tests at `test_nudge_rule_validator.py:1-318` must be extended to cover new scout.* tables and prove cross-family isolation still holds. Any rule author with `nudges.configure` is the threat surface. |
| PR C3 | **high** | Silent-break risk identical to audit §4's flag: if the fallback logic is buggy, missed_routine nudges stop firing for families that migrated to scout.task_occurrences, with no error. Smoke test must assert both-path delivery. Also touches built-in scanners that already fire on every 5-minute tick, so a SQL error immediately degrades the background job. |
| PR C4 | **low** | Documentation only. |
| PR C5 | **low** | Comment-only migration. |

Any PR that touches `public.ai_messages` is **medium+** per the user spec. None of the C1-C5 PRs proposed here touch ai_messages, by design.

If Andrew overrides and requires migrating ai_messages to scout.ai_messages, that becomes a new PR rated **high** due to: 118-row audit trail preservation, column rename landmine (`metadata` vs `attachment_meta`), and four dependent FK re-points (Section 4.3).

---

## 8. Per-PR rollback plan

### PR C1 rollback

Revert the docs commit. No DB state, no runtime impact.

### PR C2 rollback

Revert the `nudge_rule_validator.py` diff. Any nudge rules that were created against the expanded allow-list since PR C2 merged will start failing validation on next EDIT (not immediately on read - canonical_sql is stored). To fully roll back safely:

1. Revert the validator code.
2. Query `scout.nudge_rules` WHERE `canonical_sql ILIKE '%scout.%'`.
3. For each match, either edit the template_sql back to a public.* reference or set `is_active = false`.
4. Deploy.

No DB schema change to undo; canonical_sql strings are the rollback surface.

### PR C3 rollback

Flip the `family_config` feature flag `scout.task_occurrences.canonical` back to `false` for all families. Scanners revert to reading public.task_instances. Instant. No data lost; dispatches already written stay.

If the whole dual-read code is broken, revert the service diff; scanners return to pre-PR behavior. scout.task_occurrences rows accumulated during the broken window are not lost, they just are not read.

### PR C4 rollback

Revert the docs commit.

### PR C5 rollback

Revert the migration file. Since it only adds a COMMENT, reverting the code is enough; the comment stays in the DB but is harmless. Alternatively, write a companion migration `COMMENT ON CONSTRAINT ... IS NULL`.

### Audit-trail preservation note

Per user spec, "rollback must preserve the audit trail" on any PR touching ai_messages. None of C1-C5 touch ai_messages. If Andrew adds a hypothetical PR C6 (migrate ai_messages to scout), the rollback plan would be: `ALTER TABLE scout.ai_messages SET SCHEMA public` (schema relocation, not data copy) followed by restoring the ORM `__tablename__`. Rows stay put. Zero audit loss.

---

## 9. Smoke test strategy

### 9.1 Existing coverage to preserve

Backend:
- `backend/tests/test_ai_routes.py` (624 lines) - chat, conversation management, observability
- `backend/tests/test_ai_conversation_resume.py` (615 lines) - Sprint 04 resume + drawer
- `backend/tests/test_ai_observability.py` - audit trail read paths
- `backend/tests/test_ai_personality.py`, `test_ai_provider_caching.py`, `test_ai_provider_retry.py`
- `backend/tests/test_ai_tools.py` - tool routing + audit
- `backend/tests/test_nudges.py` (4148 lines) - end-to-end nudge pipeline
- `backend/tests/test_nudge_rule_validator.py` (318 lines) - SQL attack suite
- `backend/tests/test_nudge_composer.py` - P3 AI composition
- `backend/tests/test_push_notifications.py` (452 lines)
- `backend/tests/test_affirmations.py` (214 lines)
- `backend/tests/test_ai_discovery.py`, `test_ai_discovery_service.py` - P5 AI nudges
- `backend/tests/test_ai_context.py` - AI digest construction

Smoke (Playwright):
- `smoke-tests/tests/ai-roundtrip.spec.ts`
- `smoke-tests/tests/ai-conversation-resume.spec.ts`
- `smoke-tests/tests/ai-panel.spec.ts`
- `smoke-tests/tests/ai-personality.spec.ts`
- `smoke-tests/tests/ai-settings-toggles.spec.ts`
- `smoke-tests/tests/ai-streaming-depth.spec.ts`
- `smoke-tests/tests/affirmations.spec.ts`
- `smoke-tests/tests/nudges-phase-2.spec.ts` through `nudges-phase-5.spec.ts`
- `smoke-tests/tests/push-notifications.spec.ts`

### 9.2 New coverage required per PR

**PR C2 new tests (in `test_nudge_rule_validator.py`):**

- Positive: `SELECT member_id, id AS entity_id, 'task' AS entity_kind, due_at AS scheduled_for FROM scout.task_occurrences` parses + canonicalizes.
- Positive: same with `scout.task_completions`, `scout.task_templates`, `scout.routine_templates`.
- Negative: `scout.nudge_dispatches` rejects (not in allow-list even though same schema).
- Negative: `scout.permissions` rejects.
- Negative: fully-qualified `pg_catalog.pg_tables` still rejects.
- Cross-tenant isolation: a rule authored in family A containing a literal UUID of family B still gets family-scoped by `filter_rule_rows_to_family` at `nudge_rules.py:185`. Add explicit test asserting zero cross-family rows returned.

**PR C3 new tests:**

- `test_nudges.py` new section: `test_scan_missed_routines_reads_scout_task_occurrences_when_flag_on` with scout.task_occurrences rows and the flag set.
- Companion: `test_scan_missed_routines_falls_back_to_public_task_instances_when_flag_off`.
- Smoke: `smoke-tests/tests/nudges-phase-1-dual-read.spec.ts` (new file) toggling the feature flag and asserting delivered dispatches appear for both source tables.

**PR C5 new tests:** none; comment-only migration.

### 9.3 Gap analysis

Two coverage gaps identified that are **not** blockers for the slice but should be tracked:

- `test_ai_observability.py` does not assert that archiving a conversation preserves `ai_messages.created_at` ordering. Low severity; the CASCADE delete behavior is covered.
- No smoke test for `scout.ai_daily_insights` read path (only 2 rows exist). Out of scope; feature is internal.

---

## 10. Known gotchas and stop-conditions

### 10.1 #1 gotcha: nudge rule validator whitelist (audit §4)

**File:** `backend/app/services/nudge_rule_validator.py:58-70` plus `:224-225` (schema guard).

**Landmine:** `_ALLOWED_TABLES` lists nine public.* tables. `_is_disallowed_schema` at line 224 explicitly rejects `scout`. If Slice A deprecates `public.task_instances`, `public.routines`, or `public.chore_templates` without first updating this whitelist, every nudge rule that joins those tables passes re-validation on admin edit (canonical_sql is already stored) but fails at execution time with a silent schema error because Postgres cannot find the table. The scheduler tick logs a `RuleExecutionError [db_error]` once per rule per tick and moves on. Nudges stop firing for affected rules. No user-visible error surface.

**Stop-condition:** Slice A's task_instances deprecation PR **must not merge** before PR C2 lands. Guard with a joint PR or explicit pre-merge check.

### 10.2 #2 gotcha: built-in scanner SQL bypasses the validator

**File:** `backend/app/services/nudges_service.py:110-120` (overdue_task), `:148-161` (upcoming_event), `:190-206` (missed_routine).

**Landmine:** Built-in scanners use raw `text(...)` SQL against `public.personal_tasks`, `public.events`, `public.event_attendees`, `public.task_instances`, `public.routines`. No validator in the path. If Slice A deprecates those tables, these SQL strings break immediately on the next 5-minute tick. The PR C3 dual-read bridge exists to address this.

**Stop-condition:** Same as 10.1. PR C3 must land before Slice A cutover.

### 10.3 #3 gotcha: `metadata` column -> `attachment_meta` attribute mapping

**File:** `backend/app/models/ai.py:49`.

The column is named `metadata` in SQL (migration 045) but the SQLAlchemy attribute is `attachment_meta` because `metadata` is reserved on the Declarative base class. Any ai_messages migration must preserve the column name exactly. Any ORM edit must remember the attribute name. Grep `attachment_meta` before touching either.

### 10.4 #4 gotcha: `conversation_kind` CHECK is contract

**File:** `backend/migrations/015_ai_conversation_kind.sql:28-30`.

Values: `chat`, `tool`, `mixed`, `moderation`. The orchestrator reads this at `ai_conversation_service.py:145` and `orchestrator.py` flow decisions branch on it. Adding a value requires a new migration (cannot edit 015). Removing a value without backfill breaks the CHECK on existing rows.

### 10.5 #5 gotcha: quiet_hours_family is an intentional exception

**File:** `backend/migrations/050_nudge_quiet_hours_and_batching.sql:32`. `docs/plans/2026-04-21-sprint-05-plan.md` Section 2 paragraph 4.

This is the **only** scout.* table holding family-wide config outside `family_config`. Tempting to "fix" by moving to `scout.family_config['nudges.quiet_hours']`, but the scanner reads it on every 5-minute tick; the dedicated table is a perf-critical exception. Any proposal to consolidate it must produce a performance benchmark first. This slice proposes **KEEP**.

### 10.6 #6 gotcha: `parent_action_items.action_type` CHECK is multi-slice contract

**File:** migrations `015`, `016`, `018`, `019`, `020`, `050` all ALTER this CHECK.

Adding a new action_type requires DROP CONSTRAINT + ADD CONSTRAINT. Concurrent slices adding types create migration ordering hazards. `050` preserves the 020 list verbatim to avoid this, citing lines 86-103. Every future slice touching this CHECK must do the same.

### 10.7 #7 gotcha: AI discovery explicitly excludes certain domains

**File:** `backend/app/services/nudge_ai_discovery.py:6-8`, plan Section 6.

`ai_messages`, YNAB, and Apple Health are excluded from the discovery digest. Stop-condition: if this slice or any synthesis doc proposes making ai_messages canonical in scout, it does NOT automatically become discoverable. The exclusion is a separate policy gate in `build_family_state_digest`.

### 10.8 #8 gotcha: 046 filename collision

**File:** `backend/migrations/052_normalize_046_collision.sql`.

Two 046 migrations shipped on the same day (PR #35 and PR #37). 052 renamed them to 046a/046b and rewrote the tracker. Grep for plain `046_` in any new docs before committing - all references should be 046a or 046b.

### 10.9 Stop-conditions for synthesis

The synthesis layer must not:

1. Propose migrating public.ai_conversations or public.ai_messages to scout without Andrew's explicit override of this slice's Section 2 recommendation.
2. Merge any Slice A PR that stops populating public.task_instances before Slice C PR C2 (whitelist) and PR C3 (scanner bridge) have shipped.
3. Collapse `scout.quiet_hours_family` into `family_config` without a tick-time benchmark.
4. Add a new `parent_action_items.action_type` value without using the preserve-verbatim pattern from `050`.

---

## 11. Open questions

1. **Is Andrew willing to ratify "CANONICAL-in-public" as a category?** If not, the slice reduces to PRs C2/C3/C5 and Section 2 changes on the chat tables go back to OPEN.
2. **Does the audit's 35-entry UNCLEAR scout.* list enumerate each table?** The summary in the audit names "affirmations, nudge rules, push notifications, projects, home maintenance" but no complete list. This slice claims scout.affirmations (+2 siblings), scout.push_devices (+1 sibling), scout.nudge_* (4 tables), scout.quiet_hours_family - 10 of the 35. A full enumeration from the audit author would confirm no orphan was missed.
3. **Who owns `public.scout_scheduled_runs`?** Sprint 05 registered two new jobs there (`nudge_scan`, `nudge_ai_discovery_tick`). This slice uses it but did not create it. Recommend a future "scheduler slice" take ownership.
4. **Should the AI_messages retention policy be formalized in a migration-comment or a separate RETENTION.md doc?** This slice proposes a docstring + migration comment. A retention policy doc may be overkill for 118 rows.

---

## 12. What this plan does NOT do

- Does not propose SQL migrations for the public.ai_* tables. That is the explicit recommendation.
- Does not touch Slice A's chore/task/routine tables. Those are Slice A's scope, even where Slice C reads them.
- Does not modify code or schema. Every PR in Section 6 is proposal-only until Andrew signs off.
- Does not estimate calendar-time effort. PR count and ordering are the user-spec'd outputs.
- Does not audit frontend `scout-ui` for schema drift; that is a future UI-slice concern.
- Does not validate the architecture decisions in ARCHITECTURE.md or interaction_contract.md; assumes they are correct.
