# Scout Sprint 04 - AI Intelligence Layer: Conversation resume + per-member personalities

**Ref commit:** latest `main` at time of execution, preferably after Sprint 03 merge  
**Prepared:** 2026-04-21  
**Intended audience:** Claude Code running against the Scout monorepo  
**Precondition:** Sprint 03 is merged to `main`. Sprint 04 has no external-service dependency on Sprint 03 push delivery being live.  
**Track:** A  
**Wave:** 1  
**Supersedes:** 2026-04-20 draft in PDF form

This revision resolves four issues in the prior draft: permission model inconsistency, frontend/backend scope mismatch in conversation history, ambiguity around the canonical source of personality defaults, and non-deterministic acceptance tests.

## 1. Why this sprint exists

Scout AI is already useful in production, but two gaps still make it feel disposable instead of persistent.

First, conversations do not reliably resume across panel opens. The backend already persists `ai_conversations` and `ai_messages`, but the frontend still behaves like every panel open is a fresh session. That breaks continuity for project threads, follow-ups, and any interaction where "keep going from last time" should be the default.

Second, every family member currently gets the same Scout voice. That is too coarse. Andrew needs direct, systems-oriented replies. Younger kids need simpler wording and gentler pacing. Adults may want different tone, humor, and verbosity. The existing AI flags are useful but far too blunt to express that.

This sprint fixes both gaps without inventing a second persistence model or a second prompt system. Phase 1 makes conversation continuity real using the existing AI conversation tables. Phase 2 makes personality configuration a first-class per-member setting using `member_config` and the current prompt composer.

Strategically, Sprint 04 is still the right next sprint. The roadmap places it in Wave 1, and the decision log selected it early because it has no external setup dependency. It also lays groundwork for Sprint 05, which needs stable per-member context and conversation continuity, and for Sprint 06, which needs member-addressable memory primitives.

## 2. Operating constraints

All work satisfies `docs/architecture/ARCHITECTURE.md` and the eight-point compliance checklist. The framework `§F3` non-negotiables are restated here for this sprint:

- `scout.*` schema. UUID PKs named `id`. FKs named `{table_singular}_id`.
- `timestamptz` everywhere appropriate. `created_at` on every table. `updated_at` on mutable tables.
- `is_` / `has_` prefix on booleans.
- Zero external IDs on core tables. This sprint introduces no external IDs.
- Never edit an existing migration. New migrations at `backend/migrations/NNN_ai_conversation_resume.sql` and `backend/migrations/NNN_ai_personalities.sql`.
- Every mutating endpoint calls `actor.require_permission("feature.action")`.
- Frontend admin controls gated with `useHasPermission`.
- Per-member config lives in `member_config`.
- SQL params `$1` / `$2` asyncpg style.
- No em dashes in any produced content.
- `node scripts/architecture-check.js` runs at end of every phase.

Sprint-specific clarifications:

- Use the existing `ai_conversations` and `ai_messages` tables. Do not create a second conversation persistence model.
- Missing AI conversation routes are not a blocker if the underlying tables and persistence already exist. Building missing routes is in scope for Phase 1.
- Conversation resume must load a bounded history window on open. Do not hydrate an unbounded thread by default.
- Personality defaults must have one canonical source. Do not scatter per-tier default JSON across `context.py`, routes, and UI code.
- Automated tests must verify persistence, permissions, prompt composition, and preview behavior. Do not make automated pass/fail depend on subjective differences in raw model output.

## 3. Pre-flight checklist

### 3.1 Human-confirmed prerequisites

None. This sprint has no external setup requirement.

### 3.2 Machine-verifiable prerequisites

Claude Code verifies these from repo state before starting:

- `ai_conversations` table exists in current `main`.
- `ai_messages` table exists and stores role + content per turn.
- The orchestrator already writes conversation rows and message rows during chat.
- `backend/app/ai/context.py` has a prompt-composition path that already reads actor or family context.
- `member_config` exists and supports JSON config by key.
- `scout-ui/lib/config.ts` exposes `useMemberConfig<T>(memberId, key, defaultValue)` or an equivalent current-member config helper.
- Existing AI routes, if present, should be extended rather than duplicated.

### 3.3 Execution rule

Halt only if one of the foundational persistence or config prerequisites above is missing.

Do not halt just because `GET /api/ai/conversations`, `GET /api/ai/conversations/{id}/messages`, or related routes are absent. If the underlying tables and persistence exist, building or extending the routes is part of Phase 1.

## 4. Phases

This sprint has two phases. Phase 2 starts only after Phase 1 is merged to `main`, deployments are green, and the Phase 1 smoke flow is verified. The reason is practical: both phases touch the AI settings surface, AI routes, and shared AI frontend libraries.

### Phase 1 - Conversation resume

**Goal:** the AI launcher surfaces (`ScoutSheet` and `ScoutSidebar`) open into the current member's most recent active conversation when one exists, while still allowing the user to start a fresh thread and manage recent history.

**Stack:** existing React + Expo Router + SSE streaming + `sendChatMessageStream()` in `scout-ui/lib/api.ts`. No new libraries.

#### Scope

**Schema** (`NNN_ai_conversation_resume.sql`):

Extend `scout.ai_conversations`:

- add `title text null`
- add `last_active_at timestamptz not null default now()`
- add `is_pinned boolean not null default false`

Archive state reuses the existing `status text CHECK (status IN ('active', 'archived'))` column from migration 010. Do not introduce a parallel `is_archived` boolean; that would create two sources of truth.

`last_active_at` and `updated_at` differ intentionally: `updated_at` (with existing trigger `trg_ai_conversations_updated_at`) bumps on any row mutation including metadata changes (rename, pin, archive). `last_active_at` bumps only on user or assistant message turns. Resume ordering uses `last_active_at`; audit/last-touched uses `updated_at`.

Backfill rules:

- `last_active_at = coalesce(updated_at, created_at)` for existing rows
- `title` from the first user message's first 60 trimmed characters for existing rows
- if no user message exists, leave `title` null

Indexes:

- `(family_member_id, status, last_active_at desc)` — status separates active from archived at query time
- optional partial index for pinned ordering if the repo pattern favors it

Permission keys added in the migration:

- `ai.manage_own_conversations` for all canonical tiers
- `ai.clear_own_history` for all canonical tiers

Read endpoints continue to require authenticated self access plus existing `ai.chat` behavior. Mutating endpoints must use the new permission keys below and ownership checks. Ownership check alone is not sufficient.

**Backend:**

Extend or add `backend/app/services/ai_conversation_service.py` with:

- `get_most_recent_active(family_member_id, max_age_days=7)`  
  Returns the newest non-archived conversation with at least one user or assistant message in the last 7 days, or `None`.
- `list_conversations(family_member_id, include_archived, limit, offset, pinned_first=True)`
- `get_conversation_stats(family_member_id)`  
  Returns `total_count`, `active_count`, `archived_count`.
- `create_conversation(family_member_id, first_message=None)`  
  Creates a new conversation. If `first_message` is missing or blank, initial title is `"New conversation"`.
- `generate_title(first_user_message)`  
  First 60 trimmed characters after whitespace normalization. Fallback `"New conversation"`.
- `rename_conversation(id, new_title, actor)`
- `archive_conversation(id, actor)`
- `pin_conversation(id, actor)`
- `bulk_archive_older_than(family_member_id, days, actor)`

Extend `backend/app/routes/ai.py` rather than creating a parallel route module:

- `GET /api/ai/conversations`  
  Query params: `include_archived=false&limit=20&offset=0&pinned_first=true`
- `GET /api/ai/conversations/most-recent-active`  
  Returns the resumable conversation, or `204` if none eligible.
- `GET /api/ai/conversations/{id}/messages`  
  Must support `limit` and optional `before_message_id`. Default to newest 50 messages. Return a `has_more` flag so the client can know when older history exists.
- `GET /api/ai/conversations/stats`  
  Returns current-member totals for the settings page.
- `POST /api/ai/conversations`  
  Body: `{first_message?}`. Requires `actor.require_permission("ai.manage_own_conversations")`.
- `PATCH /api/ai/conversations/{id}`  
  Body: `{title?, status?, is_pinned?}` where `status` is `"active"` or `"archived"`. Requires `actor.require_permission("ai.manage_own_conversations")` and self ownership.
- `POST /api/ai/conversations/archive-older-than`  
  Body: `{days}`. Requires `actor.require_permission("ai.clear_own_history")`. Self-scoped only. Archive only, never delete.

Orchestrator updates:

- On every successful user turn and assistant turn, update `last_active_at = now()` on the conversation row.
- If a conversation was created blank and still has `title is null` or `"New conversation"`, set the title from the first real user message.
- Reused conversations must continue to flow through the existing prompt and history trimming path. Do not introduce a separate resume-specific orchestration path.

**Frontend:**

Add `scout-ui/lib/ai-conversations.ts` with hooks:

- `useMyRecentConversations({ includeArchived, limit })`
- `useMostRecentActiveConversation()`
- `useConversationMessages(conversationId, { limit, beforeMessageId })`
- `useConversationStats()`
- `useCreateConversation()`
- `useRenameConversation()`
- `useArchiveConversation()`
- `usePinConversation()`
- `useArchiveOlderConversations()`

Update the existing AI launcher surfaces: `scout-ui/components/ScoutSheet.tsx` (bottom-sheet surface) and `scout-ui/components/ScoutSidebar.tsx` (sidebar surface). Both were wired to real AI streaming in the 2026-04-20 post-operability-sprint hotfixes. Resume behavior must be identical on both surfaces, so extract shared logic into `scout-ui/lib/ai-conversations.ts` rather than duplicating across components.

Behavior on panel open (applies to both surfaces):

- Call `useMostRecentActiveConversation()`.
- If a conversation is returned, load messages through `GET /api/ai/conversations/{id}/messages?limit=50` and hydrate the panel with that history.
- If `has_more=true`, show a small non-blocking note such as "Earlier messages not loaded in this view." Full history browsing remains in the recent-conversations drawer, not infinite scroll in Phase 1.
- If no eligible conversation exists, show the existing blank state.
- Add a top-level `New conversation` affordance that calls `POST /api/ai/conversations`.
- Add a `Recent conversations` drawer or overlay listing the most recent 20 conversations with title, relative last-active time, and tap-to-resume.
- Per-row actions: rename, archive, pin.

Create `scout-ui/app/settings/ai.tsx` as a new route — it does not currently exist. Only `scout-ui/app/settings/index.tsx` is present today. Add a navigation row to `settings/index.tsx` that routes to `/settings/ai`.

On the new `/settings/ai` page, add a `Conversation history` section with:

- total conversation count
- archived conversation count
- an `Archive older conversations` control with common presets such as 7 / 30 / 90 days
- helper text: `Archives older conversations for this member. Does not delete data.`

Do not label this as an admin action. It is a self-scoped action available to all canonical tiers.

#### Acceptance criteria

- [ ] Migration applied. `ai_conversations` has the three new columns (`title`, `last_active_at`, `is_pinned`), indexes, and backfill complete. Archive state continues to use the existing `status` column.
- [ ] Permission keys `ai.manage_own_conversations` and `ai.clear_own_history` are registered.
- [ ] Backend routes are live for list, most-recent-active, bounded messages, stats, create, patch metadata, and archive-older-than.
- [ ] Happy-path and permission-denial tests exist for every new mutating endpoint.
- [ ] Ownership-denial test covers one member attempting to mutate another member's conversation.
- [ ] Orchestrator updates `last_active_at` on each turn and upgrades blank conversation titles on the first real user message.
- [ ] Frontend opens into the most recent active conversation when one exists and opens blank when none exists.
- [ ] `New conversation` works.
- [ ] Recent conversations drawer lists, renames, archives, and pins correctly.
- [ ] Conversation history settings show accurate stats and archive older conversations successfully.
- [ ] Resume path loads a bounded history window, not the entire thread by default.
- [ ] `smoke-tests/tests/ai-conversation-resume.spec.ts` covers: send a message, close panel, reopen, restored messages visible; start a new conversation; archive the old conversation; confirm archived conversation is hidden from the default list.
- [ ] Existing `ai-panel` and `ai-roundtrip` flows do not regress.
- [ ] Arch check clean.

#### Out of scope

- Cross-member conversation sharing
- Conversation full-text search
- Conversation export
- True deletion or retention purge of conversation history
- Automatic archive by inactivity
- Full infinite-scroll history browser inside the AI launcher surfaces

#### Estimated output

1 migration, ~6 backend files, ~6 frontend files, 1 smoke spec, 3 docs updates

### Phase 2 - Per-member personalities

**Goal:** each family member gets a tuned Scout prompt profile based on role, age-appropriate vocabulary, tone, verbosity, humor, and member-specific notes, without creating a second prompt pipeline.

**Stack:** existing `backend/app/ai/context.py` prompt composer. No new libraries.

#### Scope

**Schema** (`NNN_ai_personalities.sql`):

No new tables. Use existing `member_config` under key `ai.personality`.

Permission keys added in the migration:

- `ai.edit_own_personality` for all canonical tiers
- `ai.edit_any_personality` for `admin` and `parent_peer`

Stored config shape:

```json
{
  "tone": "warm | direct | playful | professional",
  "vocabulary_level": "simple | standard | advanced",
  "formality": "casual | neutral | formal",
  "humor": "none | light | dry",
  "proactivity": "quiet | balanced | forthcoming",
  "verbosity": "short | standard | detailed",
  "notes_to_self": "free-text persona notes, max 500 chars",
  "role_hints": "free-text role context, max 200 chars"
}
```

Canonical default source:

- Create one backend source of truth, for example `backend/app/ai/personality_defaults.py`, keyed by canonical `role_tiers`.
- Example tier defaults:
  - `admin` and `parent_peer`: direct / advanced / casual / dry / balanced / short
  - `teen`: warm / standard / casual / light / balanced / standard
  - `child`: warm / standard / casual / light / quiet / short
  - `kid`: playful / simple / casual / light / quiet / short
- `context.py` must import this source rather than embedding its own per-tier literals.
- `GET` routes return merged config: stored `member_config` over canonical tier defaults.
- Future members must work without a migration backfill. Do not make prompt composition depend on pre-seeded `member_config` rows.

Validation rules:

- reject unknown enum values with `422`
- trim and bound `notes_to_self` to 500 characters
- trim and bound `role_hints` to 200 characters
- reject unknown keys instead of silently storing them

**Backend:**

Add or extend:

- `backend/app/ai/personality_defaults.py`  
  Canonical per-tier defaults.
- `backend/app/ai/context.py`  
  Add `build_personality_preamble(actor, resolved_config)` and append its output to the existing system prompt before tool definitions.
- `backend/app/services/ai_personality_service.py`  
  Resolve defaults, validate payloads, upsert `member_config`, and return merged config + composed preamble.

Extend `backend/app/routes/ai.py`:

- `GET /api/ai/personality/me`  
  Returns current member's stored config, resolved config, and composed preamble.
- `PATCH /api/ai/personality/me`  
  Requires `actor.require_permission("ai.edit_own_personality")`.
- `GET /api/ai/personality/members/{id}`  
  Returns another member's stored config, resolved config, and composed preamble. Requires `ai.edit_any_personality`.
- `PATCH /api/ai/personality/members/{id}`  
  Requires `actor.require_permission("ai.edit_any_personality")`.

Implementation notes:

- Reuse the existing family-member list endpoint or hook for the admin screen. Do not invent a duplicate member model or duplicate member listing API if one already exists.
- Preview must use the backend-composed preamble. Do not duplicate preamble construction logic in the frontend.
- The `proactivity` field is configuration-only in this sprint. It has no runtime behavior until Sprint 05.

**Frontend:**

Add `scout-ui/lib/ai-personality.ts` with hooks:

- `useMyPersonality()`
- `useMemberPersonality(memberId)`
- `useUpdateMyPersonality()`
- `useUpdateMemberPersonality()`

Extend the `/settings/ai` route created in Phase 1 (`scout-ui/app/settings/ai.tsx`).

Add a `Personality` section for the current member with controls for:

- tone
- vocabulary level
- formality
- humor
- proactivity
- verbosity
- `notes_to_self`
- `role_hints`

Behavior:

- save on blur
- show character counters on free-text fields
- include helper text on proactivity: `Takes effect when proactive nudges ship in Sprint 05.`
- `Preview` button opens a modal showing the backend-composed preamble for the saved current config

Add `scout-ui/app/admin/ai/personalities.tsx`:

- gated with `useHasPermission("ai.edit_any_personality")`
- lists all family members with a compact summary such as tone + vocabulary + proactivity
- tap a member to open their personality edit form
- uses server-returned preview data, not a frontend prompt formatter

#### Acceptance criteria

- [ ] Migration applied. Permission keys are registered and no unnecessary new tables are introduced.
- [ ] Canonical tier defaults exist in one backend source module and are reused by prompt composition and API reads.
- [ ] `GET /api/ai/personality/me` returns merged config even when the member has no explicit `member_config` row yet.
- [ ] `PATCH /api/ai/personality/me` validates payloads and persists config successfully.
- [ ] `GET/PATCH /api/ai/personality/members/{id}` are gated by `ai.edit_any_personality`.
- [ ] Permission-denial test covers a non-privileged member attempting to edit another member's personality.
- [ ] `build_personality_preamble` has deterministic unit tests covering every allowed enum value and character-limit behavior.
- [ ] `compose_prompt` or equivalent prompt builder test asserts the personality preamble is present in the final composed system prompt.
- [ ] Frontend settings render for the current member, save successfully, and preview the backend-composed preamble.
- [ ] Admin personalities screen lists household members and supports editing when permitted.
- [ ] `smoke-tests/tests/ai-personality.spec.ts` covers: adult edits their own personality, preview updates, chat still succeeds; kid-tier member is denied access to edit another member's personality.
- [ ] Arch check clean.

Do not use automated assertions such as "response style differs from default" as a release gate. That kind of check is too subjective and too model-dependent.

#### Out of scope

- Dynamic personality learning or self-tuning
- Per-surface personality variants
- Voice personality controls
- Multi-language prompt variants
- Automated evaluation of raw model style as a hard pass/fail criterion

#### Estimated output

1 migration, ~5 backend files, ~5 frontend files, 1 smoke spec, 3 docs updates

## 5. Risks and trade-offs

- **Backfill volume:** existing `ai_conversations` may contain enough rows to make title backfill noticeable. Mitigation: keep the SQL bounded and idempotent. If the table is unexpectedly large, chunk the title backfill using the repo's established migration pattern.
- **Long threads:** a conversation may have far more messages than the launcher should hydrate. Mitigation: bounded `messages` reads with `limit` and `has_more`; no unbounded resume flow in this sprint.
- **Prompt token cost:** personality preambles add tokens to each chat turn. At household scale this is acceptable, but it should still be documented in the handoff and kept concise.
- **Default-source drift:** if defaults are duplicated across files, they will drift. Mitigation: one canonical backend defaults module consumed by prompt composition and read endpoints.
- **Role-tier changes after customization:** a member with a saved custom personality should keep that saved config even if their tier later changes, unless explicitly reset. Document this behavior.
- **Proactivity expectations:** the field exists before the nudges engine does. Mitigation: UI text must clearly state that `proactivity` takes effect in Sprint 05.

## 6. Explicitly deferred

Do not absorb any of these into this sprint.

- Sprint 05 - proactive nudges engine
- Sprint 06 - structured memory layer
- Sprint 08 - voice input and transcription
- Personality A/B testing
- Conversation search, export, or deletion
- Cross-member persona sharing

## 7. Amendments for Claude Code

If any line above conflicts with this section, this section wins.

- No em dashes anywhere.
- Use the canonical `role_tiers` tier names that actually exist in the repo seed.
- `ai_conversations` and `ai_messages` are existing tables. Do not create parallel conversation models.
- Missing conversation routes are Phase 1 scope, not a prerequisite failure, if the underlying persistence already exists.
- Every mutating conversation endpoint must call `actor.require_permission(...)` with `ai.manage_own_conversations`, `ai.clear_own_history`, `ai.edit_own_personality`, or `ai.edit_any_personality` as appropriate. Do not rely on ownership checks alone.
- Conversation-history cleanup in this sprint is archive-only. No true delete.
- Archive state is stored in the existing `ai_conversations.status` column (`active` / `archived`) from migration 010. Do not add a parallel `is_archived` boolean.
- `last_active_at` (new) bumps on user/assistant turns only. `updated_at` (existing) continues to bump on any row mutation. Resume ordering uses `last_active_at`.
- Conversation resume applies to both `scout-ui/components/ScoutSheet.tsx` and `scout-ui/components/ScoutSidebar.tsx`. There is no `ScoutLauncher.tsx` in the repo. Shared logic lives in `scout-ui/lib/ai-conversations.ts` and both components consume it.
- `scout-ui/app/settings/ai.tsx` does not exist today. Phase 1 creates it as a new route and adds a navigation row from `settings/index.tsx`. Phase 2 extends the same route.
- Resume must load a bounded history window through the messages endpoint. Do not hydrate the full thread by default.
- Personality defaults must come from one canonical backend source. Do not hardcode per-tier personality literals inside `context.py`.
- Preview must use the backend-composed preamble, not a duplicated frontend formatter.
- The `proactivity` field has no runtime effect until Sprint 05 and must be labeled accordingly in the UI.
- Do not use subjective model-output style assertions as automated release gates.
- Phase 2 does not start until Phase 1 is merged to `main`, Railway and Vercel are verified, and Phase 1 smoke is green.
- Open a PR automatically on each phase. Verify Railway and Vercel post-merge. Record smoke results and arch-check WARN before/after in the handoff.
- If any acceptance criterion cannot be met, halt and ask before proceeding.

## 8. Prompt for Claude Code

Use this to start Phase 1:

Read `SCOUT_SPRINT_04_AI_INTELLIGENCE_LAYER.md` in full, including `§7 Amendments`.
Read `docs/architecture/ARCHITECTURE.md` from `§The Three Layers` through `§Anti-Patterns`.
Verify `§3.2` machine-verifiable prerequisites.
If a foundational prerequisite is missing, halt and report the exact missing item.
Do not halt only because conversation routes are missing; building or extending them is Phase 1 scope if the underlying persistence exists.
Otherwise create branch `sprint/sprint-04-ai-conversation-resume` from `main`.
Implement Phase 1 only.
Ship only the commit groups that apply.
Run `node scripts/architecture-check.js` before the `docs:` commit and record before/after WARN counts in the handoff.
Open a PR automatically on phase completion with acceptance criteria, smoke results, and deployment URL.
Verify Railway and Vercel deployments render and pass smoke post-merge.
If any acceptance criterion cannot be met, stop and ask before proceeding.
Do not start Phase 2 in the same session.

After Phase 1 is merged and deployments are green, use this to start Phase 2:

Read `SCOUT_SPRINT_04_AI_INTELLIGENCE_LAYER.md` Phase 2 in full, including `§7 Amendments`.
Confirm Phase 1 is merged to `main` and deployments are green.
Create branch `sprint/sprint-04-ai-personalities` from `main`.
Implement Phase 2.
Use one canonical backend defaults source for role-tier personality defaults.
Do not write automated style-difference assertions against raw model text.
Run `node scripts/architecture-check.js` before the `docs:` commit and record before/after WARN counts in the handoff.
Open a PR automatically on phase completion with acceptance criteria, smoke results, and deployment URL.
Verify Railway and Vercel deployments post-merge.
Do not start Sprint 05 in the same session.
