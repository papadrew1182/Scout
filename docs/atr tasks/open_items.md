# Andrew's open items

Running list of things Andrew needs to handle that Claude Code cannot.
Checked items stay here for audit; once a whole group clears, archive
it to a dated file under `docs/atr tasks/archive/`.

Last updated: 2026-04-21

---

## Right now — Sprint 04 Phase 1 (AI conversation resume) — in progress

Work started in the current interactive Claude Code session on 2026-04-21.
Plan doc at `SCOUT_SPRINT_04_AI_INTELLIGENCE_LAYER.md` (repo root), with
corrections reflected against live repo (no `ScoutLauncher.tsx`, reuse
existing `status` column, etc.).

No external prerequisites. Entirely internal work.

### On Andrew's plate
- [ ] Review the Phase 1 PR when opened
- [ ] Merge the PR after review (squash, per repo convention)
- [ ] Confirm Railway backend deploy succeeds post-merge
      (per `feedback_verify_deploys` rule)
- [ ] Confirm Vercel frontend deploy succeeds post-merge
- [ ] Pull `main` locally after merge and delete the phase branch

### Scheduled trigger status
- [x] Remote cron trigger `trig_0195PNvY6e1djeKsdJz6cbZj` disabled
      2026-04-21 at Andrew's request (work being done interactively
      instead). Not deleted; edit/re-enable at
      https://claude.ai/code/scheduled/trig_0195PNvY6e1djeKsdJz6cbZj

---

## Sprint 2 — fully shipped (audit record)

All four Sprint 2 PRs merged 2026-04-21:
- #32 Sprint 2 #2: AnthropicProvider retry on 5xx / timeout
- #33 Sprint 2 #4: dietary_preferences in meal-plan generator
- #34 Sprint 2 #1: smoke-deployed CI job (manual trigger)
- #36 Sprint 2 #3: structured client_error log line for frontend crashes

No open items.

---

## Right now — PR #37 (Sprint 04 Phase 1, AI conversation resume) — MERGED + DEPLOYED

Branch: `sprint/sprint-04-ai-conversation-resume` (remote deleted)
PR: https://github.com/papadrew1182/Scout/pull/37
Merge commit: `1cff7681`

### Status
- [x] CI green on branch after a fix pass (type errors in ScoutSidebar
      + settings/ai; `adults["sally"]` → `adults["megan"]`; tz-aware
      comparisons in orchestrator hook tests)
- [x] PR #37 squash-merged to main 2026-04-21T15:16:50Z
- [x] Migration 046 applied on Railway via the public proxy URL
      (pattern from PR #38's handoff); also re-applied 045 as a no-op
      (idempotent ADD COLUMN IF NOT EXISTS)
- [x] Two new permission keys verified:
      `ai.manage_own_conversations`, `ai.clear_own_history`
- [x] Three new columns verified on `ai_conversations`:
      `title`, `last_active_at`, `is_pinned`
- [x] Post-merge CI on main: success (backend-tests, frontend-types,
      smoke-web all green; arch-check fails continue-on-error only)
- [x] Railway backend `/health` returns `{"status":"ok"}` post-merge
- [x] Vercel production deploy: success

### Minor cleanup still on Andrew's plate
- [ ] In your main repo run `git checkout main && git pull` to pull
      the squashed merge
- [ ] `git branch -d sprint/sprint-04-ai-conversation-resume` (local)
- [ ] Migration filename collision on `046_*` is cosmetic debt only
      (`046_push_notifications.sql` from PR #35 and
      `046_ai_conversation_resume.sql` from PR #37 coexist because
      migrate.py tracks by full filename). Consider renaming one in
      a follow-up if the numbering bothers you.

### Remote cron trigger
- [x] `trig_0195PNvY6e1djeKsdJz6cbZj` remains disabled. Delete it at
      https://claude.ai/code/scheduled if you want it gone entirely
      — the RemoteTrigger API does not support deletion.

### Follow-ups flagged during execution
- Recent conversations drawer UI (list with per-row rename / pin /
  archive). API is ready.
- `SAMPLE_THREAD` mock data in `ScoutSheet.tsx` + `ScoutSidebar.tsx`
  still shows when no resumable conversation exists. Replace with a
  blank state.
- Permission-denial test for `ai.manage_own_conversations` is
  currently `pytest.skip`d — no tier denies it today. Wire up if a
  `READ_ONLY` or similar tier gets added.

---

## Right now — PR #35 (Phase 1 push notifications) — MERGED

- [x] Wait for backend-tests + frontend-types CI to go green
- [x] Merge PR #35 to main (squash) — merged at commit `e5757ad`,
      closed as #35
- [x] After merge, confirm Railway deploy succeeds (backend) —
      Scout/production deployment for `e5757ad` reported success
      at 2026-04-21T05:42Z
- [x] After merge, confirm Vercel deploy succeeds (frontend) —
      Production deployment for `e5757ad` reported success
- [x] Post-merge CI on main: backend-tests, frontend-types,
      smoke-web all green (arch-check fails continue-on-error only)
- [ ] In your main repo (not the worktree) run:
      `git fetch origin && git checkout main && git pull` so your
      local `main` includes the merge
- [ ] `git branch -d sprint/expansion-phase-1-push-notifications`
      after the pull to clean up the local tracking branch
- [ ] Delete the worktree when done:
      `git worktree remove .claude/worktrees/phase-1-push`

## After Phase 1 merges — production enablement

These do not block the merge but push will not work in production
without them.

### Expo / EAS
- [ ] Register the Scout iOS bundle ID in Apple Developer
- [ ] Upload APNs Auth Key to the Scout Expo project
- [ ] `cd scout-ui && eas init` to create the EAS project ID
- [ ] Paste the EAS project ID into `scout-ui/app.json` under
      `expo.extra.eas.projectId` and open a small follow-up PR
      (without it, `Notifications.getExpoPushTokenAsync` fails on
      EAS-built apps)

### Railway env vars (backend)
- [x] `PUSH_PROVIDER=expo` — set 2026-04-21
- [x] `EXPO_PUSH_SECURITY_ENABLED=false` — set 2026-04-21
      (optional: set to `true` + provide `EXPO_ACCESS_TOKEN`)

### Vercel env vars (frontend)
- [ ] `EXPO_PUBLIC_PUSH_PROVIDER=expo`

### Physical-device validation
- [ ] Install the Scout app on a physical iPhone, sign in
- [ ] Device appears under `/settings/notifications` → Registered devices
- [ ] Admin sends a test push from another session
- [ ] iPhone displays the notification
- [ ] Tapping the notification opens Scout and `tapped_at` populates

---

## Before starting Phase 2 (Google Calendar)

- [ ] Confirm Phase 1 Railway + Vercel deploys are live and healthy
      (per your `feedback_verify_deploys` memory rule)
- [ ] Google Cloud project with Calendar API enabled
- [ ] OAuth consent screen configured, test users added
- [ ] Backend callback + webhook URL publicly reachable over HTTPS
- [ ] Confirm intended redirect URI and post-connect app return URI
- [ ] Railway env vars for Phase 2:
  - [ ] `GOOGLE_CLIENT_ID` (needs GCP OAuth client created first)
  - [ ] `GOOGLE_CLIENT_SECRET` (needs GCP OAuth client created first)
  - [x] `SCOUT_OAUTH_ENCRYPTION_KEY` — set 2026-04-21; local backup at
        `C:\Users\rober\scout-secrets-backup.txt` — copy to 1Password
        then delete the backup file
  - [x] `SCOUT_GOOGLE_OAUTH_REDIRECT_URI` — set 2026-04-21 to
        `https://scout-backend-production-9991.up.railway.app/api/connectors/google/oauth/callback`
  - [ ] `SCOUT_GOOGLE_OAUTH_APP_RETURN_URI` (needs app URL scheme decision)

---

## Out-of-scope debt flagged this session

- [ ] `database/migrations/045_ai_message_metadata.sql` has no
      `backend/migrations/` twin — pre-existing drift from PR #25
      (Supabase Storage). Small follow-up PR to mirror it would
      remove the gap; not required for Phase 1.

---

## House rules for this file

- Claude Code updates this file as action items accrue or clear.
- When a whole section's items are all checked, move the section to
  `docs/atr tasks/archive/YYYY-MM-DD_archive.md` so the top stays
  focused on open work.
- Dated section headers are OK when a deadline matters; otherwise
  group by PR / phase / deployment target.
