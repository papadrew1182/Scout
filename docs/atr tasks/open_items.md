# Andrew's open items

Running list of things Andrew needs to handle that Claude Code cannot.
Checked items stay here for audit; once a whole group clears, archive
it to a dated file under `docs/atr tasks/archive/`.

Last updated: 2026-04-22 (Phase 5 merged)

---

## Right now — PR #58 (Sprint 05 Phase 5, AI-driven discovery) — MERGED + DEPLOYED

Branch: `sprint/sprint-05-phase-5-ai-discovery` (local + remote both deleted)
PR: https://github.com/papadrew1182/Scout/pull/58
Merge commit: `e4abc06`

### Status
- [x] Final cross-task review caught two safety-critical issues
      (cross-family leak via AI-returned member_id; AI body silently
      replaced by compose_body); both fixed in the same PR before merge
- [x] CI green on branch (backend-tests, frontend-types, arch-check,
      smoke-web, Vercel all pass)
- [x] PR #58 squash-merged to main 2026-04-22T16:35:08Z
- [x] No migration this phase (per plan); Railway has no DB change to apply
- [x] Railway backend `/health` returns `{"status":"ok"}` post-merge
- [x] Railway `/ready` returns `ai_available: true`
- [x] Post-merge CI on main: backend-tests, frontend-types,
      arch-check all green; smoke-web still running at report time
      but non-blocking
- [x] Vercel production deploy for `e4abc06` reported success

### Sprint 05 is now shipped end-to-end
- Phase 1 (core engine, parent-child dispatch model): #53
- Phase 2 (quiet hours + batching): #55
- Phase 3 (AI-composed copy + held-dispatch worker): #56
- Phase 4 (admin rule engine with sqlglot whitelist): #57
- Phase 5 (AI-driven discovery): #58 <- this one

### On Andrew's plate
- [x] `git checkout main && git pull` locally (Claude Code did this;
      re-run on your own machine if you work elsewhere)
- [x] Branch deleted locally + remotely
- [ ] Try it: wait ~1 hour post-merge; check `/personal` inbox for
      any `ai_suggested` dispatches. The AI will find something worth
      nudging if your family has actionable state
- [ ] Watch weekly AI cost - Phase 5 is a cost driver. Weekly soft cap
      gates it; if you see unexpected spend, the cap is the lever

### Safety notes for this phase
- AI-returned `member_id` is filtered against the calling family
  before dispatch (mirrors Phase 4's `filter_rule_rows_to_family`).
  Cross-tenant prompt injection via the digest cannot route a nudge
  to another family.
- AI body survives `compose_body` verbatim for single-proposal
  bundles. Without this guard, the validated AI body got replaced
  by a re-composed body using title/name context that AI discovery
  never stamps.
- Dedupe key for `ai_suggested` with NULL entity_id hashes
  `context.body` - distinct AI suggestions on the same day get
  different keys; identical suggestions collapse via the UNIQUE
  constraint.
- P1 scanner and P5 AI emit different `trigger_kind` values for
  the same entity. Both dispatch by design; the P1<->P5 dedupe
  boundary regression test locks this in so a future silent
  tightening would fail CI.

### Deferred follow-ups (non-blocking)
- `occurrence_at_utc` vs `scheduled_for` semantic conflation for
  ai_suggested proposals (P1 stamps source time, P5 stamps delivery
  time). Self-contained to ai_suggested; affects only how the
  `occurrence_local_date` component of the dedupe key is computed.
- `_DISCOVERY_SYSTEM_PROMPT` is not prompt-cached - Phase 10's
  caching work should pick it up next.
- In-memory rate limit (`_last_ai_discovery_run_utc` dict) resets
  on scheduler restart. Post-restart first tick can call AI for
  every family at once. Weekly cap bounds damage. If the burst
  becomes painful, move to a DB-backed marker.
- `_is_throttled` / `_mark_discovery_ran` don't `_strip_tz` the
  incoming `now_utc`. Safe today because all callers pass naive
  UTC, but one defensive strip would keep symmetry with
  `build_family_state_digest`.
- Handoff doc: `docs/handoffs/2026-04-22_sprint_05_phase_5_ai_discovery.md`

---

## PR #57 (Sprint 05 Phase 4, admin rule engine) — MERGED + DEPLOYED

Branch: `sprint/sprint-05-phase-4-admin-rule-engine` (remote still present; delete after pull)
PR: https://github.com/papadrew1182/Scout/pull/57
Merge commit: `0ee597f`

### Status
- [x] Final cross-task review caught two safety-critical cross-tenant
      leaks (scanner + preview-count) and one UI flash bug; all three
      fixed in the same PR before merge
- [x] CI green on branch after all fixes (backend-tests, frontend-types,
      arch-check, smoke-web, Vercel all pass)
- [x] PR #57 squash-merged to main 2026-04-22T11:03:05Z
- [x] Migration 051 applied on Railway via the public proxy URL
      (`scout.nudge_rules` table, `nudges.configure` perm to PARENT +
      PRIMARY_PARENT)
- [x] Railway backend `/health` returns `{"status":"ok"}` post-merge
- [x] Railway backend `/ready` returns `ai_available: true` post-merge
- [x] Post-merge CI on main: backend-tests, frontend-types, arch-check
      all green; smoke-web still running at report time but non-blocking
- [x] Vercel production deploy for `0ee597f` reported success

### On Andrew's plate
- [ ] `git checkout main && git pull` locally (Claude Code did this in
      the repo root already; re-run on your own machine if elsewhere)
- [ ] `git branch -d sprint/sprint-05-phase-4-admin-rule-engine`
- [ ] `git push origin --delete sprint/sprint-05-phase-4-admin-rule-engine`
      if the remote still has it
- [ ] Try it: as a PARENT, open `/admin/ai/nudges` -> Rules tab,
      author a rule like
      `SELECT assigned_to AS member_id, id AS entity_id, 'personal_task' AS entity_kind, due_at AS scheduled_for FROM personal_tasks WHERE status = 'pending'`
      and hit Preview to see the match count. Save as Active and the
      hourly scan will emit nudges for matches

### Safety notes worth remembering
- Cross-family filter (`filter_rule_rows_to_family` in
  `backend/app/services/nudges_service.py`) runs at both data egress
  points (scanner dispatch AND preview-count response). Any future
  caller of `execute_validated_rule_sql` MUST apply this filter or
  we reintroduce the cross-tenant leak.
- `family_members` and `families` are still on the validator allowlist
  intentionally (so rules like "nudge every family member" work). The
  filter is what keeps them safe, not an allowlist restriction.
- Least-privilege Postgres role for rule execution is still deferred
  to a v2 hardening PR. Not blocking v1.

### Follow-ups flagged during execution
- Mixed-case regression test (rule returns SOME Family A + SOME
  Family B ids) would strengthen coverage. Current tests cover the
  all-mismatched case which was sufficient for the exploit proof.
- `trigger_entity_id` from rule output lands on `nudge_dispatch_items`
  without a cross-family check. Current impact is zero because
  `_route_hint` does not honour `trigger_entity_id` for `custom_rule`
  kind, but worth tracking as defense-in-depth for a future phase.
- Handoff doc says "40-case attack suite" on the validator tests;
  actual count is closer to 33. Cosmetic.

---

## Older — Sprint 04 Phase 1 (AI conversation resume) — in progress

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

## Right now — PR #40 (Sprint 04 Phase 2, per-member personalities) — MERGED + DEPLOYED

Branch: `sprint/sprint-04-ai-personalities` (remote deleted)
PR: https://github.com/papadrew1182/Scout/pull/40
Merge commit: `16325d3f`

### Status
- [x] CI green on branch after a fix pass (FamilyMember import path;
      missing savingText style)
- [x] PR #40 squash-merged to main 2026-04-21
- [x] Migration 048 applied on Railway via the public proxy URL
- [x] Two new permission keys live: `ai.edit_own_personality`,
      `ai.edit_any_personality`
- [x] Post-merge CI on main: backend + frontend-types + smoke-web
      green (arch-check fails continue-on-error only)
- [x] Railway backend `/health` returns `{"status":"ok"}` post-merge
- [x] Vercel production deploy: success

### On Andrew's plate
- [ ] `git checkout main && git pull` locally
- [ ] `git branch -d sprint/sprint-04-ai-personalities`
- [ ] Try it: open Scout, tune tone/verbosity at `/settings/ai`,
      send a chat, watch the voice shift on the next turn
- [ ] As adult, visit `/admin/ai/personalities` to edit another
      member's config if desired

### Follow-ups flagged during execution
- `/admin/ai/personalities` has no nav link from `/admin` yet.
  Add a row in the admin index in a small follow-up.
- Chip / free-text input helper components duplicated between
  `/settings/ai` and `/admin/ai/personalities`. Extract to
  `scout-ui/components/PersonalityControls.tsx` if a third site
  needs them.
- Proactivity field stored but not yet used. Sprint 05 nudges
  engine picks it up.

---

## PR #39 (Sprint 04 Phase 1 follow-ups) — MERGED

Merge commit: `8412d90c`. Shipped: SAMPLE_THREAD removal from both
AI launcher surfaces + "Your conversations" list on `/settings/ai`
with per-row Rename / Pin / Archive actions. No backend changes,
no migration. CI green, Vercel deploy success.

---

## PR #37 (Sprint 04 Phase 1, AI conversation resume) — MERGED + DEPLOYED

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

## Push notifications — LIVE IN PRODUCTION (2026-04-21)

iOS push is live and validated on physical device as of 2026-04-21.
Future gap-analysis runs should NOT flag this as an open item.

Out-of-repo config (not version-controlled, recorded here so audits
have the full picture):
- [x] Apple Developer: Scout iOS bundle ID registered
- [x] Expo: APNs Auth Key uploaded to the Scout Expo project
- [x] EAS project ID created and pasted into `scout-ui/app.json`
      under `expo.extra.eas.projectId` (see the file for value)
- [x] Vercel: `EXPO_PUBLIC_PUSH_PROVIDER=expo` set in production env
- [x] Railway backend: `PUSH_PROVIDER=expo` + `EXPO_PUSH_SECURITY_ENABLED=false`
      set 2026-04-21 (unchanged)
- [x] Physical-device validation complete: device registers via
      `/settings/notifications` -> Registered devices, test pushes
      display on iPhone, tap opens Scout and `tapped_at` populates

Open operations work on this surface (tracked separately):
- [ ] Rotation + incident procedure for APNs key, Expo access token,
      and EAS project credentials - deferred to the ops playbook
      (gap-analysis recommendation #8)

---

## Before starting Phase 2 (Google Calendar)

GCP OAuth setup completed 2026-04-21 by Andrew. All Phase 2 prereqs
green — code kick-off is unblocked.

- [x] Phase 1 Railway + Vercel deploys confirmed live (2026-04-21)
- [x] Google Cloud project with Calendar API enabled
- [x] OAuth consent screen configured, test users added
- [x] Backend callback + webhook URL publicly reachable over HTTPS
      (Railway production URL)
- [x] Redirect URI + app return URI recorded on Railway
- Railway env vars for Phase 2:
  - [x] `GOOGLE_CLIENT_ID` set
  - [x] `GOOGLE_CLIENT_SECRET` set
  - [x] `SCOUT_OAUTH_ENCRYPTION_KEY` set (local backup at
        `C:\Users\rober\scout-secrets-backup.txt` — copy to 1Password
        then delete the backup file)
  - [x] `SCOUT_GOOGLE_OAUTH_REDIRECT_URI` set to
        `https://scout-backend-production-9991.up.railway.app/api/connectors/google/oauth/callback`
  - [x] `SCOUT_GOOGLE_OAUTH_APP_RETURN_URI` set to
        `com.papadrew.scout://oauth/google/callback` (renamed
        2026-04-21 from an earlier `SCOUT_GOOGLE_0AUTH_APP_RETURN_URI`
        typo; zero variant is gone)

### Phase 2 sprint-plan decisions (written into SCOUT_EXPANSION_SPRINT_V2.md §7)
- [x] §D5 resolved: canonical Google Calendar connector path is
      `backend/services/connectors/google_calendar/`. Retire
      `backend/app/services/integrations/google_calendar.py` by end
      of Phase 2. Do not create a third location.
- [x] §D6 resolved: `DevToolsPanel.tsx` does not exist; `DEV_MODE` in
      `scout-ui/lib/config.ts` has no consumer. Phase 2 should instead
      annotate / retire: (1) the backend integration service, (2) the
      `POST /integrations/google-calendar/ingest` route, (3) the dead
      TS wrappers `ingestGoogleCalendar` and `ingestYnabBill` in
      `scout-ui/lib/api.ts` (safe to delete — zero callers), and
      (4) `smoke-tests/tests/dev-mode.spec.ts` (currently asserts
      absent buttons that never existed; flip once `/settings/connections`
      ships).

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
