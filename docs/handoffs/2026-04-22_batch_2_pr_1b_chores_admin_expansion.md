# Batch 2 PR 1b handoff — Chores admin expansion (2 of originally-3 items)

**Branch:** `batch-2/pr-1b-chores-admin-expansion`
**Base:** main at `f3ac2e5` (PR 1a squash merge)
**Pulled from:** PR 1 original scope, chores cluster (items 4, 5, 6).
Item 5 deferred after investigation revealed it crosses the
canonical (`scout.task_templates`) vs legacy (`public.chore_templates`)
data-model boundary and needs a dedicated planning conversation.
This PR ships items 4 + 6. The next session produces a schema-vs-
architecture audit as PR 1c to inform item 5's real shape.

## Summary

Two items: extend the admin chore form with Phase 3 scope-contract
fields, and wire photo upload for chore template examples.

No DB migration. The scope-contract columns (`included`,
`not_included`, `done_means_done`) plus `supplies`,
`photo_example_url`, `estimated_duration_minutes`, and
`consequence_on_miss` all already exist on the `ChoreTemplate`
SQLAlchemy model (added in Phase 3). They were just never exposed
through the Pydantic schemas, so the POST route silently ignored
them. This PR widens the schema on both create and read sides to
expose them. Existing callers that omit the new fields continue to
work unchanged (lists default to `[]`, nullable strings and ints
default to `None` on the backend; optional on the frontend
interface).

## Items shipped

### Item 4: Admin chore form scope-contract fields

`/admin/chores/new` form gains a "Scope contract" section with:

- **Included** (multiline textarea, one item per line)
- **Not included** (multiline textarea, one item per line)
- **Done means done** (textarea)

Plus a "Supporting detail" section with:

- **Supplies needed** (multiline textarea, one item per line)
- **Photo example** (file picker, see Item 6)
- **Estimated duration** (minutes, integer input with keyboard=number-pad)
- **Consequence on miss** (textarea)

Backend:
- `backend/app/schemas/life_management.py` — `ChoreTemplateCreate`
  and `ChoreTemplateRead` widened with seven new fields. All
  optional at create time; list fields default to `[]` matching
  the SQLAlchemy `default=list`, scalar fields default to `None`.
- `backend/app/services/chore_service.py` — `create_chore_template`
  now passes all new fields through to the model constructor.
  Inline comment documents the expansion.

Frontend:
- `scout-ui/lib/types.ts` — `ChoreTemplate` interface gains the
  seven new optional fields. Older consumers that ignore them
  continue to typecheck.
- `scout-ui/lib/api.ts` — `createChoreTemplate` payload type
  accepts the seven new optional fields.
- `scout-ui/app/admin/chores/new.tsx` — eight new form inputs
  (three scope-contract, five supporting-detail) rendered across
  two section headers. Helper `linesToList` converts multiline
  textareas to the string[] shape the model expects, dropping
  empty lines.

### Item 6: Chore template photo example upload UI

Photo picker reuses the existing `uploadAttachment` infrastructure
(`POST /api/storage/upload` → Supabase Storage) with zero new
routes or plumbing. The picker uses the same web-only
`<input type="file">` pattern as `ScoutBar` (`Platform.OS === "web"`
guard, hidden input, programmatic click via ref). Native iOS /
Android fall back to a disabled chip labeled "Photo upload is
web-only for now"; native picker via `expo-image-picker` is a
separate future item.

On successful upload:
- The signed URL from the upload response is stored in component
  state
- A 120px preview renders below the picker button
- A "Remove" chip clears the preview and unsets the URL
- On form submit, the URL is included in the POST payload as
  `photo_example_url`

On upload failure, the form shows an error message but stays
interactive; the user can retry without losing other field data.

Reused components / services (no new surface):
- Backend: `POST /api/storage/upload` (Sprint 04 Phase 3 route)
- Frontend: `uploadAttachment` in `scout-ui/lib/api.ts` (same
  helper used by AI chat attachments)

## Item 5 deferred (see PR 1c audit)

Original item 5 was "chore card inline expand with scope contract"
on child-facing surfaces (`/today`, child home). Investigation
found the chore card consumes `TaskOccurrence` from the canonical
`scout.v_household_today` view, which joins against
`scout.task_templates` (canonical) rather than
`public.chore_templates` (legacy, where the scope-contract fields
actually live). Bridging these two domains safely requires either
a view migration (risky: projection churn ripples across surfaces)
or a new endpoint + `chore_template_id` exposure on
`TaskOccurrence`.

Neither is "admin UI tweak." Rather than pick a direction blindly,
the next PR is an audit (PR 1c) mapping the canonical vs legacy
schema split, after which item 5 gets its own purpose-built PR
informed by the audit's conclusions.

## Verification

- `cd scout-ui && npx tsc --noEmit`: clean
- `py -m pytest backend/tests/test_chore_templates.py -xvs`:
  3 passed (new file — defaults-when-omitted, fields-persist,
  empty-lists-explicit)
- `py -m pytest backend/tests/test_chore_templates.py
  backend/tests/test_grocery.py backend/tests/test_canonical_session2.py
  -q`: 103 passed (chore + adjacent domains; no regressions)
- `node scripts/architecture-check.js`: 0 WARN, 1 INFO (eighth PR
  with identical pre-existing seedData drift)
- No em dashes

## Not in scope

- **Item 5** (chore card inline expand). Deferred pending the
  canonical-vs-legacy audit (PR 1c).
- **Native photo upload** (iOS / Android). Current picker is
  web-only; chip labels native surfaces with "Photo upload is
  web-only for now." Separate future item using
  `expo-image-picker`.
- **Photo thumbnail hosting / URL refresh**. Supabase signed URLs
  expire in 1 hour per the storage route's contract. The form
  saves the signed URL, which means the stored value goes stale
  within an hour. A follow-up should either (a) save the raw
  storage path and resolve signed URLs at read time, or
  (b) extend the signed-URL TTL. Not worth blocking this PR on;
  noted here so a future reader notices.
- Edit existing chore template. This PR only extends the CREATE
  form; admin editing of existing templates is a separate
  surface.

## On Andrew's plate

- Review PR 1b when opened
- Squash-merge
- This is a mixed PR (backend schema + frontend UI) so the full
  gate applies: wait for Railway `/health` + Vercel prod green +
  `smoke-deployed` green before moving on
- Post-merge, PR 1c starts immediately (docs-only audit, no
  dependency on runtime)

## Meta

- Task #53 (PR 1b) completes on merge with 2 of original 3 items.
  Item 5 picks back up after PR 1c's audit conclusions.
- Task #51 (mirror `provision_smoke_adult.py`) still pending;
  opportunistic pickup.
- Eighth PR in a row where arch-check INFO is identical
  pre-existing seedData drift. Still the right time to file #45
  as its own ticket.

## Photo upload signed-URL lifetime — FIXED in this PR

Initial draft of this PR stored the short-lived signed URL returned
by `/api/storage/upload` into `chore_templates.photo_example_url`.
Signed URLs expire in 1 hour, which would have meant photos broke
silently within an hour of upload. Andrew's review caught this
during the pre-merge diff pass.

The fix stays in this PR rather than a follow-up because "item 6
doesn't actually work past its first hour" is a functional defect,
not deferred polish. Batch 1's staples lesson: if the feature
doesn't hold up, don't ship it.

What the fix does:

- **Store the storage path, not the signed URL.** The admin form
  now captures `result.path` from the upload response and sends
  THAT as `photo_example_url` on the chore-template POST. The
  short-lived `result.signed_url` is used only for the in-form
  preview (well within the 1h window).
- **New `GET /api/storage/signed-url?path=...` endpoint** in
  `backend/app/routes/storage.py`. Resolves a stored path to a
  fresh 1h signed URL on every read. Access control: path must
  begin with the actor's `family_id`; cross-tenant reads return
  403 with a warning log entry. Returns 501 when Supabase is not
  configured (same pattern as the upload route).
- **Clarifying comment on the SQLAlchemy model column.**
  `ChoreTemplate.photo_example_url` now documents that the
  column stores a path, not a URL. Column name left as-is for
  backward compatibility since renaming would require a
  migration and zero rows currently hold data.
- **Frontend `fetchSignedUrl(path)` helper** in
  `scout-ui/lib/api.ts`. Consumers that render the photo
  (future item 5, any admin list/edit view) call this to resolve
  paths to URLs at read time. Returns `{path, signed_url,
  expires_in}` so callers can refresh near the deadline if
  needed.
- **Regression test** in
  `backend/tests/test_chore_templates.py`:
  `test_photo_example_url_stores_path_not_signed_url` pins the
  contract so a future regression to "stores a URL" would fail
  here.
- **Endpoint tests** in `backend/tests/test_storage.py` new
  `TestSignedUrlEndpoint` class: missing path -> 400,
  cross-family path -> 403, supabase-not-configured -> 501,
  happy path returns fresh URL with correct shape.

Net: photo upload now works end-to-end for as long as the chore
template exists, not just the first hour.
