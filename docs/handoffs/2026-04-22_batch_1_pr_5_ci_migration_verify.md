# Batch 1 PR 5 handoff — CI + migration apply verification

**Branch:** `batch-1/pr-5-ci-migration-verify`
**Base:** main at `5735d54` (PR 4 squash merge)
**Pulled from:** gap analysis items #3 + `open_items.md` migration-apply
line items. Last PR in Batch 1.

## Summary

Flipped the `smoke-deployed` CI job from `workflow_dispatch`-only to
auto-trigger on push-to-main. Verified migrations 040-044 are applied
on Railway (they are; no action needed). Aligned the smoke-account
secret name across Railway env vars, GitHub secrets, workflow, and
docs to `SCOUT_SMOKE_ADULT_PASSWORD`. Rotated the smoke password
mid-PR because a prior step printed it into the Claude Code transcript.

No schema change, no new routes, no new config keys. Two files
modified in this PR (`.github/workflows/ci.yml` and
`docs/release_candidate_report.md`) plus this handoff.

## Items shipped

### Item 1: `smoke-deployed` trigger flip

Before:

```yaml
if: github.event_name == 'workflow_dispatch'
```

After:

```yaml
if: github.event_name == 'push' || github.event_name == 'workflow_dispatch'
```

The top-level `on:` block already filters `push` to `main` + `release-*`
branches, so the job runs on push-to-main and operator-invoked
`workflow_dispatch` but NOT on pull_request events (PRs have not
deployed).

Two secondary fixes were required so the auto-triggered path works
without operator-supplied `workflow_dispatch` inputs:

- `SCOUT_WEB_URL` and `SCOUT_API_URL` gained `|| 'https://...'`
  fallbacks to the known production URLs. On `workflow_dispatch`
  the operator can still override via inputs; on push the defaults
  apply.
- `npx playwright test ${{ ... }}` gained a fallback test-file list
  matching the prod-safe default from the workflow_dispatch inputs
  (`tests/auth.spec.ts tests/surfaces.spec.ts tests/responsive.spec.ts
  tests/dev-mode.spec.ts`). No write paths against prod.

Top-of-file comment updated to reflect the new behavior and to cite
the provisioning history of the smoke account (2026-04-13) plus the
GitHub secrets the workflow reads.

### Item 2: verify 040-044 applied on Railway

One-line note: **all five are applied.** Query against Railway's
`_scout_migrations` table returned:

```
040_phase2_permissions.sql
041_chore_scope_contract.sql
042_home_maintenance.sql
043_home_maintenance_permissions.sql
044_meal_base_cooks.sql
```

Filenames match the repo copies exactly. The 2026-04-20 session
handoff's "Apply migrations 040-044 on Railway" item is verified
complete. No action needed; this note exists so a future gap-analysis
agent sees the verification trail and does not re-flag it.

### Secret-naming alignment (side-work)

Discovered mid-PR that the GitHub Actions workflow referenced
`secrets.SCOUT_SMOKE_PASSWORD` while Railway stored
`SCOUT_SMOKE_ADULT_PASSWORD`, and the two doc files disagreed with
each other. Option 3 from the earlier investigation was chosen:
align everything to `SCOUT_SMOKE_ADULT_PASSWORD` (Railway's name).

Changes:
- `ci.yml` reference updated to `secrets.SCOUT_SMOKE_ADULT_PASSWORD`
  plus the error-message text in the guard
- `docs/release_candidate_report.md` updated to the aligned name
  (the only live-tree doc that still used the old form;
  `docs/private_launch.md` already used the correct name)

### Password rotation (side-work)

The smoke password was printed in a prior `railway variables` output
inside the Claude Code transcript. Rotated as a low-stakes hygiene
step:

1. Generated a new 43-char URL-safe token
2. UPDATEd `user_accounts.password_hash` on Railway with the new
   bcrypt hash (exactly 1 row touched; verified via
   `POST /api/auth/login` round-trip returning 200)
3. Updated Railway env var `SCOUT_SMOKE_ADULT_PASSWORD` to the new
   value (`--skip-deploys` so no redundant redeploy)
4. User set the new token as the GitHub secret
   `SCOUT_SMOKE_ADULT_PASSWORD`

DB update happened before the env-var update so operators who read
the Railway value always see a value that matches the current
auth state.

## Verification

- `node scripts/architecture-check.js`: 0 WARN, 1 INFO. Fifth PR
  in a row with identical seedData INFO content (constants A,
  ACTION_INBOX, ACTIVITY, ALLOWANCE, B, BATCH_COOK, C, CHORES_TODAY,
  FAMILY, G, GROCERY, H, HOMEWORK, I, L, LEADERBOARD, M,
  MEALS_THIS_WEEK, P, R, S still imported by `scout-ui/app/`).
  **Task #42 watch officially concludes: pre-existing background
  noise, not introduced by any Batch 1 PR. Task #45 tracks filing
  it as its own ticket.**
- `py -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`:
  valid YAML
- GitHub API query on `repos/papadrew1182/Scout/actions/secrets`:
  returns both `SCOUT_SMOKE_ADULT_EMAIL` and
  `SCOUT_SMOKE_ADULT_PASSWORD` with recent created_at timestamps
- Production login test with new password: 200 OK

## Not in scope

- Child smoke account provisioning. The default test list does not
  exercise child surfaces, so `SCOUT_SMOKE_CHILD_EMAIL` stays as
  a currently-empty secret reference. The workflow tolerates
  absence (only `ADULT_EMAIL` and `ADULT_PASSWORD` are load-bearing
  in the guard).
- Migrating the smoke-account provisioning script from
  `/tmp/full_smoke_verify.py` (which no longer exists) into
  `scripts/`. Would be clean hygiene but unrelated to Batch 1.
- Expanding the deployed smoke test list to cover write paths
  once write-path smoke data is isolated from the real Roberts
  family. Separate sprint work.

---

# Batch 1 retrospective

## What shipped

Five serial PRs, all squash-merged:

| PR | What | Commit |
|---|---|---|
| #59 Nudges hygiene | 3 items: mixed-kind action_type documented with regression test, empty-body dedupe key hardened, `_strip_tz` symmetry in throttle helpers | `03d8de2` |
| #60 AI chat polish | 4 items: `SAMPLE_THREAD` dead-code removal, permission-denial test skip-with-reason, `sendChatMessage` dead-function deletion (reshaped from timeout investigation), prompt-cache hit-rate surfaced in `ai_cost_report.py` | `159f91e` |
| #61 Seed Roberts zone pack | 1 item: 6 zones seeded idempotently. Base-cook staples item pulled during review (content belongs in admin UI, not a seed) | `6b2ebbc` |
| #62 Sprint 05 trust items | 2 items: 046 filename collision renamed to 046a + 046b with a normalize migration 052 handling the `_scout_migrations` tracker flip, flaky `TestScannerStampsOccurrence` tests hardened pre-emptively by removing `_utcnow()` wall-clock dependency | `5735d54` |
| #63 CI + migration verify | This PR: smoke-deployed trigger flip, 040-044 verification, secret-naming alignment, password rotation | pending |

Total backlog items shipped: **12** (9 from the 72-item dump, 3
adjacent items from the gap analysis).

## What got reshaped

- **Base-cook staples (PR 3 Item 1).** Originally scoped as a seed
  addition. Pulled during review. Staple content belongs in the
  admin UI once that surface ships; don't hardcode family-specific
  taste in `seed_smoke.py`. Re-flagged as task #47 for the admin
  UI sweep.
- **sendChatMessage 60s timeout (PR 2 Item 3).** Originally scoped
  as "investigate runtime behavior, doc findings." Investigation
  revealed the function had zero callers. Reshaped to dead-code
  removal, which closed the backlog item more definitively than a
  runtime probe would have.
- **Flaky `test_overdue_task_scanner_stamps_due_at` (PR 4 Item 2).**
  Originally scoped as "root-cause-and-fix or skip-with-issue."
  Couldn't reproduce the claimed DST-boundary flake under current
  conditions (evidence was narrow: 5 consecutive test runs in one
  wall-clock window, 96-datetime DB roundtrip probe, 15-run CI
  history check). Reshaped as a pre-emptive structural fix
  removing the `_utcnow()` wall-clock dependency. Handoff on that
  PR records the specific conditions my evidence did not cover so
  a future debugger has the trail if it flakes again.
- **Password rotation (PR 5 side-work).** Not in original scope.
  Added after realizing the current password got printed into the
  Claude Code transcript. Low-stakes hygiene.

## What got deferred

- **Seed base-cook staples** → task #47 (closes when admin UI
  accepts staple content)
- **Child smoke account** → not blocking; default test list is
  adult-only
- **Production smoke-account provisioning script** → still lives
  only in docs; migrating into `scripts/` is a separate cleanup

## Task-list status at end of batch

- Completed: #41 (PR 1), #43 (PR 2 scope guard resolved), #44 (PR 2), #46 (PR 3), #48 (PR 4), #49 (PR 5)
- Carrying forward: #42 (seedData watch, confirmed pre-existing, rolls into #45), #45 (gap item to file the seedData INFO as its own XS/S ticket), #47 (base-cook staples → admin UI)

## Remaining backlog snapshot

Starting count was 72 items from the 72-item dump. Batch 1 shipped
9 directly plus 3 adjacent gap-analysis items. Approximate remaining
shape:

| Domain | Before | Shipped | Remaining |
|---|---|---|---|
| ai-chat | 15 | 4 | 11 |
| nudges | 10 | 3 | 7 |
| projects | 6 | 0 | 6 |
| ops | 6 | 2 | 4 (gap items #3 rename and `smoke-deployed` flip shipped as adjacent; 4 orig-dump ops items remain) |
| ui-polish | 5 | 0 | 5 |
| meals | 5 | 0 | 5 |
| home-maintenance | 4 | 1 | 3 |
| admin | 3 | 0 | 3 |
| chores | 3 | 0 | 3 |
| affirmations | 3 | 0 | 3 |
| push | 3 | 0 | 3 |
| tests | 3 | 1 | 2 |
| grocery | 2 | 0 | 2 |
| connectors | 2 | 0 | 2 |
| allowance | 1 | 0 | 1 |

**Total remaining: approximately 60 items** (72 - 12 shipped; rough
accounting because some items were reshaped across domain
boundaries).

## Signals worth carrying forward

- **The "don't paper over" rule worked.** Three times in Batch 1 I
  stopped for user judgment rather than forcing something through:
  the sendChatMessage reshape (PR 2), the base-cook staples pull
  (PR 3), and the smoke-account secret naming (PR 5). Each was a
  short pause that prevented a worse outcome than shipping the
  original scope would have.
- **Serial execution + per-PR handoff docs** produced a trail that
  caught at least two mistakes: the stale `SCOUT_SMOKE_PASSWORD`
  name (caught by the gap-analysis-style grep in PR 5) and the
  flaky-test evidence over-claim (caught by user review on PR 4).
- **Task #42 seedData INFO watch.** Adding a specific watch task at
  the start of the batch made the "this INFO is pre-existing noise"
  conclusion evidence-based rather than asserted. Pattern worth
  repeating for any future persistent arch-check INFO.
- **Railway + Vercel + main CI verification** as the post-merge
  checkpoint has caught zero real issues across 5 merges but has
  been critical for the PR 4 migration flip verification (the
  tracker-cleanup confirmation was only possible because we
  explicitly queried the prod DB post-deploy).

## On Andrew's plate

- Review PR 5 when opened
- Squash-merge
- Confirm Railway + Vercel deploys green post-merge (no migration
  in this PR; simpler cycle than PR 4)
- Watch the first auto-triggered `smoke-deployed` run on the merge
  commit. Default test list is read-only so failure modes are
  auth or network; if it fails, investigate before the next push
- Optional: delete the local `batch-1/pr-5-ci-migration-verify`
  branch after merge

## Meta-notes for the batch

- Task #42 (seedData INFO drift watch): closed out by conclusion
  on this PR. Pre-existing background noise confirmed. Work
  transfers to #45.
- Task #49 (PR 5): complete on merge.
- All of Batch 1 ships end-to-end.
