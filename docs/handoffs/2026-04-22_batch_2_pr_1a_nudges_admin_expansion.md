# Batch 2 PR 1a handoff — Nudges admin expansion

**Branch:** `batch-2/pr-1-admin-expansion`
**Base:** main at `a31cee4` (Batch 1 stabilization merge)
**Pulled from:** 3 of the 6 items originally scoped for Batch 2 PR 1.
After 2 of 6 items were complete, scope was reshaped to split PR 1
into 1a (nudges admin cluster) and 1b (chores admin cluster) along
the natural thematic boundary. Items 4, 5, 6 (chores domain) move
to a fresh PR 1b after this merges. The 1a/1b naming preserves the
split history.

## Summary

Three self-contained admin-surface improvements on the
`/admin/ai/nudges` + `/settings/ai` surfaces. No schema change, no
new routes, no new config keys. Two files modified total.

## Items shipped

### Item 3: Trigger source label on Recent Nudges

`/settings/ai` Recent Nudges section now shows a label under each
row's status/time header indicating where the nudge came from:

- `"Scanner: overdue task"` / `"Scanner: upcoming event"` /
  `"Scanner: missed routine"` for Phase 1 built-in scanner sources
- `"Custom rule"` for Phase 4 admin-authored rule output
- `"AI discovery"` for Phase 5 AI-driven proposals
- Mixed-kind bundles show the first kind followed by
  `(+N more)` matching the first-kind-wins convention from
  Batch 1 PR 1 (see `nudges_service.py:941`).

Implementation:
- `scout-ui/app/settings/ai.tsx` — new `labelTriggerSource` helper
  plus `TRIGGER_SOURCE_LABELS` lookup table, rendered as a new
  italic line in each nudge row
- New `nudgeSource` style (11pt italic, muted color)

Data was already present in `GET /api/nudges/me`: each
`NudgeDispatchItem` carries `trigger_kind`. Pure UI change.

### Item 2: SQL snippet library on Rules admin form

`/admin/ai/nudges` Rules tab form now has a row of tappable
example chips below the SQL template field. Tapping a chip loads
the snippet into the template field, overwriting any existing
content. Helper text warns that loading overwrites and that bound
values should be customized before saving.

Snippets shipped (all use whitelisted tables from the Phase 4
validator allowlist):

- **Overdue personal tasks** — `personal_tasks` > 1 day past due
- **Bills due in 3 days** — `bills` within upcoming 3-day window
- **Events starting in 30 min** — `events` + `event_attendees`
  JOIN, 30-minute pre-event window
- **Missed routine instances today** — `task_instances` with
  `is_completed = false` in last 24h

Implementation:
- `scout-ui/app/admin/ai/nudges.tsx` — new `RULE_SQL_SNIPPETS`
  constant at module scope (4 entries); new `snippetChip` +
  `snippetChipText` styles; snippet chip row added to the form
  below the template textarea

Pure frontend. No backend or schema change.

### Item 1: Per-member quiet-hours override editor

`/admin/ai/nudges` Quiet Hours tab now has two cards:

1. **Quiet hours (family default)** — the existing family-wide
   editor, unchanged in behavior, with its blurb updated to
   explain it's the family default (overrides live in the card
   below)
2. **Per-member overrides** — new card listing every active family
   member. Each row shows either the override window ("22:00 -
   07:00") or "Inherits family default" with appropriate actions:
   - Members without an override: single "Add override" chip
   - Members with an override: "Edit" + "Remove" chips
   - Edit mode reveals HH:MM inputs for start + end with Save
     + Cancel. Save calls `PUT /admin/config/member/{id}/nudges.quiet_hours`;
     Remove calls the matching DELETE.

The backend already reads per-member overrides from `member_config`
with `key='nudges.quiet_hours'` in
`nudges_service.py::_resolve_quiet_hours_window`; member override
wins over family default. This PR just exposes the write path via
admin UI so operators no longer have to poke `member_config`
directly.

Implementation:
- `scout-ui/app/admin/ai/nudges.tsx`
  - New `MemberQuietHoursOverridesSection` component (~180 LOC)
  - Imports `fetchMembers` + `fetchAllMemberConfigForKey` +
    `putMemberConfig` + `deleteMemberConfig` from `lib/api`
    (all pre-existing wrappers)
  - Imports `FamilyMember` type from `lib/types`
  - Render point: added `<MemberQuietHoursOverridesSection />`
    immediately below `<QuietHoursSection />` on the quiet_hours
    tab body
- New styles: `overrideRow`, `overrideRowHeader`, `overrideName`,
  `overrideSummary`

No new API endpoints, no schema change. Reuses the existing
`/admin/config/member/{id}/{key}` route and the existing
`admin.manage_config` permission gate it enforces.

## Verification

- `cd scout-ui && npx tsc --noEmit`: clean
- `node scripts/architecture-check.js`: 0 WARN, 1 INFO (same
  pre-existing seedData drift from Batch 1 — seventh PR in a row
  with no change to the specific constants)
- `git diff --stat main..HEAD`: 2 files changed, 368 insertions,
  3 deletions. Tight.
- No em dashes in any added code or comment
- No backend test file touched (all items frontend-only on
  existing API surfaces)

## Not in scope

- **PR 1b items 4, 5, 6 (chores admin cluster).** Moving to their
  own branch after this merges green. Coordinated schema changes
  in the `chore_templates` domain belong together.
- Test-mode feedback for preview-override-effects. Admin saves an
  override, the result is visible in the backend via next
  scheduler tick or manual dispatch; the admin UI doesn't yet show
  a "what will fire with this override" simulation. Separate
  follow-up.
- Snippet authoring by admins (user-defined custom snippets). The
  4 shipped snippets are hardcoded in the TS constant. Admins
  wanting more can paste raw SQL into the textarea; the snippet
  system is a starter, not a library manager.

## On Andrew's plate

- Review PR 1a when opened
- Squash-merge
- Confirm Railway + Vercel deploys green post-merge (no migration
  in this PR; simpler cycle)
- **Watch the auto-triggered `smoke-deployed` run on the merge
  commit.** Should remain green — no test-observable change since
  the smoke list is adult-only and doesn't traverse the admin UI.
  If anything unexpected fails, investigate before PR 1b starts
- Once 1a merges green, PR 1b (chores admin: items 4, 5, 6) starts

## Meta

- Task #52 was originally "Admin surface expansion (6 items)";
  treat this PR's merge as 3-of-6 complete, with the remaining 3
  as PR 1b on a fresh branch
- Seventh PR in a row where the seedData INFO drift is identical
  and pre-existing. Task #45 is the ticket for filing it as a
  separate XS issue; don't let it roll into an 8th.

## Heads-up for PR 1b execution

Two user-flagged watch items for PR 1b:

1. **Migration before code, code before UI, each in the same PR.**
   Items 4 + 5 + 6 all touch `chore_templates` schemas. If backend
   schema lands without a migration updating Railway, frontend
   calls fail. If frontend references fields before schema ships,
   typecheck fails. Order matters within the PR.
2. **TaskOccurrence projection changes in item 5 affect
   child-facing chore cards.** Smoke child tier end-to-end, not
   just the admin side. The child smoke account provisioned in
   Batch 1 stabilization is the canonical smoke identity for this.
