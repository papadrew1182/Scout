# Sprint 04 revision notes

This file summarizes the changes made to the original Sprint 04 PDF handoff before code review.

## Main corrections

1. Permission model normalized
   - Added explicit mutating permission keys for conversation management:
     - `ai.manage_own_conversations`
     - `ai.clear_own_history`
   - Kept conversation reads on existing authenticated self scope and current `ai.chat` behavior.
   - Removed the contradictory pattern where `PATCH /api/ai/conversations/{id}` relied on ownership only.

2. Conversation-history scope aligned across backend and frontend
   - Added `GET /api/ai/conversations/stats`
   - Added `POST /api/ai/conversations/archive-older-than`
   - Renamed the settings CTA from implied deletion to archive-only behavior
   - Added bounded `messages` loading with `limit` and `has_more`

3. Prerequisite logic fixed
   - Missing routes are no longer a halt condition if the underlying tables and persistence exist.
   - Foundational data model and config prerequisites still remain halt conditions.

4. Personality default source made explicit
   - Canonical tier defaults now come from one backend module such as `backend/app/ai/personality_defaults.py`
   - `context.py` imports defaults instead of hardcoding them
   - Future members work through merged fallback behavior even without seeded `member_config` rows

5. Automated tests made deterministic
   - Removed style-based acceptance like "response style differs from default"
   - Replaced with persistence, permission, prompt-composition, and preview assertions

6. Long-thread handling made concrete
   - Resume path hydrates only a bounded message window by default
   - Full unbounded thread loading is explicitly out of scope

7. Sprint dependency wording tightened
   - Sprint 04 now depends on Sprint 03 being merged to `main`, not on push delivery being live in production.

## Output files

- `SCOUT_SPRINT_04_AI_INTELLIGENCE_LAYER.md`
- `SCOUT_SPRINT_04_AI_INTELLIGENCE_LAYER_REVISED.md`

Both files contain the same revised handoff content.

## Post-code-review corrections (2026-04-21)

A second-pass review against the live Scout repo surfaced four concrete repo-fact issues. Both files were updated:

1. **Frontend target corrected.** The plan referenced `scout-ui/components/ScoutLauncher.tsx`, which does not exist. Replaced with the actual AI launcher surfaces: `ScoutSheet.tsx` and `ScoutSidebar.tsx` (both wired to real AI streaming in 2026-04-20 hotfixes). Shared logic factored into `scout-ui/lib/ai-conversations.ts`.

2. **Settings route target corrected.** `scout-ui/app/settings/ai.tsx` does not exist today; only `settings/index.tsx` does. Phase 1 now creates the new route and adds a navigation row; Phase 2 extends it.

3. **Schema duplication removed.** Migration 010 already has `ai_conversations.status TEXT CHECK (status IN ('active', 'archived'))`. The draft added a parallel `is_archived boolean`. Dropped the boolean, reused the existing `status` column for archive state, kept `is_pinned` as a separate boolean. PATCH body and the compound index were updated accordingly.

4. **`last_active_at` vs `updated_at` disambiguated.** Both columns now have an explicit role in the plan: `updated_at` bumps on any row mutation (including metadata changes like rename, pin, archive); `last_active_at` bumps only on user or assistant turns. Resume ordering uses `last_active_at`.

§7 Amendments gained five new bullets pinning these decisions against drift during execution.
