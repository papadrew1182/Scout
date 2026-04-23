# Canonical rewrite sprint - re-enable checklist

**Purpose:** single checklist of everything the sprint disables, so Phase 5 PR 5.3 has an authoritative reversal target and nothing stays off after sprint close.

**Companion docs:**
- `docs/plans/2026-04-22_canonical_rewrite_v5_1_merged.md` (execution plan)
- `docs/plans/2026-04-22_canonical_rewrite_v5_preflight.md` (facts baseline)
- `docs/plans/_snapshots/README.md` (pre-sprint snapshot process)

---

## 1. Railway environment variables

Each env var is flipped at the start of the sprint and flipped back at the end. Each flip is a manual operator action by Andrew (Claude does not have Railway credentials).

| Env var | Set at | Set by | Revert at | Revert by | Notes |
|---------|--------|--------|-----------|-----------|-------|
| `SCOUT_SCHEDULER_ENABLED` | Phase 0 manual ops (after PR 0.2 merges) | Andrew | Phase 5 PR 5.3 step 1 via `scripts/unquiesce_prod.py --full` | Andrew | Sprint value: `false`. Revert: `true` (or delete; default is `true`). |
| `SCOUT_ENABLE_BOOTSTRAP` | Phase 0 manual ops | Andrew | Phase 5 PR 5.3 step 1 via `scripts/unquiesce_prod.py --full` | Andrew | Sprint value: `true`. Revert: `false`. Startup warns while enabled in prod. |
| `SCOUT_AI_ENABLED` | Phase 0 manual ops | Andrew | Phase 5 PR 5.2 via `scripts/unquiesce_prod.py --ai-only` | Andrew | Sprint value: `false`. Revert: `true` (or delete; default unset = enabled per config). |

**Verification at revert time:**

```bash
# From Railway dashboard or CLI after unquiesce script runs:
# - scheduler runs a tick within 5 minutes (check public.scout_scheduled_runs)
# - /api/ready returns ai_available: true
# - /api/auth/bootstrap returns 403 (bootstrap disabled)
```

---

## 2. GitHub Actions / CI

| Change | Set at | Set by | Revert at | Revert by | Notes |
|--------|--------|--------|-----------|-----------|-------|
| `.github/workflows/ci.yml` `smoke-deployed.if:` | Phase 0 PR 0.1 | Claude via PR | Phase 5 PR 5.3 step 4 | Claude via PR | Sprint value: `if: github.event_name == 'workflow_dispatch'`. Revert: `if: github.event_name == 'push' \|\| github.event_name == 'workflow_dispatch'`. Restores the original comment block verbatim. |

**Exact diff to revert** (for Phase 5 PR 5.3 to apply):

```diff
   smoke-deployed:
-    # Runs Playwright against the real Vercel + Railway deploy.
-    #
-    # TEMPORARY (canonical rewrite sprint 2026-04-23): auto-trigger on
-    # push-to-main is DISABLED for the duration of Phase 1 through Phase 5.
-    # The scout.* schema is being rebuilt; auto-running smoke against prod
-    # mid-sprint would fail and produce noise. Workflow_dispatch remains
-    # available for operator-initiated runs outside the maintenance window.
-    #
-    # Reversal: Phase 5 PR 5.3 restores the original `if:` clause
-    #   (`github.event_name == 'push' || github.event_name == 'workflow_dispatch'`)
-    # after scripts/unquiesce_prod.py --full has confirmed green.
-    #
-    # Originally: runs on push-to-main + release-* (top-level on: filters);
-    # available via workflow_dispatch; does NOT run on pull_request.
-    if: github.event_name == 'workflow_dispatch'
+    # Runs Playwright against the real Vercel + Railway deploy. Auto-
+    # triggered on push-to-main (top-level `on:` block filters push to
+    # main + release-*); still available via workflow_dispatch for
+    # operator-driven runs. Does NOT run on pull_request events because
+    # PRs haven't deployed.
+    if: github.event_name == 'push' || github.event_name == 'workflow_dispatch'
```

**Order of operations in Phase 5 PR 5.3** (per v5.1 §Phase 5 Step 8):

1. Flip env vars via `scripts/unquiesce_prod.py --full`. Wait for deploy green.
2. Verify first scheduler tick clean (5-minute wait + `public.scout_scheduled_runs` check).
3. Reprovision smoke accounts via `scripts/provision_smoke_child.py` and `scripts/provision_smoke_adult.py` (adult script may still be a Batch 1 pickup; create here if not done).
4. ONLY AFTER steps 1-3 complete: merge PR 5.3 to revert the `ci.yml` edit and auto-trigger smoke-deployed on the merge commit.

The first auto-smoke-run on the merge commit is the definitive rewrite validation signal.

---

## 3. Supabase Storage

| Change | Phase | Revert at | Notes |
|--------|-------|-----------|-------|
| Attachments bucket contents | Purged in Phase 0 via `scripts/quiesce_prod.py` | Not reverted | Pre-existing blobs are orphaned by the rewrite (ai_messages drops) and have no meaningful recovery path. Per v5.1 §10 "Does NOT preserve Supabase Storage blobs." |

Buckets and signed-URL infrastructure stay configured. Only the blob contents are purged.

---

## 4. Frontend / client apps

No persistent changes. Clients are closed for the duration of Phase 1 through Phase 3 (no manual user action via UI), and reopened naturally in Phase 5 bootstrap + acceptance checklist.

Expected behavior:
- Stored session tokens return 401 after Phase 1 (sessions table truncated).
- User re-logs in via bootstrap flow in Phase 5.
- Client push tokens re-register on next app launch and write `scout.push_devices`.

---

## 5. Database-side state (reseeded, not reverted)

Seed-reference tables are truncated in Phase 1 PR 1.2 and repopulated in Phase 5 PR 5.1 via a dedicated reseed migration. This is NOT a revert (the migration is new); it is an explicit reseed step. Tables:

- `scout.permissions`
- `scout.role_tier_permissions`
- `scout.connectors`
- `scout.affirmations`
- `scout.household_rules`
- `scout.time_blocks`

Per v5.1 §Phase 5 Step 2, sources for the reseed span migrations 022, 023, 034, 035, 039, 040, 043, 046a, 046b, 047, 048, 049, 050, 051. The reseed migration uses natural-key lookups only - no hardcoded IDs.

---

## 6. Manual discipline (Andrew, during the window)

- [ ] All scout-ui clients closed (mobile, web tabs) before Phase 1 begins.
- [ ] No manual DB writes for the full duration: no psql sessions, no Supabase SQL editor queries, no Supabase table editor clicks, no ad-hoc scripts beyond the named `quiesce_prod.py` / `unquiesce_prod.py`.
- [ ] No `workflow_dispatch` runs of smoke-deployed during the window.
- [ ] Don't chat with Scout AI (belt-and-suspenders alongside `SCOUT_AI_ENABLED=false`).

These are tracked in the Phase 0 handoff doc; this file is the summary.

---

## 7. Sprint closure verification

After Phase 5 PR 5.3 merges and the first auto-smoke-run passes:

- [ ] `SCOUT_SCHEDULER_ENABLED` is `true` or unset on Railway
- [ ] `SCOUT_AI_ENABLED` is `true` or unset on Railway
- [ ] `SCOUT_ENABLE_BOOTSTRAP` is `false` on Railway
- [ ] `.github/workflows/ci.yml` `smoke-deployed.if:` includes the `'push'` event again (exact text per section 2)
- [ ] `/api/ready` returns `ai_available: true`
- [ ] `/api/auth/bootstrap` returns 403
- [ ] First auto-triggered smoke-deployed run on PR 5.3's merge commit is green
- [ ] Sprint handoff doc written

---

End of checklist. This file is the single reversal reference. Update it if any sprint PR adds an additional disable step.
