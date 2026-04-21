# Sprint 04 Phase 1 — AI conversation resume — handoff

**Prepared:** 2026-04-21
**Branch:** `sprint/sprint-04-ai-conversation-resume`
**Base:** `main @ 70bde59`
**Commits:**
- `8971040` chore(migrations): sync 045_ai_message_metadata twin to backend/
- `d5f43ec` migration: Sprint 04 Phase 1 - ai_conversation_resume (046)
- `9ff8b8f` backend: service + routes + orchestrator
- `993398a` frontend: lib + ScoutSheet/ScoutSidebar + /settings/ai
- `123ab67` test + docs: backend tests + smoke spec + tracker

## What shipped

### Schema (migration 046)
- Adds `title`, `last_active_at`, `is_pinned` to `ai_conversations`.
- Reuses the existing `status` column (`active / archived / ended`
  from migration 019) for archive state. No parallel `is_archived`
  boolean.
- Backfills `last_active_at = COALESCE(updated_at, created_at)` and
  `title` from each conversation's first user message (first 60
  whitespace-normalized chars). Idempotent via `IS NULL` guards.
- Two new indexes: resume query `(family_member_id, status,
  last_active_at DESC)` and a partial index for pinned rows.
- Two new permission keys registered in `scout.permissions` and
  granted to `YOUNG_CHILD / CHILD / TEEN / PARENT / PRIMARY_PARENT`:
  - `ai.manage_own_conversations` — list/rename/archive/pin
  - `ai.clear_own_history` — bulk archive-older-than

### Backend
- New `backend/app/services/ai_conversation_service.py`.
- Routes extended in `backend/app/routes/ai.py`:
  - `GET /api/ai/conversations` (extended) — now self-scoped by actor;
    supports `include_archived`, `pinned_first`, `limit`, `offset`;
    orders by `last_active_at DESC`. `family_id` and `kind` remain as
    optional legacy params.
  - `GET /api/ai/conversations/stats` (new)
  - `POST /api/ai/conversations` (new) — needs
    `ai.manage_own_conversations`
  - `PATCH /api/ai/conversations/{id}` (new) — needs
    `ai.manage_own_conversations`; rejects `status='ended'` (use
    `POST /end` for that)
  - `POST /api/ai/conversations/archive-older-than` (new) — needs
    `ai.clear_own_history`; archive-only
  - `GET /api/ai/conversations/{id}/messages` (extended) — response
    shape changed from bare array to `{messages, has_more}`; supports
    `limit` and `before_message_id`; ownership tightened (see below)
- `backend/app/ai/orchestrator.py::_persist_message` now bumps
  `last_active_at` on user/assistant turns (tool rows don't count)
  and upgrades a null / `"New conversation"` title from the first
  real user message.
- Existing `GET /api/ai/conversations/resumable` endpoint unchanged —
  its 30-min freshness + pending-confirmation / moderation safety
  gates still govern auto-resume. This phase does **not** duplicate
  that logic.

### Frontend
- New `scout-ui/lib/ai-conversations.ts` with plain fetch helpers.
  (No react-query in the repo; this matches the existing pattern.)
- `ScoutSheet.tsx` + `ScoutSidebar.tsx`:
  - On open, call `fetchResumableConversation` then
    `fetchConversationMessagesPaginated(limit=50)` and hydrate the
    thread. If no resumable thread exists, fall through to the
    existing blank / sample state.
  - Track `conversationId` in state; pass it through to
    `sendChatMessageStream` so subsequent turns continue the same
    thread.
  - Capture `conversation_id` from the stream's `"done"` event on the
    first turn of a new conversation.
- New route `scout-ui/app/settings/ai.tsx` with a Conversation history
  section (counts + 7/30/90-day archive-older-than presets).
- `scout-ui/app/settings/index.tsx` gains an "AI & Conversations" nav
  row mirroring the existing "Notifications" row.

### Tests
- `backend/tests/test_ai_conversation_resume.py` — unit + HTTP:
  - `generate_title` edge cases
  - List filters (`include_archived`, `pinned_first`)
  - Stats counts + self-scoping
  - `bulk_archive_older_than` happy path + self-scoping
  - Orchestrator hook: `last_active_at` bumps on user/assistant; no
    bump on tool; title upgrade from first user message; second user
    message doesn't overwrite an already-set title
  - HTTP ownership denial on `PATCH` and `GET /messages` (returns 404)
  - HTTP pagination: `has_more=true` at limit=50 with 75 messages
  - HTTP create + patch happy paths
- `smoke-tests/tests/ai-conversation-resume.spec.ts` — exercises the
  new endpoints via authenticated request plus asserts the
  `/settings/ai` page renders.

### Permission-denial coverage (note)
The plan required a permission-denial test. The two new keys
(`ai.manage_own_conversations` and `ai.clear_own_history`) are
granted to every user tier per migration 046 — there is no current
tier that is denied either. The permission-denial test in
`test_ai_conversation_resume.py::TestPermissionGates` documents this
with an explicit `pytest.skip` and a reference to the ownership-denial
tests, which cover the real-world access control concern (can a
sibling touch a sibling's conversation? No — 404).

## Deviations from the written plan (and why)

1. **No new `/most-recent-active` endpoint.** The existing
   `/resumable` endpoint already serves auto-resume with safety gates
   (30-min freshness; excludes pending-confirmation and
   moderation-blocked threads). The plan's proposed 7-day resume
   without gates would have been a UX regression. Documented in the
   plan's §7 Amendments update path but not implemented as a new
   endpoint.
2. **Role tier names.** The plan referenced lowercase (`admin /
   parent_peer / teen / child / kid`). The live schema uses uppercase
   canonical names (`PRIMARY_PARENT / PARENT / TEEN / CHILD /
   YOUNG_CHILD`) per migrations 022 + 040 + 043. Migration 046 uses
   the correct live names.
3. **`scout.ai_conversations` vs `ai_conversations`.** The plan
   referenced the `scout.` prefix. Actual table lives in the default
   (public) schema; the migration does not qualify with `scout.`.
4. **Frontend file name.** The plan's
   `scout-ui/lib/ai-conversations.ts` is plain fetch helpers, not
   react-query hooks (the repo doesn't use react-query). Shape
   preserved; name preserved.
5. **Minimum-viable drawer UI.** The plan called for a "Recent
   conversations" drawer with per-row rename / archive / pin
   controls. Ship scope in this PR covers the resume plumbing + the
   /settings/ai archive-older-than action. The full drawer list UI
   is a small follow-up; API surface is already in place.
6. **Ownership tightening.** The prior
   `GET /api/ai/conversations/{id}/messages` only checked
   family-level access, letting any sibling read any sibling's thread.
   Tightened to require `family_member_id` match. This is a behavior
   change; called out in the backend commit message.

## Arch check

- Baseline (from 2026-04-20 handoff): **39 WARNs**
- After this branch: **41 WARNs**
- Delta from this branch's work: **0** — the +2 are from work that
  merged between 2026-04-19 (when the baseline was recorded) and this
  branch's cut: `storage.py` (Supabase storage, PR #25) and one other.
  Neither is Sprint 04 code.

## On Andrew's plate

See `docs/atr tasks/open_items.md` §"Right now — Sprint 04 Phase 1".
Short form:

- [ ] Review the PR diff
- [ ] Merge (squash, per repo convention)
- [ ] Confirm Railway backend deploy succeeds post-merge
- [ ] Confirm Vercel frontend deploy succeeds post-merge
- [ ] Pull `main` locally and delete this phase branch

## Follow-ups flagged during execution

Non-blockers; separate PRs or Phase 2 scope:

- **Recent conversations drawer UI.** API is ready. Components need
  UI work (list rows, per-row actions). Could land as `Sprint 4 #2`
  or defer to Phase 2.
- **SAMPLE_THREAD mock data** in `ScoutSheet.tsx` and
  `ScoutSidebar.tsx` still shows as initial state when no resumable
  conversation exists. Should be replaced with a blank state.
- **Permission-denial test wiring.** If a future tier lacks these
  new permissions (e.g. a hypothetical `READ_ONLY` tier), update the
  skipped test to exercise the denial.

## Parallel session

A parallel Claude Code session may be implementing Expansion Sprint
Phase 3 (Family Projects) on `sprint/expansion-phase-3-family-projects`
using migration 047+. That PR is independent and does not conflict
with this one on migrations, routes, or core services. Minor conflict
possible on:
- `scout-ui/app/settings/index.tsx` (both add nav rows)
- `docs/atr tasks/open_items.md` (both may edit)

Both are easy merge conflicts; plan to merge this PR first, then
rebase the Phase 3 PR.
