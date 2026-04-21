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

---

## Phase 2 - Manual Data Entry Restoration

### Pre-flight

- [ ] Migration 040_phase2_permissions.sql applied to database
- [ ] `npx tsc --noEmit` passes
- [ ] Backend pytest suite passes (349+ tests)

### Backend permission gates

- [ ] `POST /api/families/{id}/personal-tasks` returns 403 for DISPLAY_ONLY tier
- [ ] `POST /api/families/{id}/personal-tasks` returns 201 for CHILD tier
- [ ] `POST /api/families/{id}/events` returns 403 for CHILD tier
- [ ] `POST /api/families/{id}/events` returns 201 for TEEN tier
- [ ] `POST /api/families/{id}/chore-templates` returns 403 for TEEN tier
- [ ] `POST /api/families/{id}/chore-templates` returns 201 for PRIMARY_PARENT
- [ ] `POST /api/families/{id}/meals` returns 403 for TEEN tier
- [ ] `POST /api/families/{id}/meals` returns 201 for PARENT tier

### Personal tasks - /today

- [ ] "Add task" button visible on /today
- [ ] Tapping opens AddTaskSheet inline
- [ ] Title field is required (shows error if empty)
- [ ] Due date field is optional
- [ ] Submitting creates the task via API
- [ ] Sheet closes after successful creation
- [ ] Board refreshes to show new task

### Calendar events - /calendar

- [ ] "Add event" button visible on /calendar
- [ ] Tapping opens AddEventSheet inline
- [ ] Title, start, and end fields are required
- [ ] Validates end > start
- [ ] All-day and Hearth toggles work
- [ ] Submit is disabled when user lacks calendar.manage_self
- [ ] Creates event via API and closes sheet

### Chore templates - /admin/chores/new

- [ ] Form renders with name, description, cadence, due time fields
- [ ] Cadence chip selector works (daily/weekly/monthly/odd-even)
- [ ] Submit creates template via API
- [ ] Success message appears after creation
- [ ] Child user sees permission denial message

### Meal staples - /admin/meals/staples/new

- [ ] Form renders with name, protein, pattern, prep time fields
- [ ] Pattern chip selector works
- [ ] Submit creates meal via API
- [ ] Success message appears after creation
- [ ] Child user sees permission denial message

### Architecture check

- [ ] `node scripts/architecture-check.js` shows reduced Check 1 WARN count
- [ ] Known Gaps table updated for resolved routes

### Smoke tests

- [ ] `npx playwright test tests/data-entry.spec.ts` passes
- [ ] Happy-path tests for all four domains
- [ ] Permission-denial tests for admin forms

---

## Phase 6 - Finish Affirmations

### User surface

- [ ] AffirmationCard renders on /today after the summary strip
- [ ] Card shows affirmation text with category and tone metadata
- [ ] Reaction buttons visible (Heart, Nope, Skip, Later)
- [ ] Tapping a reaction animates the card out
- [ ] Refreshing shows a different affirmation (within cooldown rules)
- [ ] AffirmationPreferences section visible on /settings

### Admin surface

- [ ] Admin affirmations page accessible at /admin/affirmations
- [ ] Library tab shows list of affirmations with active/inactive toggle
- [ ] Governance tab shows config (cooldown, repeat window, etc.)
- [ ] Targeting tab shows per-member enable/disable toggles
- [ ] Analytics tab shows delivery and reaction counts
- [ ] Child user cannot access /admin/affirmations

### Validation items (spec section 7)

- [ ] 1. Admin routes return 403 without affirmations.manage_config
- [ ] 2. Max 1 affirmation visible, reactions available
- [ ] 3. Zero admin controls on user surface
- [ ] 4. Thumbs-down removes affirmation from rotation
- [ ] 5. Heart boosts category weight
- [ ] 6. Cooldown prevents re-show
- [ ] 7. Admin CRUD works
- [ ] 8. Analytics returns aggregates
- [ ] 9. Family-level disable works
- [ ] 10. Member-level disable works

### Smoke tests

- [ ] `npx playwright test tests/affirmations.spec.ts` passes

---

## Expansion Phase 1 — Push notifications

### Prerequisites

- [ ] `PUSH_PROVIDER=expo` set in Railway env
- [ ] `EXPO_PUBLIC_PUSH_PROVIDER=expo` set in Vercel env
- [ ] EAS project ID populated in `scout-ui/app.json` (`expo.extra.eas.projectId`)
- [ ] APNs Auth Key uploaded to the Scout Expo project
- [ ] Apple Developer bundle ID registered for production

### Backend tests

- [ ] `py -m pytest backend/tests/test_push_notifications.py` — 13 tests
      covering service happy-path, receipt polling, DeviceNotRegistered
      deactivation, route permission denial, and AI tool push/fallback
- [ ] Full suite green at or above prior passing count

### User surface

- [ ] `/settings/notifications` renders for all tiers
- [ ] On web build, a non-error "not supported" notice appears
- [ ] Registered devices list reflects the current actor only
- [ ] Recent notifications list reflects the current actor only
- [ ] Revoke button deactivates a device and the list refreshes

### Admin surface

- [ ] Admins see the "Send a test push" card on /settings/notifications
- [ ] Admins see the "Family delivery log" card on /settings/notifications
- [ ] Child-tier actor receives 403 on POST /api/push/test-send
- [ ] Child-tier actor receives 403 on GET /api/push/deliveries
      (family-wide log)

### Provider semantics

- [ ] A successful Expo ticket sets delivery row `status=provider_accepted`
      and stores `provider_ticket_id`
- [ ] Receipt polling transitions rows to `provider_handoff_ok` or
      `provider_error`
- [ ] DeviceNotRegistered (ticket or receipt) deactivates
      `scout.push_devices.is_active`

### Scheduler

- [ ] APScheduler tick (5 min) invokes `run_push_receipt_poll_tick`
- [ ] Advisory lock gate is respected — two app instances do not
      double-poll

### AI tool

- [ ] With an active device and an accepted ticket,
      `send_notification_or_create_action` returns
      `status=push_delivered` and creates no ParentActionItem
- [ ] With no active device, the tool returns
      `status=fallback_action_inbox` and creates one ParentActionItem

### Manual physical-device validation

- [ ] Install the Scout app on a physical iPhone and sign in
- [ ] Device appears under /settings/notifications → Registered devices
- [ ] Admin sends a test push from another session
- [ ] iPhone displays the notification
- [ ] Tapping the notification opens Scout and `tapped_at` populates

### Smoke tests

- [ ] `npx playwright test tests/push-notifications.spec.ts` passes
