# Scout Sprint Unblock Checklist

**Prepared:** 2026-04-21
**Applies to:** Sprint 04 (AI Intelligence Layer) and the Expansion Sprint (Push / Google Calendar / Family Projects)
**Purpose:** single-source list of things Andrew must complete or decide before Claude Code starts any of these sprints.

Items are grouped by blast radius. Repo-health items in §A apply to every sprint. Per-sprint items in §B through §E only apply when that sprint is next up.

---

## A. Repo-health — complete BEFORE any sprint branch is cut

### A1. Reconcile migration numbering

`backend/migrations/` tops out at **044_meal_base_cooks.sql**. `database/migrations/` has **045_ai_message_metadata.sql**. The two directories are supposed to mirror each other. Any new sprint migration will pick the wrong next number.

**Action:** decide which directory is canonical and copy/rename so both end at the same N. One-line answer either way. Record in `docs/architecture/migrations.md` or a short handoff note.

### A2. Apply operability-sprint migrations on Railway

Per `docs/handoffs/2026-04-20_session_handoff.md`: migrations 040–044 are committed to main but Railway auto-deploys code, not SQL. Any sprint that assumes permission keys from 040 or home-maintenance tables from 042 are live will fail in production.

**Action:**
```
railway run python backend/migrate.py
```
Then confirm: `SELECT max(filename) FROM schema_migrations;`

### A3. Decide what to do with the 8 skipped Session 3 smoke tests

Currently gated by `SMOKE_SESSION3` env var in CI. Both sprints will pile new smoke specs on top. Leaving them in the current state creates ambient confusion about what's actually passing.

**Action:** either (a) fix selectors and unskip, OR (b) open an issue, downgrade to a known-skip allowlist with an explicit due date. Pick one.

### A4. Arch-check baseline recorded

39 pre-existing WARN findings. CI currently has `continue-on-error: true`. Both sprint plans state "any new WARN is a blocker" — which only works if the baseline is written down.

**Action:** create `docs/architecture/arch_check_baseline.md` listing the 39 files and their warn categories. Each phase handoff then records delta against this.

### A5. Concurrent-session branch thrash

2026-04-20 handoff reports another Claude Code session keeps switching the working branch to `feat/supabase-storage-attachments`. Required two cherry-picks to recover last time.

**Action:** either close/pause other Claude Code sessions for the duration of a sprint, OR include in the sprint prompt: "verify `git rev-parse --abbrev-ref HEAD` matches the phase branch before every commit."

---

## B. Sprint 04 — AI Intelligence Layer (Conversation resume + Personalities)

No external prerequisites. All items are plan-fixes or in-repo decisions.

### B1. Fix the plan: `ScoutLauncher.tsx` does not exist

Sprint 04 §Frontend says "Update `scout-ui/components/ScoutLauncher.tsx`". That file is not in the repo. The real AI launcher surface is `scout-ui/components/ScoutSheet.tsx` + `scout-ui/components/ScoutSidebar.tsx`, both wired to real AI streaming in 2026-04-20 post-sprint hotfixes.

**Action:** edit the Sprint 04 doc — replace every `ScoutLauncher.tsx` reference with the correct file(s). If Phase 1 runs as written, Claude Code will either halt or create a new orphaned launcher.

### B2. Fix the plan: `scout-ui/app/settings/ai.tsx` does not exist

Only `scout-ui/app/settings/index.tsx` exists. The plan says to extend `settings/ai.tsx` in two places (Conversation history and Personality sections).

**Action:** decide — (a) add both sections to existing `settings/index.tsx`, OR (b) create a new route `settings/ai.tsx`. Either works; pick one and update the plan.

### B3. Decide: `is_archived` boolean vs existing `status` column

Migration 010 already has `ai_conversations.status TEXT CHECK (status IN ('active', 'archived'))`. Sprint 04's migration adds `is_archived boolean`. These would be two sources of truth.

**Action:** pick one approach in the plan:
- Option A (smaller change): drop the new `is_archived` field; reuse existing `status`. Add query helpers only.
- Option B (cleaner long-term): migrate `status` values into the new boolean, then drop `status`. Touches existing code that reads `status`.

### B4. Clarify: `last_active_at` vs existing `updated_at`

Migration 010 already has `updated_at` with a trigger. The plan adds `last_active_at` on top. They should differ — metadata mutations (rename/pin/archive) should bump `updated_at` but not "activity" — but the plan doesn't say that, and Claude Code may collapse them.

**Action:** add one sentence to the plan: "Metadata mutations bump `updated_at` only; user/assistant turns bump `last_active_at`."

### B5. Confirm `max_age_days=7` for resume

A member who last used Scout 10 days ago will hit the blank state instead of resuming. Consider 30.

**Action:** confirm 7 or change to preferred value. Minor.

### B6. Confirm smoke specs `ai-panel` and `ai-roundtrip` aren't in the SMOKE_SESSION3 skip set

Plan acceptance criterion says they must not regress. If they're skipped in CI, the criterion is unenforceable.

**Action:** verify (`grep` the spec files for the skip guard). If they are gated, resolve A3 first.

---

## C. Expansion Sprint Phase 1 — Push notifications

All human-confirmed items. Claude Code cannot verify any of these from the repo.

### C1. Apple Developer
- [ ] Apple Developer Program membership active
- [ ] Scout production iOS bundle ID registered in Apple Developer portal
- [ ] APNs Auth Key (.p8) generated in Developer → Keys
- [ ] Key ID and Team ID recorded in 1Password / password manager

### C2. Provider decision
- [ ] Confirmed: Expo Push Service (the sprint's default). If any other provider, the sprint must be rewritten.
- [ ] APNs credentials either uploaded to Expo/EAS OR available for upload before testing

### C3. Physical device
- [ ] At least one iPhone/iPad with the dev build installed. Smoke tests cannot validate device display; only a physical device can.

### C4. Railway backend env vars
- [ ] `PUSH_PROVIDER=expo`
- [ ] `EXPO_PUSH_SECURITY_ENABLED=false` (or `true` if using security)
- [ ] `EXPO_ACCESS_TOKEN` — only required if `EXPO_PUSH_SECURITY_ENABLED=true`

### C5. Vercel frontend env vars
- [ ] `EXPO_PUBLIC_PUSH_PROVIDER=expo`

### C6. Expo app config
- [ ] `app.config.ts` / `app.json` includes `expo-notifications` plugin
- [ ] Expo project ID wired into token registration path

---

## D. Expansion Sprint Phase 2 — Google Calendar

Highest external-dependency surface. Several repo decisions must also be made first.

### D1. Google Cloud project
- [ ] GCP project exists for Scout
- [ ] Calendar API enabled in API Library
- [ ] OAuth consent screen configured
  - Scopes: `https://www.googleapis.com/auth/calendar.calendarlist.readonly` and `https://www.googleapis.com/auth/calendar.events`
  - (Narrowest that works. Do not request full `auth/calendar` unless specifically needed.)
- [ ] Test users added while app is in testing mode — every adult family member who'll connect a calendar

### D2. OAuth 2.0 client
- [ ] Web Application client created (NOT iOS/Native — backend is the client)
- [ ] Authorized redirect URI includes `https://scout-backend-production-9991.up.railway.app/api/connectors/google/oauth/callback` (or current Railway prod URL)
- [ ] Andrew has decided and recorded the intended `SCOUT_GOOGLE_OAUTH_APP_RETURN_URI` (where backend redirects the client after token exchange)

### D3. Railway backend env vars
- [ ] `GOOGLE_CLIENT_ID`
- [ ] `GOOGLE_CLIENT_SECRET`
- [ ] `SCOUT_OAUTH_ENCRYPTION_KEY` — **must be stable forever**. Used with `cryptography.fernet`. Generate once with `Fernet.generate_key()`; store permanently. If lost, all stored OAuth tokens become unreadable and every adult must re-consent.
- [ ] `SCOUT_GOOGLE_OAUTH_REDIRECT_URI`
- [ ] `SCOUT_GOOGLE_OAUTH_APP_RETURN_URI`

### D4. Webhook reachability
- [ ] `POST /api/connectors/google/webhook` resolves over public HTTPS. Google will not call localhost or any non-public address. If Railway is the prod host, this already works.

### D5. Repo decision: consolidate existing Google Calendar code

There are currently three Google Calendar code surfaces:
1. `backend/services/connectors/google_calendar/` — canonical connector pattern (adapter, client, mapper)
2. `backend/app/services/integrations/google_calendar.py` — older dev-mode ingestion
3. The sprint plan proposes `backend/app/services/connectors/google_calendar.py` — a third path

Shipping as-is creates three parallel Google Calendar code paths.

**Action:** before Phase 2 starts, decide the canonical path. Recommended:
- Keep `backend/services/connectors/google_calendar/` (already the convention)
- Retire `backend/app/services/integrations/google_calendar.py` by end of Phase 2
- Do NOT create a third location

Write this decision into the sprint plan's §7 Amendments.

### D6. Repo decision: locate actual dev ingestion UI

The sprint plan tells Claude Code to annotate `scout-ui/components/DevToolsPanel.tsx` as deprecated. That file doesn't exist. Dev controls likely live in `scout-ui/features/controlPlane/ControlPlaneHome.tsx` or `features/notifications/ActionCenter.tsx`.

**Action:** before Phase 2 starts, grep for "manual ingest" / "dev ingestion" / "ingest calendar" and pin the correct file path in the plan.

---

## E. Expansion Sprint Phase 3 — Family Projects

Fully internal. No Andrew action required.

### E1. Optional: confirm promotion semantics

The plan adds `personal_tasks.source_project_task_id` so a project task can be "promoted" into a member's personal task list. Promotion is one-way; the project task is source of truth.

**Action:** if you disagree with this semantic (e.g. you want bidirectional sync), flag now. Otherwise no action.

---

## F. Cross-cutting decisions

### F1. Sprint execution order

Based on external-dependency cost and risk, recommended order:

1. **Sprint 04 Phase 1** (AI conversation resume) — zero external deps, addresses a known UX gap, small surface area
2. **Expansion Phase 3** (Family Projects) — zero external deps, high product value
3. **Sprint 04 Phase 2** (Personalities) — zero external deps, depends on Phase 1
4. **Expansion Phase 1** (Push) — start Apple work in parallel with 1–3 above; execute once credentials are ready
5. **Expansion Phase 2** (Google Calendar) — most external deps; schedule last

This ordering lets internal work ship while Apple/Google setup happens asynchronously.

### F2. Canonical role tier names

Current state (verified from migration 024 and 034): `admin / parent_peer / teen / child / kid`.

**Action:** confirm these are still the target. If any tier has been renamed since 034_reconcile_permissions, update all four sprint plans. Sprint 04 Phase 2's personality defaults are keyed by these exact strings.

### F3. Who connects Google calendars in Phase 2

Expansion Phase 2 assumes every adult consents individually (credentials are per-member). Only users in GCP's "test users" list can consent while the app is in testing mode.

**Action:** confirm — Andrew only for v1, or Andrew + Sally both? This drives test-user list and acceptance criteria.

### F4. Scheduler ownership

`backend/app/scheduler.py` already exists (APScheduler + Postgres advisory locks from the tier1 proactive work). Both sprint plans hedge on "if scheduler exists, use it." It does.

**Action:** confirm — any new scheduled jobs (push receipt polling, Google watch renewal, daily brief delivery) register via `start_scheduler()`, not standalone entry points.

### F5. Railway migration deploy strategy

Operability sprint surfaced that Railway auto-deploys code but not SQL. This will keep happening. Options:
- Run `railway run python backend/migrate.py` manually after every merge (current)
- Add a post-deploy hook that runs migrations
- Move to a Railway database deploy pipeline

**Action:** pick one. Affects every future sprint.

---

## Minimum to unblock the next session

If only three things get done before the next Claude Code sprint session:

1. **Apply migrations 040–044 on Railway** (§A2). Everything built on top assumes they're live.
2. **Reconcile migration numbering** (§A1). Blocks every new migration.
3. **Fix the Sprint 04 plan (§B1, §B2, §B3) OR start with Expansion Phase 3 instead.** Sprint 04 as written today will halt Claude Code on "ScoutLauncher not found" or produce an orphaned file.

Everything else in §C and §D can be done while Sprint 04 Phase 1 or Expansion Phase 3 is in flight.
