# Scout Frontend Roadmap

Last reconciled: 2026-04-12 against commit `9481f8f` on `main`.

This is the first frontend roadmap for Scout. The frontend lives in `scout-ui/`
(Expo / React Native Web, served via `expo export --platform web`). This doc is
the planning layer — for the cross-surface reconciliation see
`docs/ROADMAP_RECONCILIATION.md`.

A screen-data readiness audit is not the same thing as a frontend roadmap.
This document tracks UX maturity and remaining polish, not just whether data
is plumbed.

## Status Legend

- **VERIFIED** — code exists and is exercised by Playwright smoke or manual
  deployed verification.
- **IMPLEMENTED** — code exists but not covered by smoke.
- **PARTIAL** — only part of the intended surface exists.
- **DEFERRED** — intentionally later.
- **UNKNOWN** — not enough evidence.

## 1. App Shell, Nav, Scout Launcher
Status: **VERIFIED**

- `scout-ui/app/_layout.tsx` — root layout, `AuthProvider`, `NavBar`, Scout panel
- `scout-ui/components/NavBar.tsx` — Personal / Parent / Meals / Grocery /
  Settings tabs + Scout AI button + child-member dropdown
- `scout-ui/components/ScoutLauncher.tsx` — modal AI chat panel (see AI Roadmap §4)
- `scout-ui/app/index.tsx` — root redirect / quick home

Evidence: smoke tests exercise shell/nav via every surface test in
`smoke-tests/tests/surfaces.spec.ts`.

Gaps: none for private launch.

## 2. Auth UX
Status: **VERIFIED**

- `scout-ui/lib/auth.tsx` — `AuthProvider` with localStorage token persistence,
  `/api/auth/me` revalidation, login/logout, member context
- `scout-ui/components/LoginScreen.tsx` — email/password form, error + loading states
- `scout-ui/app/settings/index.tsx` — password change, session list, revoke-others

Smoke: `smoke-tests/tests/auth.spec.ts` — 5 tests (adult login, child login,
bad password, sign-out, invalid-token recovery).

Gaps:
- No explicit "switch to another member" UI within a single logged-in session.
  Currently each member signs in individually. Fine for v1; debt captured below.

## 3. Personal Surface
Status: **VERIFIED**

- `scout-ui/app/personal/index.tsx` — today priority layer (urgent tasks, events,
  overdue bills), combined calendar, top-5 personal tasks, Scout snapshot,
  finance snapshot, recent notes, dev-mode ingestion buttons

Smoke: `surfaces.spec.ts` loads the dashboard and waits for "Dashboard" text.

Gaps:
- **RexOS** and **Exxir** collapsible panels are placeholder stubs only (copy
  only, no wiring). Captured as deferred UX debt.
- Dev-mode Google Calendar / YNAB ingestion buttons are gated by `DEV_MODE`;
  production build behavior needs a product decision (hide vs gate server-side).

## 4. Parent Surface
Status: **VERIFIED**

- `scout-ui/app/parent/index.tsx` — full parent dashboard:
  - Household insight banner (rule-based on_track / at_risk / off_track / complete)
  - Action Inbox component (grocery, purchase request, meal plan reviews)
  - Family schedule (next 3 days)
  - Kids today status (per-child task completion)
  - Weekly progress (wins / 5 days)
  - Meals + Bills sections
  - Weekly payout with per-child baseline and earned amount
  - "Run Weekly Payout" button wired to backend

Smoke: parent surface touched via `surfaces.spec.ts` + role visibility test.

Gaps:
- **Bonus / penalty** buttons on the payout card are visually present but the
  handlers are "not implemented yet". Matches backend gap (see Backend Roadmap §2).

## 5. Child Surface
Status: **VERIFIED**

- `scout-ui/app/child/[memberId].tsx` — per-child view:
  - Progress summary with encouragement copy
  - Schedule filtered by `is_hearth_visible`
  - Responsibilities grouped by routine vs chore
  - Meals for today
  - Weekly wins M–F dot display + earned payout
  - `NeedSomething` widget (grocery / purchase request entry)

Smoke: child login path exercised in `auth.spec.ts`; child does NOT see
"Accounts & Access" asserted in `surfaces.spec.ts`.

Gaps:
- Task completion step-tracking relies on `TaskCard` component; no Playwright
  coverage for actually completing a task end-to-end. Debt captured below.

## 6. Meals UX
Status: **IMPLEMENTED** (happy path partially smoked)

- `scout-ui/app/meals/this-week.tsx` — current-week plan display, AI generation
  flow (questions → answers → regenerate → approve), plan archive, regenerate-day
- `scout-ui/app/meals/groceries.tsx` — plan-specific groceries grouped by store
- `scout-ui/app/meals/prep.tsx` — exists; content not re-verified
- `scout-ui/app/meals/reviews.tsx` — exists; content not re-verified
- `scout-ui/app/meals/_layout.tsx` — tab layout

Smoke: `surfaces.spec.ts` loads `meals/this-week` and asserts "This Week".

Gaps:
- AI meal-plan generation flow is not smoke-tested (questions → approve path).
- `prep.tsx` and `reviews.tsx` content was not verified in this reconciliation
  pass — listed as **UNKNOWN** until re-audited.

## 7. Grocery / Purchase Request UX
Status: **VERIFIED**

- `scout-ui/app/grocery/index.tsx` — active items (by store), purchased items,
  pending-review section, purchase-request section with urgency badges,
  approve / reject / convert actions
- `scout-ui/components/NeedSomething.tsx` — shared add-to-list / request form

Smoke: `surfaces.spec.ts` loads `grocery` page.

Gaps:
- No smoke path for actually approving a pending item. Covered by backend
  `test_grocery.py` (26 tests) but not at UI level.

## 8. Settings — Accounts & Access
Status: **VERIFIED**

- `scout-ui/app/settings/index.tsx`:
  - My Account: password change, active session list, revoke others
  - Accounts & Access (adults only): create / reset password / activate /
    deactivate / revoke sessions per member

Smoke: `surfaces.spec.ts` — adult sees "Accounts & Access", child does not.

Gaps: none for private launch.

## 9. Parent Action Inbox
Status: **VERIFIED**

- `scout-ui/components/ActionInbox.tsx` — color-coded cards for
  `grocery_review`, `purchase_request`, `meal_plan_review`; auto-routes to
  the right page on tap
- Rendered on parent dashboard.

Gaps:
- No pagination / filter; single flat list. Fine for family-scale volume.

## 10. Error / Loading / Retry States
Status: **IMPLEMENTED**

- Every data-fetching component has `ActivityIndicator` + error text +
  empty-state messaging.
- `ActionInbox.tsx` includes a retry button on error.

Gaps:
- No global error boundary. Expo Router / React Native Web does not use
  Next.js `error.tsx` / `loading.tsx` conventions, so there is no top-level
  fallback if a render crashes. Debt captured below.

## 11. Playwright Smoke Coverage
Status: **VERIFIED** (for launch gate), **thin** (for feature depth)

- `smoke-tests/tests/auth.spec.ts` — 5 tests
- `smoke-tests/tests/surfaces.spec.ts` — 7 tests (dashboards, meals, grocery,
  settings, role visibility)
- `smoke-tests/tests/ai-panel.spec.ts` — 1 test (quick-action + AI chat)

Total: ~12 Playwright tests, all passing in `ci.yml :: smoke-web` and in
deployed verification.

Gaps:
- Write-path coverage is weak (no task-completion, meal-approval, or
  grocery-approval E2E tests).
- AI panel smoke covers entry-point only, not tool calling or confirmation.

## 12. Deployment / Web Readiness
Status: **VERIFIED**

- `scout-ui/Dockerfile` — Node 20 slim, `expo export --platform web`, serve `dist`
- `scout-ui/vercel.json` — `npm run build:web`, SPA rewrite
- `scout-ui/railway.json` — same build, serve `dist`
- `scout-ui/app.json` — Expo config with metro web bundler

Verified in deployed smoke at `https://scout-ui-gamma.vercel.app`.

Gaps:
- Bundle size / performance budget is unmeasured. No Lighthouse or Web Vitals
  tracking wired up.
- No service worker / offline story.

## Shared UX / Platform Systems Already Built

- `lib/auth.tsx` session context + `lib/api.ts` typed API client with trace IDs
- Consistent error / loading / empty-state pattern per component
- `NeedSomething` reusable widget across personal / parent / child surfaces
- Color-coded `ActionInbox` with route handoff
- Role-gated navigation (adult vs child) via `NavBar.tsx`

## Recommended Next Frontend Sequence

1. **Write-path smoke coverage**: task completion, meal plan approval, grocery
   approval. Converts current read-only smoke into a launch-blocking regression
   net.
2. **Global error boundary** — even a single top-level boundary component
   removes the worst-case "blank screen" failure mode.
3. **Meals `prep.tsx` / `reviews.tsx` audit + smoke** — these pages exist but
   are currently **UNKNOWN** in this reconciliation.
4. **Bonus / penalty UX wiring** — once backend gains the endpoints, the parent
   payout card is already the right home.
5. **Dev-mode ingestion buttons**: decide prod behavior (hide, gate server-side,
   or remove).
6. **RexOS / Exxir placeholder panels** — product decision: build, remove, or
   re-label as "coming soon".

## Deferred Frontend UX / Polish Ledger

| Item | Why deferred | Launch impact | Next window |
|---|---|---|---|
| Global error boundary / fallback screen | Component-level handling covers 99% of cases | Low — worst case is a blank surface | Next sprint |
| Write-path E2E smoke (tasks, meals, grocery) | Read-path smoke + backend tests gave adequate confidence | Medium — regressions in write flows wouldn't be caught by CI | Next sprint |
| Bonus / penalty parent payout UX | Backend not yet built; UI stubs only | None — parents can still run payout | Next sprint |
| RexOS / Exxir personal-surface panels | Placeholder copy only | None — not exposed as a feature | Later |
| Dev-mode ingestion buttons in prod builds | DEV_MODE gate exists but not audited for prod | Low — only visible if `DEV_MODE` leaks | Next sprint |
| Multi-member session switching | Each member signs in individually | None at family scale | Later |
| Bundle / Web Vitals measurement | Untested at launch scale | None today | Later |
| Offline / service worker | Expo Web export does not ship one | None for home use | Later |
| `meals/prep.tsx` + `meals/reviews.tsx` audit | Not re-verified in this pass | UNKNOWN — treat as risk until audited | Next sprint |
| Task-step completion Playwright coverage | Backend tested; UI not | Low | Next sprint |
| Accessibility / a11y audit | Not run | Unknown | Later |
| Responsive / mobile-web verification beyond smoke | Smoke runs desktop viewport only | Unknown | Next sprint |
