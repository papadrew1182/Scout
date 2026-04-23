# Batch 1 stabilization handoff — child account + /personal smoke fix

**Branch:** `batch-1/stabilization-child-and-personal`
**Base:** main at `0142b29` (PR 5 squash merge)
**Pulled from:** the post-merge auto-triggered `smoke-deployed` run
on PR 5, which surfaced 6 failures. Three were child-account driven
(`SMOKE_CHILD_EMAIL` was empty because the account had never been
provisioned). Three were `/personal` responsive tests timing out
on a stale selector. This PR ships both fixes together.

## Summary

Two items, one PR, since the failure investigation linked them
(both block the first push-to-main auto-triggered smoke-deployed
from going green). No schema change, no new routes, no new config
keys.

## Item 1: Provision child smoke account

The 2026-04-13 adult smoke account (smoke@scout.app) was created
by an ad-hoc `/tmp/full_smoke_verify.py` script that never made it
into the repo. That was the antipattern this PR refuses to repeat.

**What shipped:**

- `scripts/provision_smoke_child.py` - repo-committed, idempotent
  Python script. Mirrors the adult pattern but lives in version
  control. Uses the same `backend/app/services/auth_service.hash_password`
  (bcrypt). Pre-checks with SELECT-first guards before any INSERT;
  refuses to run if more than one row matches a unique WHERE. Single
  transaction wrapping all DB writes. Live login round-trip against
  prod as the final sanity check before printing the token.

- Applied against Railway:
  - Created scout.family_members row: `first_name=Smoke-Child`,
    `last_name=Roberts`, `role=child`, `birthdate=2015-01-01`,
    `is_active=true`
  - Created scout.user_accounts row: `email=smoke-child@scout.app`,
    `auth_provider=email`, `is_primary=false`, `is_active=true`,
    `password_hash` = bcrypt of a fresh 43-char URL-safe token
  - Created scout.role_tier_overrides row pointing the family_member
    at the `CHILD` tier (UPPERCASE, post-migration 034)
  - Live login round-trip to
    `https://scout-backend-production-9991.up.railway.app/api/auth/login`
    returned 200 with a session token

- Railway env vars set on `scout-backend` service:
  - `SCOUT_SMOKE_CHILD_EMAIL` = `smoke-child@scout.app`
  - `SCOUT_SMOKE_CHILD_PASSWORD` = (43-char URL-safe token)

- GitHub repo secrets set (by Andrew via the dashboard):
  - `SCOUT_SMOKE_CHILD_EMAIL`
  - `SCOUT_SMOKE_CHILD_PASSWORD`

- `.github/workflows/ci.yml` `smoke-deployed` job exposes a new
  `SMOKE_CHILD_PASSWORD` env var from
  `secrets.SCOUT_SMOKE_CHILD_PASSWORD`

- 7 smoke spec files updated to use the child-specific password:
  - `auth.spec.ts`, `surfaces.spec.ts`, `affirmations.spec.ts`,
    `ai-panel.spec.ts`, `chore-ops.spec.ts`, `data-entry.spec.ts`,
    `write-paths.spec.ts`
  - Each gets a new constant
    `const CHILD_PASSWORD = process.env.SMOKE_CHILD_PASSWORD || "testpass123";`
  - 9 total `login(page, CHILD_EMAIL, PASSWORD)` call sites flipped
    to `login(page, CHILD_EMAIL, CHILD_PASSWORD)`

The option chosen here was "separate child password." The simpler
path would have been to reuse the adult's password (smoke tests
currently use a single `SMOKE_PASSWORD` for both accounts), but the
product call was to maintain credential separation even at smoke
scale. Documented as option B in the earlier design discussion; the
scope cost was the 9 call-site edits and the new env var layer, not
unreasonable.

## Item 2: /personal responsive + nav smoke fix

**What was actually failing:**

The PR 5 post-merge `smoke-deployed` run listed 3 `/personal`
responsive tests timing out on `waitForSelector('text=Andrew\'s Dashboard')`.
Andrew's manual check confirmed `/personal` renders fine in prod.

Investigation traced the stale selector to two files:
`smoke-tests/tests/responsive.spec.ts:22` and
`smoke-tests/tests/interaction-audit.spec.ts:23`. Both used the
literal string `"Andrew's Dashboard"` as the wait-for-ready selector
on `/personal`.

**Why the string was wrong:**

`scout-ui/app/personal/index.tsx:181-183` renders the heading as
`${member.first_name}'s Dashboard`, dynamically interpolating the
logged-in member's first name. The smoke tests run as
`smoke@scout.app` (first_name = "Smoke"), so the page actually
renders `"Smoke's Dashboard"`, not `"Andrew's Dashboard"`. The
hardcoded string was a relic from when the test ran against an
account whose first_name was Andrew.

**The fix:**

Both files now anchor on `"Top 5 tasks"` - an unconditionally-rendered
card title in `scout-ui/app/personal/index.tsx:229`. Chosen because:

- Plain ASCII (no Unicode middle-dot like `"Calendar · This week"`
  which could introduce escaping concerns)
- Distinctive phrasing unlikely to collide with other routes
- Verified to render unconditionally (card title renders regardless
  of whether the task list has data; empty state shows "No tasks -
  you're all caught up!" as the body but the title is always there)
- Surface-identifying - clearly belongs to the `/personal` dashboard

An inline comment in both files explains the choice so a future
engineer does not re-couple the test to the (still-dynamic) heading.

## Verification

- `scripts/provision_smoke_child.py` executed cleanly against
  Railway; created 3 rows (family_member, user_account, role_tier_override)
  in a single transaction; live login round-trip returned 200
- `grep -n "Andrew's Dashboard" smoke-tests/tests/*.spec.ts` returns
  zero hits in the live tree (ignoring orphaned worktrees)
- `grep -c "login(page, CHILD_EMAIL, PASSWORD)" smoke-tests/tests/*.spec.ts`
  returns zero hits; all 9 sites flipped to `CHILD_PASSWORD`
- `gh api repos/papadrew1182/Scout/actions/secrets` returns 4 secrets:
  `SCOUT_SMOKE_ADULT_EMAIL`, `SCOUT_SMOKE_ADULT_PASSWORD`,
  `SCOUT_SMOKE_CHILD_EMAIL`, `SCOUT_SMOKE_CHILD_PASSWORD`
- `node scripts/architecture-check.js`: 0 WARN, 1 INFO (same
  pre-existing seedData drift from Batch 1 - not touched here)

## Expected effect on next smoke-deployed run

The previous failed run reported 6 failures. Expected breakdown
after this PR merges:

| Previous failure | Root cause | Fix in this PR |
|---|---|---|
| auth.spec.ts:33 `child can sign in` | empty SMOKE_CHILD_EMAIL | ✓ |
| surfaces.spec.ts:65 `settings loads for child` | empty SMOKE_CHILD_EMAIL | ✓ |
| surfaces.spec.ts:70 `child does NOT see Accounts & Access` | empty SMOKE_CHILD_EMAIL | ✓ |
| responsive.spec.ts:39 desktop `/personal has no horizontal overflow` | stale selector | ✓ |
| responsive.spec.ts:39 iPhone-portrait `/personal has no horizontal overflow` | stale selector | ✓ |
| responsive.spec.ts:39 iPhone-landscape `/personal has no horizontal overflow` | stale selector | ✓ |

All 6 failures should resolve. If any other smoke test was
coincidentally touching the same stale selector or credential state,
it would surface on the auto-triggered post-merge run.

## Not in scope

- `interaction-contract.spec.ts` imports `CHILD_EMAIL` but never
  calls `login(page, CHILD_EMAIL, ...)`. Dead import. Left alone
  (scope discipline - unused-import cleanup is a separate hygiene
  pass).
- Rotating other accounts or migrating the adult's provisioning
  script (`/tmp/full_smoke_verify.py`) into the repo. The new child
  script is the template if anyone wants to do that follow-up.
- Additional selector anti-fragility sweeps across other smoke
  specs. Only the two files that referenced `"Andrew's Dashboard"`
  are touched here.

## On Andrew's plate

- Review PR 6 when opened
- Squash-merge
- **Watch the auto-triggered `smoke-deployed` run on the merge
  commit.** If all 6 previously-failing tests now pass, Batch 1 is
  officially done. If any still fail, investigate before the next
  push.
- Optional: delete the local stabilization branch after merge

## Meta

- Task #50 (child account provisioning): complete on merge
- Task #47 (base-cook staples -> admin UI sweep): still pending;
  carries into Batch 2
- Task #45 (seedData INFO ticket): still pending; carries into
  Batch 2
- Batch 1 retrospective was written up in PR 5's handoff
  (`docs/handoffs/2026-04-22_batch_1_pr_5_ci_migration_verify.md`).
  This PR is the stabilization tail of that batch and does not have
  a separate retrospective.
