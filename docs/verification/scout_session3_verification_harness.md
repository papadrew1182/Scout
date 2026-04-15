# Scout Session 3 — verification harness

This is the lightweight manual verification checklist for the Session 3
operating surface + control plane lane (Blocks 1 through 4). The
`scout-ui` repo ships no test framework, so Block 4's "smoke coverage"
contract is fulfilled by this doc: run it end-to-end before calling
Session 3 demo-ready.

## When to use

- Before a demo or stakeholder walkthrough of the Scout operating surface
- After any change that touches Today, Rewards, Calendar, Control Plane,
  or Assist
- After any change to `features/lib/contracts.ts`, `mockData.ts`,
  `mockClient.ts`, `realClient.ts`, or `AppContext.tsx`
- Before merging a Session 3 branch into `main`

## Pre-flight

```bash
cd scout-ui
npx tsc --noEmit    # must pass clean
npm run web         # or: npm run ios
```

## Mode switch

The frontend picks its data source from `EXPO_PUBLIC_SCOUT_API_MODE`:

- `mock` (default) → in-memory mock client, no backend required
- `real` → `realClient` against `API_BASE_URL`

The verification pass exercises both modes. Mock mode verifies the
happy paths against seeded Roberts data. Real mode verifies that every
canonical endpoint Session 3 consumes — including
`/api/calendar/exports/upcoming` and `/api/control-plane/summary`,
which became real and DB-backed in Session 2 block 3 (commit
`3a3bf31`) and were activated on the frontend in Session 3 block 5
(commit `6e6facf`) — actually round-trips against a running Session 2
backend.

---

## Route-level smoke — MOCK MODE

Run with `EXPO_PUBLIC_SCOUT_API_MODE=mock` (the default).

### `/` — root redirect
- [ ] Visiting `/` redirects to `/today` (see `app/index.tsx`)
- [ ] Session 3 shell (AppProvider + ScoutShell) wraps the page
- [ ] Bottom tab bar shows: Today · Rewards · Calendar · Plane · Assist

### `/today` — household operating surface
- [ ] Eyebrow says "Household", title says "Today", subtitle shows the
      current date
- [ ] Summary strip shows non-zero `Due` / `Done` / `Late` counts
- [ ] Per-kid Daily Win pills render with `completed / required` counts
- [ ] Filter chips include `Household` + one chip per kid
- [ ] Tapping a kid chip filters blocks/standalone/weekly lists
- [ ] Tapping a task opens the `CompletionSheet`
- [ ] Standards-of-done render for templates that have them
  (e.g. `rotating_common_area_closeout`, `afterschool_dog_walks`)
- [ ] Tapping "Mark complete" flips local state AND shows a success toast
- [ ] The task status immediately flips to "Done" without a page reload
- [ ] Daily Win pill for that kid updates to reflect the new completion
- [ ] Toast auto-dismisses after ~4 seconds

### `/rewards` — current week payout
- [ ] Eyebrow says "Rewards", title says "This week", subtitle has the
      period range and `$X.XX projected`
- [ ] Approval pill shows `DRAFT` / `READY FOR REVIEW` / `APPROVED`
- [ ] One `DailyWinCard` per kid with filled vs hollow dots for wins
- [ ] One `WeeklyPayoutCard` per kid with baseline allowance, payout
      percent, projected payout, and miss reasons
- [ ] The footer disclosure names Scout as the reward owner and
      Greenlight as the payout-facing rail

### `/calendar` — publication preview
- [ ] Eyebrow "Calendar publication", title "Household anchor blocks"
- [ ] Day-grouped list of anchor blocks renders (today / tomorrow /
      weekday labels)
- [ ] Each block shows label, time, source type, and `On Hearth` chip
- [ ] The footnote says "Hearth is display only. Tap a chore on Today
      to interact with it"
- [ ] If the mock Google Calendar connector is `stale` or `error`, a
      banner appears ABOVE the list with a warn or error tone

### `/control-plane` — starter surface
- [ ] Eyebrow "Control plane", title "Connectors, sync, publication"
- [ ] Mode tag pill visible under the title: `MOCK DATA` in yellow
- [ ] Sync status panel shows healthy / stale / error counts from
      `mockControlPlaneSummary`
- [ ] Publication panel shows calendar export + reward approval counts
- [ ] Connector health panel shows one row per connector (google_calendar,
      greenlight, rex, ynab, apple_health)
- [ ] Traffic-light dot colors match health (green / yellow / red)
- [ ] Long connector labels truncate cleanly without breaking the row
- [ ] No reconnect / approve / retry buttons are present — read-only only

### `/assist` — suggestion chips + starter surfaces
- [ ] Eyebrow "Scout assist", title "Ask, suggest, intervene"
- [ ] Mode tag pill visible under the title
- [ ] Five chips visible (or four, if the signed-in user is kid-tier —
      `What needs parent attention?` is parent-gated)
- [ ] Tapping "What is due next?" expands an AnswerCard with up to 3
      upcoming tasks, each with owner / label / time
- [ ] Tapping "Who is late?" shows late counts per member OR
      "Nobody is late right now"
- [ ] Tapping "Am I on track for a Daily Win?" shows per-kid status
      (or just the signed-in kid if kid-tier)
- [ ] Tapping "What will Hearth show tonight?" shows today-after-17:00
      hearth_visible exports
- [ ] Tapping "What needs parent attention?" (parent view) aggregates
      approvals, sync failures, connector errors, late tasks
- [ ] Action Center is visible only when signed in as parent-tier
- [ ] Notification Preferences card is visible to everyone but
      `Parent alerts` row is hidden for kid-tier

---

## Route-level smoke — REAL MODE

Run with `EXPO_PUBLIC_SCOUT_API_MODE=real` against a running Session 2
backend at `feat/scout-canonical-household-connectors@3a3bf31` (or any
descendant). Every endpoint Session 3 consumes is real and DB-backed;
there are no shipped-stubs left to verify.

### `/today`, `/rewards` — must render live
- [ ] Both routes load real data from the canonical endpoints
- [ ] Completion POST still updates local state + refetches rewards
      when the server signals `daily_win_recomputed` or
      `reward_preview_changed`
- [ ] No error banner appears under normal operation

### `/calendar` — must render live exports
- [ ] No mock rows render — the page does NOT silently fall back to
      mock data
- [ ] Day-grouped list of real `scout.v_calendar_publication` rows
      renders (or the empty state if the seeded family has no
      upcoming exports yet)
- [ ] If `/api/calendar/exports/upcoming` returns a non-2xx, an error
      banner with a `Try again` button appears (no more "not yet
      shipped" wording — the endpoint is live as of Session 2 block 3)
- [ ] If the backing Google Calendar connector reports `stale` /
      `lagging`, the secondary warn banner above the list explains
      the publication state

### `/control-plane` — must render live summary + connector health
- [ ] `MOCK DATA` pill is NOT shown; `LIVE DATA` pill is shown instead
- [ ] `SyncStatusPanel` shows real healthy / stale / error counters
      from `/api/control-plane/summary`
- [ ] `PublicationStatusPanel` shows real calendar export +
      reward-approval counters from the same summary
- [ ] `ConnectorHealthPanel` renders real connector rows from
      `/api/connectors` + `/api/connectors/health` (DB-backed since
      Session 2 block 3, commit `3a3bf31`)
- [ ] If `/api/control-plane/summary` returns a non-2xx, an error
      banner with a `Try again` button appears at the top, but
      `ConnectorHealthPanel` still renders because the connector
      endpoints are independent of the summary slice
- [ ] If both connector endpoints error simultaneously, an error panel
      with a retry button appears under `Connector health`

### `/assist` — parent attention chip in real mode
- [ ] When `/api/control-plane/summary` is healthy, the
      `parent_attention` answer aggregates pending approvals + sync
      failures + connector errors + failed exports + late tasks
- [ ] When the summary slice errors, the answer gracefully skips the
      summary-derived lines and only surfaces `Today` lateness — never
      a raw error string

---

## Contract honesty checks

Run once per branch. These verify no frontend-only contract drift:

- [ ] `features/lib/contracts.ts` matches `docs/sessions/scout_session_3_operating_surface_and_control_plane.md`
      under the "UI contracts consumed by this lane" section
- [ ] `CompletionResponse` is the four-field bare echo — no
      `updated_block`, no `daily_win_preview`
- [ ] `TaskOccurrence` status union is exactly
      `open | complete | late | excused`
- [ ] `RoleTierKey` union matches canonical role tiers (PRIMARY_PARENT
      | PARENT | TEEN | CHILD | YOUNG_CHILD | DISPLAY_ONLY)
- [ ] No new endpoints have been invented in `realClient.ts`
- [ ] `realClient.getCalendarExports` calls
      `GET /api/calendar/exports/upcoming` (live since Session 2
      block 3 — see `backend/app/routes/canonical.py:626`)
- [ ] `realClient.getControlPlaneSummary` calls
      `GET /api/control-plane/summary` (live since Session 2 block 3
      — see `backend/app/routes/canonical.py:687`)
- [ ] `ConnectorFreshness` is the closed union
      `live | lagging | stale | unknown` (matches
      `backend/services/connectors/sync_persistence.py:23`)
- [ ] `ConnectorStatus` is the closed union `disconnected | configured
      | connected | syncing | stale | error | disabled | decision_gated`
      (matches `backend/services/connectors/sync_persistence.py:14-19`)
- [ ] No `fetch` call bypasses `realClient` or `mockClient`

## Role / view-mode consistency

- [ ] Sign in as PARENT or PRIMARY_PARENT → Action Center + parent
      affordances visible, parent_attention chip visible
- [ ] Sign in as TEEN / CHILD / YOUNG_CHILD → Action Center hidden,
      parent_attention chip hidden, parent alerts row hidden in
      NotificationPreferences, parent override toggle hidden in
      CompletionSheet
- [ ] No age-based branching anywhere — `useIsParent()` only checks
      `role_tier_key`

## Accessibility spot checks

- [ ] All tappable elements have `accessibilityRole` set
- [ ] Completion confirmation button has `accessibilityLabel`
- [ ] Toasts have `accessibilityLiveRegion="polite"`
- [ ] Error banners have `accessibilityLiveRegion="polite"`
- [ ] Long connector labels use `numberOfLines={1}` with `ellipsizeMode="tail"`
- [ ] Long miss-reason strings wrap instead of overflowing

## Narrow-width spot checks

Open devtools, toggle device toolbar, and pick the 320px-wide preset.

- [ ] Today summary strip fits without horizontal scroll
- [ ] Per-kid Daily Win pills wrap to multiple rows (they have
      `flexWrap: "wrap"` and a 100px min-width)
- [ ] Filter chip row wraps for long kid names
- [ ] Connector rows keep the traffic-light dot + status pill on the
      same line with a truncated label

## Final gate

- [ ] `npx tsc --noEmit` is clean
- [ ] Session 3 status note from the charter has been filled in with
      Completed / In progress / Blocked by Session 2 / Contracts
      changed / Roadmap reconciliation fields
