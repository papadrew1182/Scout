# Scout Operability Sprint - Verification Harness

Manual verification checklists for each phase of the operability sprint.
Walk each section against both mock mode and real mode before marking
a phase complete.

---

## Phase 1 - Interaction Contract + Dead-Tap Audit

### Pre-flight

- [ ] `npx tsc --noEmit` passes (type check)
- [ ] `npm run web` starts (or `npx expo start --web`)
- [ ] `node scripts/architecture-check.js` reports zero new WARN-level findings

### /today - TodayHome

- [ ] Summary strip (Due / Done / Late) renders correctly
- [ ] Summary strip counters are NOT tappable (no navigation on click)
- [ ] Per-kid Daily Win pills are visible
- [ ] Tapping a Daily Win pill navigates to `/members/{kid_id}`
- [ ] Placeholder member page shows the kid's name
- [ ] Filter chips (Household + per-kid) are visible
- [ ] Tapping a filter chip toggles the child focus (no navigation)
- [ ] Tapping Household chip resets to unfiltered view
- [ ] Task cards render in HouseholdBoard (blocks + standalone + weekly)
- [ ] Tapping a task checkbox marks it complete (optimistic UI)
- [ ] Tapping a task body opens the CompletionSheet
- [ ] CompletionSheet shows owner, status pill, due time, standards
- [ ] Typing in the notes field does NOT collapse the sheet
- [ ] Toggling the parent override switch does NOT collapse the sheet
- [ ] Clicking "Mark complete" saves and closes the sheet
- [ ] Toast appears after completion
- [ ] AffirmationCard slot renders (if wired from Phase 6)

### /rewards - RewardsHome

- [ ] Period header and total projection render
- [ ] DailyWinCard per kid is visible
- [ ] Tapping DailyWinCard navigates to `/members/{kid_id}?tab=wins`
- [ ] Placeholder member page shows "Tab: wins"
- [ ] WeeklyPayoutCard per kid is visible
- [ ] Tapping WeeklyPayoutCard navigates to `/members/{kid_id}?tab=payout`
- [ ] Placeholder member page shows "Tab: payout"
- [ ] Approval pill shows DRAFT / READY / APPROVED state
- [ ] When ready_for_review + parent + has allowance.run_payout: tapping pill shows action panel
- [ ] Footer disclosure text is non-interactive (no navigation)

### /meals/this-week - Meals

- [ ] Weekly meal grid renders with day columns
- [ ] Tapping a day cell expands it inline (shows note inside cell)
- [ ] Tapping the same day cell again collapses it
- [ ] Expanded cell has a highlighted border
- [ ] No navigation occurs on cell tap (stays on /meals/this-week)

### /grocery - Grocery

- [ ] Per-store cards render with item rows
- [ ] Item checkboxes are tappable
- [ ] Tapping a checkbox marks the item as purchased (checkmark + strikethrough)
- [ ] Needs Review section shows pending items
- [ ] Approve button appears for users with grocery.approve permission
- [ ] Add item button opens the modal form

### /calendar - CalendarPreview

- [ ] Day-grouped anchor blocks render
- [ ] Day group headers are non-interactive (no navigation)
- [ ] Tapping an anchor block row expands inline detail (Source, Target, Hearth)
- [ ] Tapping the expanded row collapses it
- [ ] On Hearth chip is display-only (no navigation)
- [ ] When Google Calendar connector is unhealthy: banner renders
- [ ] Tapping the health banner navigates to /control-plane
- [ ] "Open Control Plane" link text is visible on the banner

### /admin - Admin index

- [ ] Each section card navigates to `/admin/{section}` on tap
- [ ] Cards are permission-gated (sections without permission are hidden)

### /members/{id} - Placeholder member card

- [ ] Route loads for a valid kid ID
- [ ] Shows "MEMBER" eyebrow and kid's name
- [ ] Shows "Coming in Phase 3" placeholder
- [ ] When tab query param is present, displays "Tab: {value}"
- [ ] Kid-tier user sees their own card
- [ ] Kid-tier user gets "Not available" for another kid's card
- [ ] Parent-tier user can view any kid's card

### Architecture check

- [ ] `node scripts/architecture-check.js` Check 5 (dead-tap) reports 0 WARN
- [ ] Check 5 enforcement is active (CHECK_5_ENFORCE = true)
- [ ] No new WARN findings introduced by Phase 1

### Smoke tests

- [ ] `npx playwright test tests/interaction-contract.spec.ts` passes
- [ ] navigate-detail tests verify route changes
- [ ] execute-action tests verify filter toggle
- [ ] expand-inline tests verify inline expansion
- [ ] no-op-documented tests verify no navigation
- [ ] CompletionSheet regression test passes
