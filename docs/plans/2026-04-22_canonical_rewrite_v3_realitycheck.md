# Scout canonical rewrite - v3 plan reality check

**Prepared:** 2026-04-23
**Source plan:** `2026-04-22_canonical_rewrite_v3_plan.md` (attached at request time)
**Reviewer:** Claude Code (repo-reality check only, not structural review)
**Scope:** Eight items Andrew specified. Evidence-based, grep-verified.
**Status:** advisory. Does not start execution.

**Erratum (2026-04-23, added as part of PR 0.2):** this document contains 4 references to `SCOUT_AI_ENABLED` as the env var controlling AI availability. That env var name is incorrect. The actual env var is `SCOUT_ENABLE_AI` (feeds `settings.enable_ai` at `backend/app/config.py:93`). The correct name is used in the v5.1 merged plan and PR 0.2 scripts. References in this historical doc were left as-is to preserve the record of what was believed at reality-check time; future operational guidance uses the correct name.

---

## 0. Headline findings

1. **There is no Supabase Auth integration.** The v3 Phase 0 "Supabase Auth pre-flight" is based on a false premise. Scout uses Supabase only for Storage (file attachments). Auth is in-house: bcrypt + local `public.sessions` + `public.user_accounts`. Phase 0's user-cleanup reduces to `TRUNCATE public.user_accounts; TRUNCATE public.sessions;` and nothing in the Supabase control plane needs touching.

2. **Scheduler has 8 jobs, not 4.** v3 §6 names `nudge_scan`, `nudge_ai_discovery_tick`, `_run_morning_brief`, `_run_anomaly_scan`. Missing from the named list: `_run_weekly_retro`, `_run_moderation_digest`, `run_push_receipt_poll_tick`, `process_pending_dispatches_tick`. All 8 are disabled by a single env var (`SCOUT_SCHEDULER_ENABLED=false`), so the quiesce mechanism is simple even though the job count is larger than the plan states.

3. **Protected-tables rule is implementable as written.** No FK references anywhere in migrations point at `public.sessions` or `public.scout_scheduled_runs`. Both are leaf nodes; truncating has zero cascading effect. v3 §3 rule is safe.

4. **Next migration number is 053.** No in-flight work on any branch past migration 052. v3's reservation of 053-080 is consistent with reality.

5. **Bootstrap mechanism already exists.** `POST /api/auth/bootstrap` + `SCOUT_ENABLE_BOOTSTRAP=true` creates the first admin account when zero accounts exist. Phase 5 "re-authenticate self" is a one-call flow against this existing endpoint. Plan should name it explicitly.

6. **Two v3 inventory discrepancies worth flagging:** (a) Phase 5 bootstrap checklist item #4 assumes an AI tool for chore creation that doesn't exist; (b) the clean-slate approach implicitly orphans Supabase Storage blobs, which the plan doesn't acknowledge.

---

## 1. FK check for protected tables (Item 1)

**Question:** Can `public.sessions` and `public.scout_scheduled_runs` be truncated without cascading damage? Any FKs pointing at them?

**Method:** `grep -ri "REFERENCES\s+(public\.)?sessions\b"` across `backend/migrations/` and `database/migrations/`. Same for `scout_scheduled_runs`.

**Result:** Zero matches for both tables in any migration file.

- `public.sessions` - referenced only from `backend/app/services/auth_service.py` and `backend/app/models/foundation.py:71` (the ORM). No FK constraints in SQL. Truncate is a no-op on the FK graph.
- `public.scout_scheduled_runs` - referenced only from `backend/app/scheduler.py` and `backend/app/models/scheduled.py:13`. No FK constraints in SQL. Truncate is a no-op on the FK graph.

**Verdict:** v3 §3 rule is safe. Both tables are leaf nodes. Truncate allowed, as planned.

**Supplementary note:** `public.sessions` rows are auth tokens. Truncating logs everyone out, as the plan states. The only active user is Andrew, so this is acceptable. The v3 plan correctly identifies this.

**Supplementary note on `scout_scheduled_runs`:** the 48 rows are the dedupe mutex for daily scheduler work. Truncating mid-day could cause today's already-fired jobs to re-fire if the scheduler is still running. The v3 §5 quiesce step happens first, so no jobs run during the truncate - the rule is safe ONLY if truncate is inside the quiesce window, not before or after. Recommend Phase 0 explicitly order: (1) quiesce scheduler, (2) verify no tick in flight, (3) truncate.

---

## 2. Quiesce mechanism audit (Item 2)

**Question:** What writes to DB at runtime? v3 §6 names 4 scheduler jobs, AI writers, and "background workers." Surface what §6 missed.

### 2.1 Scheduled jobs - complete list

Source: `backend/app/scheduler.py:142-222` (the `_tick` function; all 8 jobs run on the 5-minute interval):

| # | Job | File:line | DB writes |
|---|-----|-----------|-----------|
| 1 | `run_morning_brief_tick` | `scheduler.py:142,278-354` | inserts `parent_action_items`, `scout_scheduled_runs`, writes AI messages |
| 2 | `run_weekly_retro_tick` | `scheduler.py:152,418-487` | inserts `parent_action_items`, `scout_scheduled_runs` |
| 3 | `run_moderation_digest_tick` | `scheduler.py:162,568-717` | inserts `parent_action_items`, `scout_scheduled_runs` |
| 4 | `run_anomaly_scan_tick` | `scheduler.py:172,785-893` | inserts `parent_action_items`, `scout_anomaly_suppressions`, `scout_scheduled_runs` |
| 5 | `run_push_receipt_poll_tick` | `scheduler.py:182-189`, implemented in `app/services/push_service.py` | updates `scout.push_deliveries` (provider receipts) |
| 6 | `run_nudge_scan_tick` | `scheduler.py:193-199`, implemented in `app/services/nudges_service.py` | inserts `scout.nudge_dispatches` and `scout.nudge_dispatch_items` |
| 7 | `nudge_ai_discovery_tick` | `scheduler.py:205-212`, implemented in `app/services/nudge_ai_discovery.py` | inserts `scout.nudge_dispatches`, reads `ai_messages`, `parent_action_items`, `family_members` etc. |
| 8 | `process_pending_dispatches_tick` | `scheduler.py:216-222`, implemented in `app/services/nudges_service.py` | updates held dispatches, may write to `scout.push_deliveries` |

**v3 §6 misses 4 of 8 jobs.** The single-env-var quiesce fixes this regardless (the env var stops the whole scheduler), but the plan's list is incomplete.

### 2.2 Quiesce mechanism

Source: `backend/app/main.py:67-76`.

```python
if os.environ.get("SCOUT_SCHEDULER_ENABLED", "true").lower() != "false":
    scheduler = start_scheduler(lambda: SessionLocal())
    logger.info("Scout backend started (scheduler=on)")
else:
    logger.info("Scout backend started (scheduler=off)")
```

**Mechanism (prescriptive for Phase 0):**
1. Set `SCOUT_SCHEDULER_ENABLED=false` on Railway.
2. Redeploy (or restart) the backend. On next lifespan start, no scheduler thread is spawned.
3. All 8 jobs are silent for the sprint duration.
4. Re-enable at end of Phase 3 by setting the env var back to `true` (or deleting it - default is "true").

**Advisory lock safety:** `scheduler.py:130,229` uses a Postgres advisory lock (`settings.scheduler_advisory_lock_key`, default `0x5C0A7_11CC`) to prevent concurrent ticks across instances. Default value is hardcoded in `config.py:51` - no env var required. Irrelevant during quiesce because no ticks run.

### 2.3 Startup hooks

Source: `backend/app/main.py:56-86` (single lifespan context manager).

- Only one startup action: conditional `start_scheduler()` call. Quiesced by the env var.
- No DB writes at startup itself.
- Graceful `stop_scheduler()` on shutdown (idempotent).

No additional `@app.on_event("startup")` handlers; FastAPI route handlers don't spawn workers.

### 2.4 Threading / asyncio audit

Grep for `threading.Thread`, `asyncio.create_task`, `asyncio.ensure_future`, `BackgroundTasks`, `loop.create_task`, `Executor.submit`, `run_in_executor` across `backend/`:

- **Zero worker-thread spawns found outside scheduler.**
- One mention of `threading.Lock()` at `backend/app/routes/mcp_http.py:39,73` - in-process rate limiter mutex. No background task, no DB writes from the lock itself.
- `backend/app/ai/orchestrator.py:569,572,595` - `asyncio.get_event_loop().run_until_complete(...)` for inline image-attachment fetches inside request handlers. These run synchronously in the request context; they are not background tasks.

**Verdict:** No background workers outside the scheduler. Quiescing the scheduler covers everything.

### 2.5 AI writers

Source: `backend/app/ai/orchestrator.py`, `backend/app/ai/tools.py`.

AI tool invocations run synchronously in request-handler context. The `ToolExecutor.execute()` pattern at `tools.py:142-192` dispatches to handlers. Every write-capable tool runs inside the same request transaction and logs to `ai_tool_audit`.

**Quiesce strategy for AI writers during the maintenance window:**

The plan's §6 lists three options: (a) read-only middleware, (b) feature flag, (c) accept no AI calls happen.

Recommendation: **option (c)**. Scout has zero users. Andrew is the only caller. If Andrew doesn't chat with Scout between Phase 1 and Phase 3, no AI writes happen. No middleware needed. State the expectation in v3: "Do not interact with the Scout UI between end of Phase 1 and end of Phase 3. If you need to test something, it's the Phase 5 bootstrap."

If belt-and-suspenders is wanted: `backend/app/config.py:102` has `ai_enabled: bool = True` setting. Flip `SCOUT_AI_ENABLED=false` to hard-disable the AI surface during the window.

### 2.6 What v3 §6 missed (summary)

1. **4 additional scheduler jobs:** `_run_weekly_retro`, `_run_moderation_digest`, `run_push_receipt_poll_tick`, `process_pending_dispatches_tick`.
2. **The exact env var name** for the scheduler: `SCOUT_SCHEDULER_ENABLED`. Plan says "env var, config flag, or commenting out" - prescribe the env var specifically.
3. **Advisory lock detail:** not a concern during quiesce (since no ticks run), but the plan could note that re-enable after Phase 3 is self-consistent because the advisory lock handles concurrent starts safely.
4. **AI env var:** `SCOUT_AI_ENABLED=false` if an explicit block is desired. Plan should name this if Andrew wants a hard gate rather than self-discipline.

---

## 3. Supabase Auth pre-flight (Item 3)

**Question:** Is truncating `public.user_accounts` sufficient, or do auth users also need deletion from Supabase Auth's own tables?

### 3.1 Finding

**There is no Supabase Auth integration.** Supabase is used only for file Storage.

Evidence:

- `backend/app/config.py:68-75` - Supabase settings docstring explicitly says "Supabase Storage - used by the attachments service." Three env vars: `SCOUT_SUPABASE_URL`, `SCOUT_SUPABASE_SERVICE_ROLE_KEY`, `SCOUT_SUPABASE_STORAGE_BUCKET` (default `"attachments"`). Upload endpoints return 501 when `supabase_url` is unset.
- `backend/.env.example:15-18` - same three env vars, labeled "Supabase Storage (optional)."
- `backend/app/services/auth_service.py:15` imports `bcrypt`. Password hashing is `bcrypt.hashpw` / `bcrypt.checkpw` (line 32-37). No Supabase call.
- `backend/app/services/auth_service.py:20` imports UserAccount, Session, FamilyMember, Family from `app.models.foundation`. Auth reads and writes these ORM models directly.
- `backend/app/routes/auth.py:14` - router prefix `/api/auth`. All routes route through `auth_service`. No external auth provider.
- Grep for `supabase` across the entire backend finds 10 hits across `storage.py`, `ai/orchestrator.py` (attachment URLs), `schemas/ai.py`, tests, configs. None in any auth path.
- Grep for `gotrue`, `auth.users`, Supabase's Auth-specific symbols: **zero matches**.

### 3.2 What Phase 0 actually needs to do

**Supabase pre-flight reduces to:**

1. Truncate `public.user_accounts`. Authentication state is fully cleared.
2. Truncate `public.sessions`. All bearer tokens invalidated.
3. Set `SCOUT_ENABLE_BOOTSTRAP=true` on Railway. `backend/app/config.py:90` defines this.
4. Optional: purge the Supabase Storage bucket if desired (see §3.3).

**No Supabase API calls needed.** No auth.users table to delete from. No Supabase Admin SDK invocation.

### 3.3 Orphan blob problem (new open question)

Supabase Storage holds uploaded attachments. Migration history shows `backend/app/services/storage.py` + `backend/app/routes/storage.py` implement signed-URL upload flows tied to `ai_messages.attachment_meta` (column name `metadata` - reserved-word remap per `backend/app/models/ai.py:49`).

After Phase 1 drops `public.ai_messages`, any blob in the Supabase `attachments` bucket loses its DB reference and becomes orphan. This is not a data-integrity issue (no code looks them up) but it does leave dead files in the bucket.

**Decision needed for v3:** purge the Supabase Storage bucket during Phase 0, or leave the blobs as dead weight? Plan doesn't mention this.

If purging: one `curl` call against the Supabase Storage REST API to list + delete all objects in the bucket. Low risk.

### 3.4 Phase 5 bootstrap clarification

The plan says "Re-authenticate self. Verify login works end-to-end against scout.* tables." Prescriptive version:

1. `SCOUT_ENABLE_BOOTSTRAP=true` env var set (done in Phase 0).
2. POST to `/api/auth/bootstrap` with `{ "email": "andrew@...", "password": "..." }`. Returns a session token. Route at `backend/app/routes/auth.py:77`; service at `backend/app/services/auth_service.py:374`.
3. First account is created with `is_primary=true`; session token returned.
4. Use the token to exercise the checklist items in §5 of the v3 plan.
5. **At end of Phase 5:** flip `SCOUT_ENABLE_BOOTSTRAP=false`. This is mentioned in `config.py:148-149` as a production warning ("WARNING: Bootstrap enabled in production").

v3 plan should name these specific env vars and the specific endpoint.

### 3.5 Stop-condition removed

v3 §8 includes "Supabase Auth pre-flight reveals an unknown mechanism" as a stop-condition. **This stop-condition is now n/a** - the pre-flight is complete, the mechanism is "no Supabase Auth, bcrypt locally." Remove this stop-condition from v3.

---

## 4. Canonical schema inventory (Item 4)

Full inventory produced by sub-audit. Summary here; detail in appendix §A.

**Total scout.* tables needed after Phase 2: 59.**

Split by v3's four Phase-2 PRs:

| PR | Domain | Table count | Notes |
|----|--------|-------------|-------|
| 2.1 | Identity | 12 | families, family_members, user_accounts, sessions, role_tiers, role_tier_overrides, member_config, permissions, role_tier_permissions, user_family_memberships, user_preferences, device_registrations |
| 2.2 | Chores + tasks | 12 | task_templates (with scope fields native), routine_templates, routine_steps, standards_of_done, task_occurrences, task_assignment_rules, task_completions, task_exceptions, task_notes, task_occurrence_step_completions, daily_win_results, personal_tasks |
| 2.3 | AI | 8 | 5 public.ai_* equivalents + 3 nudge_* (already exist) |
| 2.4 | Remaining | 27 | meals, grocery, purchase_requests, home_maintenance, affirmations, parent_action_items, projects, events, calendar, connectors, budget/bill snapshots, push, rewards |

**Already canonical (no rebuild):** nudge_dispatches, nudge_dispatch_items, nudge_rules, quiet_hours_family, home_zones/assets/maintenance_*, affirmations + siblings, push_devices/deliveries, connectors/connector_accounts, household_rules, reward_policies, task_assignment_rules.

**Sprint 05 tables to explicitly NOT drop in Phase 1:** `scout.nudge_dispatches`, `scout.nudge_dispatch_items`, `scout.nudge_rules`, `scout.quiet_hours_family`, `scout.push_devices`, `scout.push_deliveries`. v3 §5 Phase 1 PR 1.3 correctly says "Keep scout.* tables that will be retained (nudge_* series, etc.)" but doesn't enumerate. This is the keep list.

### 4.1 Critical schema requirement: scope-contract fields on `scout.task_templates`

Closes the audit's HIGH-severity `v_household_today` gap. Seven columns must land on `scout.task_templates` at creation time in Phase 2 PR 2.2 (not bolted on later):

- `included jsonb NOT NULL DEFAULT '[]'`
- `not_included jsonb NOT NULL DEFAULT '[]'`
- `done_means_done text`
- `supplies jsonb NOT NULL DEFAULT '[]'`
- `photo_example_path text` (renamed from `photo_example_url` per v3 Q6)
- `estimated_duration_minutes integer`
- `consequence_on_miss text`

In the clean-slate framing these are NATIVE columns, not backfilled. Reference shape: `backend/migrations/041_chore_scope_contract.sql` + `backend/migrations/042_home_maintenance.sql:42-45` (which shipped the pattern correctly on `scout.maintenance_templates`).

### 4.2 AI domain clarification

v3 Q1 says "Drop `public.ai_*` tables. Build `scout.ai_*` per original architecture." This contradicts Slice C's CANONICAL-in-public finding from PR 68. Either works, but clean-slate implementing `scout.ai_*` means:

- Copy migrations 010 / 014 / 015 / 016 / 017 / 018 / 019 / 045 / 046b column shapes verbatim into new scout.ai_* tables.
- Preserve the `metadata` column name (SQLAlchemy attribute remains `attachment_meta` per `backend/app/models/ai.py:49`).
- `ai_messages` FKs `ai_conversations.id`. Build ai_conversations first.
- `ai_tool_audit`, `ai_homework_sessions`, and `ai_daily_insights` all FK to `ai_conversations` (or are standalone in ai_daily_insights's case).
- `ai_homework_sessions` has a `subject` CHECK constraint from migration 018 lines 23-33 - preserve the vocabulary exactly.

No data to copy (clean slate). Just fresh DDL.

### 4.3 `scout.standards_of_done` - verified missing from current schema

The canonical inventory lists `scout.standards_of_done` as an existing table, but the audit doesn't mention it. Grep of migrations confirms **no CREATE TABLE for `scout.standards_of_done`** anywhere. The ORM model at `backend/app/models/canonical.py` references it as an FK target. This is a gap: the table name is referenced but the table was never created. **This is likely a silent bug pre-dating v3.** Phase 2 PR 2.2 is the chance to create it fresh - worth explicit mention.

---

## 5. Consumer surface map (Item 5)

Full map produced by sub-audit. Summary here; detail in appendix §B.

**Total legacy tables covered:** 35.
**Tables with active consumers:** 28.
**Approximate total file hits:** 200+ across `backend/`, `scout-ui/`, `smoke-tests/`, `scripts/`, `migrations/`.

### 5.1 Heaviest consumer surfaces (per PR)

| PR | Top-3 most-referenced tables | Approx file count |
|----|------------------------------|--------------------|
| 3.1 (auth+identity) | `public.family_members`, `public.families`, `public.user_accounts` | 30+ files each (ORM imports pervasive) |
| 3.2 (chores+tasks) | `public.task_instances`, `public.chore_templates`, `public.personal_tasks` | 20+ files each |
| 3.3 (AI) | `public.ai_messages`, `public.ai_conversations`, `public.ai_tool_audit` | 10-15 files each |
| 3.4 (remaining) | `public.parent_action_items`, `public.grocery_items`, `public.events` | 10+ files each |

### 5.2 High-surprise-risk files flagged for per-PR audit

From the consumer map:

1. **`backend/app/services/tenant_guard.py:16-37`** - the guard that enforces family-scoping. Every auth-bearing route depends on this. Auth rewire (PR 3.1) must update it first.
2. **`backend/app/services/nudge_rule_validator.py:58-70`** - SQL allow-list with 9 public.* table names hardcoded. Must be updated during chores rewire (PR 3.2) or every nudge rule breaks silently.
3. **`backend/app/services/nudges_service.py:193-206`** (`scan_missed_routines`) and `:110-120` (`scan_overdue_tasks`) - raw SQL strings against `public.task_instances`, `public.routines`, `public.personal_tasks`. Bypass the validator; break on rewire.
4. **`backend/app/services/dashboard_service.py:15-27`** - imports 8 different model classes. Rewiring in one PR is feasible but will be a big-diff PR.
5. **`backend/app/ai/orchestrator.py:351-358`** - AI orchestrator creates `ParentActionItem` rows. Rewire must include this path.
6. **`scout-ui/lib/types.ts`** - TypeScript mirror types for every domain. Regeneration or manual update required per rewire.
7. **`scout-ui/lib/api.ts`** - ~200 API functions. Each one's response shape must survive the rewire.

### 5.3 Files that appear in EVERY PR's consumer audit

These files touch multiple domains. Handle carefully at each Phase 3 PR:

- `backend/app/services/dashboard_service.py` (reads 8 model types across auth, chores, meals, grocery, finance, tasks)
- `backend/app/services/nudges_service.py` (reads task_instances, routines, personal_tasks, events, parent_action_items - cross-cutting)
- `backend/app/ai/tools.py` (AI tools for chores, tasks, meals, grocery, finance)
- `backend/app/ai/orchestrator.py` (writes parent_action_items, reads everything)
- `scout-ui/lib/types.ts` (all domain types)
- `scout-ui/lib/api.ts` (all API functions)

Recommendation: each Phase 3 PR's consumer audit must call out if it touches any of these 6 files, and if so, what fraction.

---

## 6. Migration number range (Item 6)

**Next available: 053.**

Confirmed by:
- `Glob backend/migrations/*.sql` highest result: `052_normalize_046_collision.sql`.
- Same result in the mirror at `database/migrations/`.
- The 046a/046b pair (`046a_push_notifications.sql`, `046b_ai_conversation_resume.sql`) is a historical resolved artifact; migration 052 normalized the tracker entries. No forward conflict.

**In-flight work check:** Diffed `main..origin/<branch>` for every remote branch (via `git ls-remote --heads origin`). No branch has migrations past 052. The recent branches (`chore/app-json-ios-config`, `chore/eas-config-and-lockfile`, `deploy-verify`, `docs/*`) carry the same 050/051/052 set as main.

**v3 reservation of 053-080:** consistent with reality. 27 numbers available for the sprint; v3 estimates 13-17 PRs with migrations in 5-8 of them. Comfortable margin.

**Recommendation:** Lock numbers at commit time per PR. Do not pre-reserve beyond what's in the PR body. If a concurrent sprint starts, numbers past `053+N` stay available.

---

## 7. Open questions v3 should answer (Item 7)

v3 does not address:

1. **Orphan blobs in Supabase Storage** (new, from §3.3). Purge or leave?

2. **AI-enabled during window.** §6 offers three options for AI quiesce, but doesn't pick one. Recommend option (c) (don't chat) with optional belt-and-suspenders `SCOUT_AI_ENABLED=false`. Plan should commit to one.

3. **Bootstrap flag lifecycle.** The plan says "Re-authenticate self" but doesn't name the env var (`SCOUT_ENABLE_BOOTSTRAP`), the endpoint (`POST /api/auth/bootstrap`), or the flip-off-after-bootstrap step. Adding these 3 lines makes Phase 5 concrete.

4. **Phase 5 checklist item #4 assumes an unbuilt feature.** "Chore creation via Scout AI produces a scout.task_template row" - there is no AI tool for creating chore templates. `backend/app/ai/tools.py:40` lists `mark_chore_or_routine_complete` but no `create_chore_template`. Either:
   - (a) Change the checklist to "Chore creation via admin UI (`/admin/chores/new`) produces a scout.task_template row", which is the real flow, OR
   - (b) Note that a new AI tool must ship before the checklist is runnable.
   Recommend (a).

5. **Frontend token handling across clean slate.** scout-ui stores the session token client-side. After Phase 1 truncates `public.sessions`, the stored token returns 401 from `/api/auth/me`. Does the UI redirect to login gracefully, or crash? Not a blocker for Andrew (single user, can force-refresh), but worth confirming the login page renders without backend data.

6. **`scout.standards_of_done` table is FK-referenced but apparently never created.** §4.3 above. This is a silent pre-existing bug. Phase 2 PR 2.2 should include it in the create list.

7. **Two more action types in parent_action_items CHECK.** The audit listed 4 values; migrations have added more across sprints (`meal_plan_review`, `moderation_alert`, `daily_brief`, `weekly_retro`, `anomaly_alert`). When rebuilding `scout.parent_action_items` fresh in Phase 2, the CHECK list must include all currently-extant values. Source of truth: grep migrations `*.sql` for `action_type IN (`.

8. **Migration mirror dropped in Phase 1?** The repo keeps `backend/migrations/` mirrored at `database/migrations/`. The v3 plan doesn't explicitly say to mirror drop migrations. Assume yes (consistent with house convention), but make it explicit.

9. **`public.scout_scheduled_runs` truncate ordering.** §1 above flags that the truncate must happen inside the quiesce window, not before. Add to Phase 0 sub-step ordering.

10. **Smoke-deployed re-enable mechanism.** §5 Phase 0 says "disable smoke auto-trigger" and §5 Phase 5 PR 5.2 says "re-enable." Mechanism hasn't been named. Assuming it's a workflow `on: push: branches-ignore:` edit in `.github/workflows/`, but the plan should prescribe the exact file and line.

11. **`SCOUT_ENVIRONMENT` vs `SCOUT_ENABLE_BOOTSTRAP`.** Conflict risk: `config.py` has `environment: str = "development"`. If production config has `SCOUT_ENVIRONMENT=production` AND `SCOUT_ENABLE_BOOTSTRAP=true` at the same time, the startup validator (lines 146-149) emits a warning. Not fatal - just noise - but Andrew should know to expect the warning during the sprint.

12. **CLAUDE.md / memory entries.** `feedback_batch_cleanup_pattern.md` memory cites `docs/handoffs/batch_1_cleanup_pattern.md` as a path. This file may or may not exist at that literal path (the memory is the authority). v3 §12 checklist references it as "re-read" - confirm the file is readable before Phase 0.

---

## 8. Plan-vs-reality discrepancies (Item 8)

Evidence-based list of places where v3 does not match the actual repo.

1. **§6 scheduler jobs list is 4; actual is 8.** Add the 4 missing: `_run_weekly_retro`, `_run_moderation_digest`, `run_push_receipt_poll_tick`, `process_pending_dispatches_tick`.

2. **§5 Phase 0 Supabase Auth pre-flight.** Based on false premise. There is no Supabase Auth integration - only Supabase Storage. Rewrite as "clean up attachments bucket (optional)" or delete.

3. **§6 quiesce mechanism ambiguity.** "env var, config flag, or commenting out" - prescribe the single mechanism: `SCOUT_SCHEDULER_ENABLED=false`.

4. **§5 Phase 5 item #4 (chore creation via AI).** No such AI tool exists. Rewrite checklist item.

5. **§5 Phase 1 PR 1.3 "keep scout.* tables that will be retained (nudge_* series, etc.)".** Enumerate the keep list explicitly: `scout.nudge_dispatches`, `scout.nudge_dispatch_items`, `scout.nudge_rules`, `scout.quiet_hours_family`, `scout.push_devices`, `scout.push_deliveries`, `scout.home_zones`, `scout.home_assets`, `scout.maintenance_templates`, `scout.maintenance_instances`, `scout.affirmations`, `scout.affirmation_feedback`, `scout.affirmation_delivery_log`, `scout.connectors`, `scout.connector_accounts`, `scout.household_rules`, `scout.reward_policies`.

6. **§5 Phase 2 PR 2.1 "Native scout.* tables, not shims over public.*"** - plan implies `scout.sessions` becomes native. Re-read v3 §3: "`public.sessions`: Truncate allowed as approved exception. Schema preserved." Contradiction: is `sessions` native in scout (PR 2.1) or preserved in public (§3)? Resolution: §3 is correct - sessions stays in public, truncated only. Update PR 2.1 domain list to drop `scout.sessions` from the "native scout" list.

7. **§8 stop-condition "Supabase Auth pre-flight reveals an unknown mechanism"** - now n/a. Remove.

8. **§12 executive readiness checklist references `docs/handoffs/batch_1_cleanup_pattern.md`.** Verify the file exists at that exact path before Phase 0.

9. **Estimated PR count 13-17.** Probably understates Phase 3 rewiring. With 28 active-consumer tables across 200+ files, 4-5 Phase 3 PRs is achievable but on the upper end - 5-7 more likely. Adjust the range to "13-20" or split Phase 3 PRs more finely.

10. **§10 wall-clock estimate "2-3 calendar days."** Phase 3 rewiring estimate of "5-8 hours" does not match the consumer-surface reality. With 200+ files and mandatory per-PR consumer audits including DB-side dependencies (§7 of v3), expect Phase 3 to take 8-12 hours minimum. Net sprint: 3-4 calendar days, not 2-3.

---

## 9. Recommendations for v3 update

Priority-ordered list of edits Andrew should make before paste-to-Code:

**Must-fix (plan is wrong or incomplete):**

1. Rewrite §5 Phase 0 Supabase Auth pre-flight - replace with the concrete "truncate user_accounts + sessions; set SCOUT_ENABLE_BOOTSTRAP=true" step.
2. Remove §8 stop-condition about Supabase Auth.
3. Replace §6 scheduler job list with the full 8 (or delete the enumeration and just say "all 8 jobs in `backend/app/scheduler.py`").
4. §6 prescribe `SCOUT_SCHEDULER_ENABLED=false` as THE mechanism.
5. §5 Phase 5 checklist item #4 - reword to use admin UI, not Scout AI.
6. §3 add ordering note: truncate `scout_scheduled_runs` only AFTER quiesce completes.

**Should-fix (plan is ambiguous):**

7. §5 Phase 1 PR 1.3 - enumerate the keep list (§5.1 above has the list).
8. §5 Phase 2 PR 2.1 - drop `scout.sessions` from "native scout" (stays in public per §3).
9. §5 Phase 5 add: re-authentication endpoint is `POST /api/auth/bootstrap`, requires `SCOUT_ENABLE_BOOTSTRAP=true`, set the flag back to `false` after first login.
10. §10 adjust wall-clock to 3-4 calendar days; PR count to 13-20.

**Nice-to-fix (explicit call-outs):**

11. Add §3.3 orphan-blobs decision to the plan.
12. Add §7 "AI quiesce strategy: recommend option (c) don't chat during window; optional `SCOUT_AI_ENABLED=false`."
13. Add `scout.standards_of_done` to Phase 2 PR 2.2 create list.
14. Note migration-mirror (`database/migrations/`) applies to drop migrations too.

---

## 10. Appendix A: Canonical schema inventory

Full 59-table inventory produced by schema-audit subagent. Grouped by Phase 2 PR.

### PR 2.1 - Identity (12 tables)

| scout.* table | Replaces | Create-fresh? |
|---------------|----------|---------------|
| families | public.families | yes (clean slate) |
| family_members | public.family_members | yes |
| user_accounts | public.user_accounts | yes |
| sessions | public.sessions | **NO - stays in public per §3** |
| role_tiers | public.role_tiers | yes |
| role_tier_overrides | public.role_tier_overrides | yes |
| member_config | public.member_config | yes |
| permissions | n/a (already canonical) | keep |
| role_tier_permissions | n/a | keep |
| user_family_memberships | n/a | keep (unwired, leave alone) |
| user_preferences | n/a | keep |
| device_registrations | n/a | keep |

### PR 2.2 - Chores + tasks (12 tables)

| scout.* table | Replaces | Notes |
|---------------|----------|-------|
| task_templates | public.chore_templates | **must include 7 scope-contract fields native** |
| routine_templates | public.routines | keep (already exists, clean-slate rebuild) |
| routine_steps | public.routine_steps | promote from UNCLEAR, create fresh |
| standards_of_done | n/a | **create fresh - appears to be missing** |
| task_occurrences | public.task_instances | rename + clean-slate |
| task_assignment_rules | already canonical | keep |
| task_completions | n/a | keep |
| task_exceptions | n/a | keep |
| task_notes | n/a | keep |
| task_occurrence_step_completions | public.task_instance_step_completions | create fresh |
| daily_win_results | public.daily_wins | keep |
| personal_tasks | public.personal_tasks | validate during Phase 5 bootstrap |

### PR 2.3 - AI (5 scout.ai_* + existing scout.nudge_*)

| scout.* table | Replaces | Notes |
|---------------|----------|-------|
| ai_conversations | public.ai_conversations | create fresh, mirror column shapes from migrations 010/014/015/019/046b |
| ai_messages | public.ai_messages | preserve `metadata` SQL column name (reserved-word issue) |
| ai_tool_audit | public.ai_tool_audit | create fresh |
| ai_daily_insights | public.ai_daily_insights | create fresh |
| ai_homework_sessions | public.ai_homework_sessions | preserve subject CHECK from migration 018 |
| nudge_dispatches / nudge_dispatch_items / nudge_rules / quiet_hours_family | n/a | keep (sprint 05) |

### PR 2.4 - Remaining (30 tables)

**Meals (5):** meal_weekly_plans, meal_plan_entries, meal_staples, meal_reviews, member_dietary_preferences.

**Grocery + purchases (2):** grocery_items, purchase_requests.

**Home maintenance (4, all already exist):** home_zones, home_assets, maintenance_templates, maintenance_instances.

**Affirmations (3, all already exist):** affirmations, affirmation_feedback, affirmation_delivery_log.

**Parent action items (1):** parent_action_items. Rebuild with full CHECK vocabulary: `grocery_review`, `purchase_request`, `chore_override`, `general`, `meal_plan_review`, `moderation_alert`, `daily_brief`, `weekly_retro`, `anomaly_alert`.

**Projects (6):** project_templates, project_template_tasks, projects, project_tasks, project_milestones, project_budget_entries.

**Calendar (2):** time_blocks, calendar_exports.

**Connectors (6, most already exist):** external_calendar_events, work_context_events, budget_snapshots, bill_snapshots, activity_events, travel_estimates. Plus existing connectors/connector_accounts/sync_jobs/etc.

**Push (2, already exist):** push_devices, push_deliveries.

**Rewards (6):** reward_policies (exists), allowance_periods, allowance_results, reward_extras_catalog, reward_ledger_entries, settlement_batches, greenlight_exports.

Full column / FK / index list available from the schema-audit subagent output.

---

## 11. Appendix B: Consumer surface map

Heavy hits are listed in §5.2. Full per-table file list from the consumer-audit subagent is too long for this document - if Andrew wants it inline, it's ~2500 words. Alternative: retain the subagent output as `docs/plans/_drafts/2026-04-22_v3_realitycheck_consumer_map.md`.

**Consumer audit checklist template for per-PR handoffs** (built from the subagent's structure):

```
## Consumers found

### Source code (repo-wide grep)
Searched for: <legacy_table>, <ORM class name>
Scope: backend/, scout-ui/, smoke-tests/, scripts/, migrations/, docs/
Matches: <N files>
Updated: <list>
Intentionally skipped: <list with reason>

### Database-side dependencies
- Views: <queried information_schema.views>
- Triggers: <queried information_schema.triggers>
- Functions: <queried pg_proc>
- Grants / policies: <queried information_schema.role_table_grants>
- Indexes: <queried pg_indexes>
- Default expressions: <queried pg_attrdef>
- FK references from retained scout.* tables: <queried information_schema.referential_constraints>

### Handled / Skipped
<for each: updated | dropped | intentionally left | not applicable>
```

Non-negotiable per v3 §7.

---

## 12. Summary for Andrew

**Plan is mostly implementable as written.** 8 items checked. Findings:

- Green: FK safety (§1), migration number (§6), quiesce mechanism (§2 - simpler than plan suggests), bootstrap mechanism (§3 - already exists).
- Yellow: canonical schema inventory (§4 - 59 tables, mostly scope-contract fields on task_templates is the main new requirement), consumer surface (§5 - 200+ files, which suggests Phase 3 takes 8-12 hours not 5-8).
- Red: Supabase Auth pre-flight (§3 - based on false premise, delete from plan), scheduler job list (§2 - 4 jobs missing), Phase 5 checklist item #4 (§7 - assumes an unbuilt AI tool).

**Minimum v3 edits before execution:** items 1-6 from §9 recommendations.

**Execution readiness:** after the plan edits, everything needed to run is grounded. No new unknowns. All mechanisms (quiesce, truncate, bootstrap, drop-order) are present in the codebase today.

**Stand down until Andrew decides.** This is advisory.
