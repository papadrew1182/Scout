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
happy paths; real mode verifies real-vs-mock honesty (truthful
"unavailable" banners when endpoints aren't shipped yet).

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

## Route-level smoke — REAL MODE (real-vs-mock honesty)

Run with `EXPO_PUBLIC_SCOUT_API_MODE=real` against a Session 2 backend
that has shipped canonical endpoints but NOT yet shipped
`/api/calendar/exports/upcoming` or `/api/control-plane/summary`.

### `/today`, `/rewards` — must render live
- [ ] Both routes load real data from the canonical endpoints
- [ ] Completion POST still updates local state + refetches rewards
- [ ] No "unavailable" banner appears — these endpoints are live

### `/calendar` — must show truthful unavailable banner
- [ ] No mock rows render — the page does NOT silently fall back to
      mock data
- [ ] An explicit `Calendar export feed not yet shipped` warn banner
      explains the missing endpoint
- [ ] No retry button appears (retry is not applicable for an
      unimplemented endpoint)
- [ ] When the backend eventually ships the endpoint, the page
      transitions to the real list on the next refresh with no code
      changes

### `/control-plane` — must show honest partial state
- [ ] `MOCK DATA` pill is NOT shown; `LIVE DATA` pill is shown instead
- [ ] The `Summary feed not yet shipped` warn banner is visible
- [ ] `SyncStatusPanel` and `PublicationStatusPanel` render as
      unavailable (dimmed values / "—")
- [ ] `ConnectorHealthPanel` STILL renders real connector rows —
      `/api/connectors` + `/api/connectors/health` are independent of
      the summary and live since Session 2 commit ad912e7
- [ ] If both connector endpoints error simultaneously, an error panel
      with a retry button appears under `Connector health`

### `/assist` — parent attention chip in real mode
- [ ] Without `/api/control-plane/summary`, the `parent_attention`
      answer skips summary-derived lines and only surfaces `Today`
      lateness — never a regex error string

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
- [ ] `realClient.getCalendarExports` still throws the "not yet
      implemented" string (the availability helper depends on it)
- [ ] `realClient.getControlPlaneSummary` still throws the "not yet
      implemented" string
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
