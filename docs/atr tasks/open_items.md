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
