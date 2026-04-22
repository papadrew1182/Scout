# Sprint 05 Phase 4 - Admin Rule Engine - handoff

**Prepared:** 2026-04-21
**Branch:** `sprint/sprint-05-phase-4-admin-rule-engine`
**Base:** `main` post-PR #56 (Phase 3 merge `016f8f0c`)
**Spec:** `SCOUT_SPRINT_05_PROACTIVE_NUDGES.md`
**Plan:** `docs/plans/2026-04-21-sprint-05-plan.md` §7 Phase 4

## What shipped

### Schema
- Migration 051:
  - `scout.nudge_rules` with `family_id` FK, `UNIQUE (family_id, name)`, partial index on `(family_id, is_active) WHERE is_active = true`, CHECK constraints on source_kind / trigger_kind / severity / default_lead_time_minutes, and a `chk_nudge_rules_sql_template_has_sql` constraint.
  - `nudges.configure` permission granted to PARENT + PRIMARY_PARENT.
- `sqlglot>=23,<27` added to `backend/requirements.txt`.

### Models + schemas
- `backend/app/models/nudge_rules.py` NudgeRule.
- `backend/app/schemas/nudges.py` extended with NudgeRuleRead / NudgeRuleCreate / NudgeRulePatch / PreviewCountResponse.

### Validator + executor + scanner (the critical path per revised plan §5)
- `backend/app/services/nudge_rule_validator.py`:
  - `validate_rule_sql(template_sql) -> CanonicalSQL`. sqlglot parse (read='postgres'), strict node + function + table whitelist, comment-scan belt-and-suspenders, re-serializes AST into canonical SQL.
  - Approved tables (v1): `public.personal_tasks / events / event_attendees / task_instances / routines / chore_templates / family_members / families / bills`. Anything in `pg_*`, `information_schema`, or `scout.*` is rejected.
  - Allowed functions: `now / coalesce / lower / date_trunc / extract / count / min / max / sum / current_timestamp / current_date`.
  - Raises `RuleValidationError` with a tagged message: `[parse] / [multi-statement] / [not-select] / [disallowed-node] / [disallowed-function] / [disallowed-schema] / [disallowed-table] / [comment]`.
  - 40-case attack suite in `backend/tests/test_nudge_rule_validator.py` covers DML, DDL, multi-statement, CTE, UNION/INTERSECT/EXCEPT, subqueries, COPY, CALL, pg_* / information_schema / scout access, disallowed tables, unapproved functions, and SQL comments. Landed BEFORE CRUD routes per plan safety bar.
- `backend/app/services/nudges_service.py::execute_validated_rule_sql`:
  - Nested tx with `SET LOCAL statement_timeout` + `lock_timeout` + `transaction_read_only = on` + `TIME ZONE 'UTC'`.
  - Caps returned rows at 200.
  - Validates the row shape has the four required columns: `member_id / entity_id / entity_kind / scheduled_for`.
  - Raises `RuleExecutionError` with tagged message on timeout / lock / db_error / schema.
- `backend/app/services/nudges_service.py::scan_rule_triggers`:
  - Iterates active `NudgeRule` rows; emits `NudgeProposal` with `trigger_kind='custom_rule'`.
  - One bad rule is logged + skipped; does not poison the tick.
  - Total wall-clock budget (`budget_seconds`, default 2.0s) stops iteration once exhausted.

### Pipeline integration
- `run_nudge_scan` now calls `scan_rule_triggers` AFTER the built-in scanners (per plan §3). `rule_scan_budget_seconds` kwarg bounds rule execution. Built-ins still run unconditionally.
- `run_nudge_scan_tick` (scheduler wrapper) still passes default `budget=2.0s`.

### Admin CRUD
- `backend/app/routes/admin/nudge_rules.py`:
  - `GET /api/admin/nudges/rules` - list family's rules.
  - `POST /api/admin/nudges/rules` - create; validates template_sql; stores canonical_sql.
  - `PATCH /api/admin/nudges/rules/{id}` - re-validates on any template_sql change; keeps old canonical_sql on 422.
  - `DELETE /api/admin/nudges/rules/{id}` - 204.
  - `POST /api/admin/nudges/rules/{id}/preview-count` - runs canonical SQL and returns row count (capped 200) or tagged error.
- All five gated by `nudges.configure`. Cross-family rule id returns 404. Non-admin returns 403.

### Frontend
- `scout-ui/app/admin/ai/nudges.tsx` refactored into tabs:
  - **Quiet hours** (Phase 2, unchanged).
  - **Rules** (new): list, Add form, Pause/Resume toggle, Preview count, Delete with confirm.
- `scout-ui/lib/nudges.ts` extended with 5 helpers + types.
- `scout-ui/lib/api.ts` gained `del` helper.
- TypeScript 0 errors.

### Tests
- `backend/tests/test_nudges.py`: 108+ pass total (Phases 1-4 combined) + 1 pre-existing unrelated failure.
- `backend/tests/test_nudge_rule_validator.py`: 40 pass (attack suite).
- Full regression: 846+ pass.

## What this phase does NOT do

- **AI-driven trigger discovery** - Phase 5 scope.
- **Least-privilege DB role for rule execution.** v1 relies on `SET LOCAL transaction_read_only = on` + `statement_timeout` + `lock_timeout` + strict SQL whitelist. A separate Postgres role (e.g. `scout_rule_reader`) with only SELECT grants on the approved tables is the natural v2 hardening; not required for v1 because the whitelist already blocks all DML/DDL and the transaction is READ ONLY at session scope.
- **Per-rule timeout overrides** - one system-wide `statement_timeout_ms` (default 1500) applies to all rules.
- **Rule versioning / audit history** - updates overwrite.
- **Preview count for large result sets** - cap is 200; UI shows "(capped)" when hit.

## Known follow-ups

1. Pre-existing test failure `TestScannerStampsOccurrence::test_overdue_task_scanner_stamps_due_at` (flaky DST boundary) - unchanged from earlier phases.
2. Least-privilege DB role for rule execution (see above).
3. Rule SQL snippet library in the admin UI (pre-filled examples for common triggers).

## Arch check

Run before committing handoff:
- Before: Warnings: 0 | Info: 1.
- After: Warnings: 0 | Info: 1.
- Delta: 0 new WARNs (Phase 4 adds routes, service functions, validator; all gated). Handoff + smoke spec commit does not touch backend/frontend code.

## On Andrew's plate

- [ ] Review the PR.
- [ ] Merge (squash).
- [ ] Apply migration 051 on Railway via the public proxy URL pattern.
- [ ] Confirm `scout.nudge_rules` exists and `nudges.configure` is registered.
- [ ] Railway `/health` green post-deploy.
- [ ] Vercel deploy green (frontend shipped the tabbed UI).
- [ ] Pull main locally; delete the phase branch.

## Parallel-session note

Concurrent Claude Code sessions continued to drift HEAD to `fix/ios-push-foreground-handler` during Phase 4 - every subagent re-verified branch before each write and before each commit, same pattern as Phases 1-3. No rework needed.
