# Scout Frontend Roadmap

Last reconciled: 2026-04-13 against commit `9481f8f` on `main`.

This is the frontend roadmap for Scout. The frontend lives in `scout-ui/`
(Expo / React Native Web, deployed via `expo export --platform web`).

A screen-data readiness audit is not the same thing as a frontend roadmap.
This document tracks UX maturity and remaining polish, not just "did the
data reach the screen." For the cross-surface reconciliation see
`docs/ROADMAP_RECONCILIATION.md`.

## Status Legend

- **VERIFIED** — code exists and is exercised by Playwright smoke or
  documented deploy verification.
- **IMPLEMENTED** — code exists but is not covered by smoke.
- **PARTIAL** — only part of the intended surface exists.
- **DEFERRED** — intentionally later.
- **UNKNOWN** — not enough evidence to judge.

"VERIFIED" means *private-launch ready*, not *strategically complete*. The
two summary sections at the bottom separate those.

## 1. App Shell / Nav / Scout Launcher

**Status:** VERIFIED

**What exists:**
- `scout-ui/app/_layout.tsx` — root layout, `AuthProvider`, `NavBar`, Scout panel wrapper
- `scout-ui/components/NavBar.tsx` — Personal / Parent / Meals / Grocery / Settings tabs, Scout AI button, child-member dropdown
- `scout-ui/components/ScoutLauncher.tsx` — slide-up modal AI chat panel
- `scout-ui/app/index.tsx` — root redirect / home

**Evidence:** every surface test in `smoke-tests/tests/surfaces.spec.ts` traverses the shell.

**Missing verification:** none for private launch.

**Missing UX/product work:** no top-bar notification badge for Action Inbox count.

**Recommended next step:** leave as-is for launch; revisit badge after Action Inbox gains filters.

## 2. Auth UX

**Status:** VERIFIED

**What exists:**
- `scout-ui/lib/auth.tsx` — `AuthProvider` with localStorage token persistence, `/api/auth/me` revalidation, login/logout, member context
- `scout-ui/components/LoginScreen.tsx` — email/password with error + loading states
- `scout-ui/app/settings/index.tsx` — password change, session list, "revoke other sessions"

**Evidence:** `smoke-tests/tests/auth.spec.ts` — 5 tests (adult login, child login, bad password, sign-out, invalid-token recovery).

**Missing verification:** none.

**Missing UX/product work:**
- No "switch to another member" UI within a single logged-in session. Each member signs in individually.
- No password-strength meter on password change.
- No email-based password reset (admin-initiated only).

**Recommended next step:** ship launch as-is. Revisit multi-member switching if usage shows frequent sign-in churn.

## 3. Personal Surface

**Status:** VERIFIED

**What exists:**
- `scout-ui/app/personal/index.tsx` — today priority layer (urgent tasks, events, overdue bills), combined calendar (next 3 days), top-5 personal tasks, Scout snapshot, finance snapshot, recent notes, dev-mode ingestion buttons
- RexOS + Exxir collapsible panels (placeholder copy only)

**Evidence:** `surfaces.spec.ts` loads the dashboard and waits for "Dashboard" text.

**Missing verification:** smoke does not assert any specific tile's data — only that the page renders.

**Missing UX/product work:**
- RexOS / Exxir panels are stubs. Product decision needed: build, remove, or re-label as "coming soon".
- Dev-mode Google Calendar / YNAB ingestion buttons are gated by `DEV_MODE` but production behavior has not been audited.
- No loading skeleton; initial render is a spinner.

**Recommended next step:** decide RexOS/Exxir fate; audit DEV_MODE gate before next prod deploy.

## 4. Parent Surface

**Status:** VERIFIED

**What exists:**
- `scout-ui/app/parent/index.tsx` — full parent dashboard:
  - Household insight banner (rule-based `on_track` / `at_risk` / `off_track` / `complete`)
  - Action Inbox component
  - Family schedule (next 3 days)
  - Kids today status (per-child task completion)
  - Weekly progress (wins / 5 days, status pill)
  - Meals + Bills sections
  - Household overview stats
  - Weekly payout with per-child baseline + earned amount
  - "Run Weekly Payout" button

**Evidence:** parent surface touched via `surfaces.spec.ts` + role visibility test ("Accounts & Access" assertion).

**Missing verification:** smoke does not actually run a weekly payout or exercise the insight banner variants.

**Missing UX/product work:**
- **Bonus / penalty** buttons on the payout card are rendered but "not implemented yet" — matches backend gap.
- Household insight banner is rule-based, not AI-driven.
- No drill-in from "kids today status" to individual child detail page.

**Recommended next step:** wire bonus/penalty once backend endpoint lands; add drill-in link to child surface.

## 5. Child Surface

**Status:** VERIFIED

**What exists:**
- `scout-ui/app/child/[memberId].tsx` — per-child view: progress summary, schedule filtered by `is_hearth_visible`, responsibilities grouped by routine vs chore, today's meals, weekly wins M–F dot display, earned payout, `NeedSomething` widget

**Evidence:** child login path exercised in `auth.spec.ts`; child does NOT see "Accounts & Access" asserted in `surfaces.spec.ts`.

**Missing verification:**
- No E2E for actually completing a task (step-tracking via `TaskCard`).
- No E2E for using `NeedSomething` as a child.

**Missing UX/product work:**
- No celebration / confetti on "last task done" day.
- No way for a child to view their own history beyond the current week.

**Recommended next step:** add task-completion E2E first; polish celebration state later.

## 6. Meals UX

**Status:** VERIFIED (core) / IMPLEMENTED (subpages)

**What exists:**
- `scout-ui/app/meals/_layout.tsx` — tab layout
- `scout-ui/app/meals/index.tsx` — redirect to `/meals/this-week`
- `scout-ui/app/meals/this-week.tsx` — current-week plan display, AI questions → answers → regenerate → approve workflow, plan archive, regenerate-day actions
- `scout-ui/app/meals/groceries.tsx` — plan-specific groceries grouped by store
- `scout-ui/app/meals/prep.tsx` (122 lines) — Sunday prep view with tasks + timeline from `plan.prep_plan`, retry + empty states
- `scout-ui/app/meals/reviews.tsx` (417 lines) — per-meal reviews with rating (1–5), leftover options (none/some/plenty), repeat/tweak/retire decisions, summary view

**Evidence:** `surfaces.spec.ts` loads `meals/this-week` and asserts "This Week".

**Missing verification:**
- AI generation loop (questions → approve) is not smoke-tested.
- `prep.tsx` and `reviews.tsx` have never been exercised by a smoke test.
- No test for plan archive or day-regenerate actions.

**Missing UX/product work:**
- No history view for past weekly plans beyond the approved/archived distinction.
- Reviews page cannot filter by member or rating.

**Recommended next step:** add a smoke test that loads `this-week` after a plan exists and asserts the generation buttons render. Skip generating through AI in smoke (slow + flaky).

## 7. Grocery / Purchase Request UX

**Status:** VERIFIED

**What exists:**
- `scout-ui/app/grocery/index.tsx` — active items (grouped by store), purchased items, pending-review, purchase-requests with urgency badges, approve / reject / convert actions
- `scout-ui/components/NeedSomething.tsx` — shared reusable form across personal / parent / child surfaces

**Evidence:** `surfaces.spec.ts` loads the grocery page and confirms body renders.

**Missing verification:** no smoke path for approving a pending item or converting a request. Backend `test_grocery.py` (26 tests) covers it at the service layer.

**Missing UX/product work:**
- No bulk actions (approve all, move all to purchased).
- No history tab for recently-purchased items.

**Recommended next step:** add E2E for the approve-pending flow — it's the highest-value missing smoke.

## 8. Settings — Accounts & Access

**Status:** VERIFIED

**What exists:**
- `scout-ui/app/settings/index.tsx` — My Account (password change, session list, revoke others) + Accounts & Access (adults only: create / reset password / activate-deactivate / revoke sessions / last-login display)

**Evidence:** `surfaces.spec.ts` asserts role visibility — adult sees "Accounts & Access", child does not.

**Missing verification:** no E2E for actually creating a new account or resetting a password.

**Missing UX/product work:**
- No confirmation dialog before deactivating an account.
- No audit log visible to the user.

**Recommended next step:** add a confirmation dialog for destructive actions; E2E for account creation.

## 9. Parent Action Inbox

**Status:** VERIFIED

**What exists:**
- `scout-ui/components/ActionInbox.tsx` — modal with color-coded badges for `grocery_review`, `purchase_request`, `meal_plan_review`; auto-routes to the right page on tap; load / error / empty states; retry button.
- Rendered on parent dashboard.

**Evidence:** parent surface smoke hits the page that mounts the inbox.

**Missing verification:** no smoke asserts the inbox actually displays items, or that tapping routes correctly.

**Missing UX/product work:**
- No pagination / filter; single flat list. Fine at family-scale volume.
- No "mark as read" semantics — items disappear when acted on, but if a parent ignores an item it stays forever.

**Recommended next step:** none for launch. Revisit filtering when the list consistently exceeds ~15 items.

## 10. AI Panel UX and Handoff

**Status:** IMPLEMENTED (Sprint 1 closeout, 2026-04-13 — confirmation flow + disabled state landed; smoke deepened)

**What exists:**
- `scout-ui/components/ScoutLauncher.tsx` — slide-up chat modal with:
  - Quick-action chips (6 pre-canned prompts)
  - Message history (user bubbles right, assistant left)
  - `X-Scout-Trace-Id` header for backend correlation (commit `9481f8f`)
  - Handoff cards rendered from `result.handoff` — tap deep-links into the created entity
  - **Confirmation card** rendered from `result.pending_confirmation` — confirm/cancel affordance that re-invokes `/api/ai/chat` with a structured `confirm_tool` payload (Sprint 1 closeout, `5f11821`)
  - **Disabled-state card** when `/ready.ai_available=false` — probed via `fetchReady()` on panel open; the chat UI never mounts in the disabled state (Sprint 1 closeout, `5f11821`)
- `scout-ui/lib/api.ts :: sendChatMessage()` — single POST to `/api/ai/chat`, awaits full JSON response. Options signature now accepts `{ confirmTool }` for the confirmation resubmit path.

**Evidence:** `smoke-tests/tests/ai-panel.spec.ts` — **3 tests**: content assertion (non-empty response), disabled-state (stub `/ready` via `page.route()`), child-surface open-without-crash. Plus new round-trip tests in `ai-roundtrip.spec.ts` when AI is enabled (see §12).

**Missing verification:**
- No test covers conversation resume across panel opens (conversations persist server-side).
- AI round-trip + confirmation round-trip run only when `ai_available=true` at test start (they skip otherwise).

**Missing UX/product work:**
- **No streaming.** The panel shows a spinner until the whole response arrives. Biggest perceived-latency issue in the product.
- No conversation resume — server persists conversations but the panel starts blank each open.
- No typing indicator (because no streaming).
- No per-surface quick-action overrides (same 6 chips everywhere).

**Recommended next step:** streaming response pipeline is the single biggest UX win for AI; tracked as AI Roadmap Phase A item.

## 11. Loading / Empty / Error / Retry States

**Status:** IMPLEMENTED (Sprint 1 closeout, 2026-04-13 — global error boundary landed)

**What exists:**
- Per-component `ActivityIndicator` (loading)
- Error text with retry button on data-fetching components (`ActionInbox.tsx`, `meals/prep.tsx`, parent dashboard)
- Empty-state messaging on every list view
- **Global `ErrorBoundary` (new)** in `scout-ui/components/ErrorBoundary.tsx`, wrapped around the AuthProvider + AppShell in `app/_layout.tsx`. Catches render-time errors anywhere below the shell and renders a "Something went wrong — Reload" fallback. Logs via `console.error("[Scout ErrorBoundary]", ...)` for forwarding to a future error-reporting provider.

**Missing verification:** no Playwright test forces a render crash to assert the boundary renders. The boundary is currently verified by code review + manual inspection.

**Missing UX/product work:**
- No production error reporting provider (Sentry or equivalent) yet — the boundary logs to stdout only.
- No skeleton loaders — everything is `ActivityIndicator` spinners.
- No offline / stale-data banner.

**Recommended next step:** wire an error-reporting provider into `ErrorBoundary.componentDidCatch` in Sprint 2.

## 12. Smoke Coverage

**Status:** VERIFIED (Sprint 1 residual closeout, 2026-04-13 — suite expanded from 13 to 28 tests)

**What exists:**
- `smoke-tests/tests/auth.spec.ts` — 5 tests (auth happy path + error paths)
- `smoke-tests/tests/surfaces.spec.ts` — 7 tests (read-path load on every main surface + role visibility)
- `smoke-tests/tests/ai-panel.spec.ts` — **3 tests** (content assertion, disabled-state stub via `page.route()`, child surface open)
- `smoke-tests/tests/write-paths.spec.ts` — 6 write-path tests: approve pending grocery, approve draft meal plan (no longer annotated-skip — the seed now deterministically surfaces a draft), run weekly payout, convert purchase request, child task completion, child meal-review submit.
- `smoke-tests/tests/meals-subpages.spec.ts` — 3 meals tests: `this-week` renders seeded draft plan, `prep` loads (header or empty state), `reviews` loads with Save Review form.
- `smoke-tests/tests/dev-mode.spec.ts` — 1 test asserting `DevToolsPanel` ingestion buttons are NOT rendered on the personal surface.
- `smoke-tests/tests/ai-roundtrip.spec.ts` **(residual closeout)** — 2 conditional AI tests: `add_grocery_item` quick-action round-trip with optional handoff tap; `create_event` confirmation round-trip (assert `pending_confirmation` renders, tap Confirm, assert `confirm_tool` direct-path response). Both skip cleanly when `ai_available=false`.
- `smoke-tests/tests/error-boundary.spec.ts` **(residual closeout)** — 1 test exercising the global `ErrorBoundary`. Navigates to `/__boom`, clicks the trigger, asserts the boundary fallback renders. Gated on `EXPO_PUBLIC_SCOUT_E2E=true` at build time; skips cleanly otherwise.

Total: **28 Playwright tests** (was 13). The only skips now are intentional capability gates (AI enabled / E2E hooks flag), not coverage holes.

**Missing verification — remaining UNCOVERED flows:**
- AI tool execution full round-trip through the UI (create task via AI → verify on Personal).
- AI `confirmation_required` UI round-trip (confirm tap surfaces a second chat call with `confirm_tool`).
- Handoff card deep-link taps.
- Account create / password reset through the adult settings screen.
- Render crash forcing the new global error boundary to render its fallback.
- Deployed browser smoke against Railway + Vercel (still launch-local-only; operator checklist in `AI_ROADMAP.md §10`).

**Recommended next step:** AI tool round-trip + confirmation UI round-trip are the two highest-value remaining write-path tests.

## 13. Deployment / Web Readiness

**Status:** VERIFIED

**What exists:**
- `scout-ui/Dockerfile` — Node 20 slim, `expo export --platform web`, serves `dist` on port 3000
- `scout-ui/vercel.json` — `buildCommand: npm run build:web`, `outputDirectory: dist`, SPA rewrite
- `scout-ui/railway.json` — same build, serve `dist`, healthcheck `/`
- `scout-ui/app.json` — Expo config with metro web bundler, single output

**Evidence:** deployed at `https://scout-ui-gamma.vercel.app`; 9/9 deployed smoke pass per `docs/release_candidate_report.md`.

**Missing verification:**
- No bundle-size budget or CI gate.
- No Web Vitals / Lighthouse tracking.
- No production error reporting (Sentry / equivalent).

**Missing UX/product work:**
- No service worker / offline story.
- No PWA install metadata.

**Recommended next step:** add minimal bundle-size reporting to CI; decide on error reporting provider.

## Shared UX / Platform Systems Already Built

- `lib/auth.tsx` session context + `lib/api.ts` typed API client with trace IDs
- Consistent loading / error / empty / retry pattern per component
- `NeedSomething` reusable widget across personal / parent / child
- Color-coded `ActionInbox` with route handoff
- Role-gated nav (adult vs child) in `NavBar.tsx`
- `meal_plan_hooks.ts` shared across meals pages

## Recommended Next Frontend Sequence

1. **Write-path smoke** — task completion, approve pending grocery, run weekly payout. Converts read-only smoke into a real regression net.
2. **Global error boundary** — cheapest fix for the worst-case blank-screen failure.
3. **AI panel depth** — one tool round-trip smoke + streaming pipeline + confirmation UI.
4. **Bonus / penalty parent payout** — blocked on backend endpoint; UI is already the right home.
5. **DEV_MODE ingestion gate audit** — decide prod behavior before next deploy.
6. **RexOS / Exxir product decision** — build, remove, or re-label.

---

## Front-end VERIFIED Today

Surfaces with code **and** evidence (smoke or deployed verification):

- App shell / nav / Scout launcher
- Auth UX (including bad-password, invalid-token recovery, role visibility)
- Personal surface (page render)
- Parent surface (page render)
- Child surface (page render + role visibility)
- Meals "this week" (page render)
- Grocery page render
- Settings page render + role-gated Accounts & Access
- Action Inbox render (via parent surface)
- AI panel entry point
- Deployment (Railway + Vercel, post-deploy smoke)

## Front-end Launch-Sufficient But Not Complete

Passed the launch gate; not strategically done:

- **AI panel** — one happy-path test covers entry; tool execution, confirmation, history, streaming all absent.
- **Meals subpages (`prep.tsx`, `reviews.tsx`)** — real implementations but no smoke.
- **Write-path coverage across the app** — every main surface is read-path only in smoke.
- **Error states** — per-component only; no global boundary.
- **Bonus / penalty parent UX** — buttons rendered, handlers are stubs.
- **Dev-mode ingestion buttons** — behind a flag that hasn't been audited for prod.
- **RexOS / Exxir panels** — placeholder copy only.
- **Household insight banner** — rule-based, not AI-driven (may be fine permanently).
- **Notification badge for Action Inbox** — does not exist.
- **Bundle / Web Vitals / accessibility** — unmeasured.

## Front-end Deferred Ledger

| Item | Why deferred | Launch impact | Next window |
|---|---|---|---|
| Write-path E2E smoke (task complete, grocery approve, payout, meal-plan approve) | Read-path smoke + backend tests gave adequate confidence | Medium — regressions in write flows wouldn't be caught by CI | Next sprint |
| Global error boundary | Component-level handling covers 99% of cases | Low — worst case is a blank surface | Next sprint |
| AI streaming responses | Request/response works; streaming is UX debt | Perceived latency on long replies | See AI Roadmap Phase A |
| AI panel smoke depth (tools, confirmation, resume) | Happy-path smoke was the launch bar | Medium | Next sprint |
| Confirmation flow UI inside ScoutPanel | Backend returns `confirmation_required` but UI has no affordance | Write tools requiring confirmation currently awkward | AI Roadmap Phase B |
| Bonus / penalty parent payout UX | Backend not yet built | None — parents can still run payout | Next sprint |
| RexOS / Exxir personal-surface panels | Placeholder copy only | None — not exposed as a feature | Later |
| Dev-mode ingestion button audit | Gate exists but not prod-validated | Low — only visible if `DEV_MODE` leaks | Next sprint |
| `meals/prep.tsx` + `meals/reviews.tsx` smoke | Not covered in current suite | Low | Next sprint |
| Task-step completion E2E | Backend tested; UI not | Low | Next sprint |
| Error reporting / Sentry | No provider chosen | Unknown — blind to prod JS errors | Next sprint |
| Bundle-size CI gate + Web Vitals | No measurement yet | None today | Later |
| Accessibility audit | Not run | Unknown | Later |
| Responsive / mobile-web verification beyond smoke | Smoke runs desktop viewport only | Unknown | Next sprint |
| Skeleton loaders (replace spinners) | Functional but not polished | None | Later |
| Multi-member session switching | Each member signs in individually | None at family scale | Later |
| Service worker / offline / PWA | Expo Web does not ship one | None for home use | Later |

## Front-end Unknowns

- Does the current prod build actually hide dev-mode ingestion buttons, or is the flag being set at runtime in production? Needs manual verification.
- Do meals `prep.tsx` and `reviews.tsx` handle the empty-plan / error paths correctly at UI level? Code is present and structured, but not smoked.
- Does `ScoutLauncher` render the AI `result.handoff` button correctly for every entity type? Only the chat response has been smoke-checked.
- Is the parent household insight banner's `off_track` / `at_risk` logic reviewed by a product owner, or is it a rough heuristic nobody has validated?
- Does `sendChatMessage` gracefully handle a 60s timeout without tearing the panel state? No test forces this.
- Raw `grep -c "test("` across `smoke-tests/tests/*.spec.ts` shows 13 test declarations (auth 5 + surfaces 7 + ai-panel 1). `docs/release_candidate_report.md` (commit `549723b`) records 12/12 at preflight. Either a test was added post-preflight or the preflight count missed one — needs a fresh `npx playwright test` run to confirm.

---

## Top 10 Frontend Deferred Items

Prioritized deferred work, worst-impact-first:

1. **Write-path smoke suite** (§12) — task completion, grocery approve, run weekly payout, meal-plan approve, meal review submit. Converts read-only smoke into a real regression net. Highest leverage; no backend dependency.
2. **Global error boundary** (§11) — single top-level `ErrorBoundary` in `_layout.tsx`. Cheapest fix for the worst-case blank-screen failure mode.
3. **AI panel tool-call + confirmation smoke** (§10) — at least one write-tool round-trip asserted, including `confirmation_required: true` branch. Covers the highest-risk interaction surface.
4. **Meals `prep.tsx` + `reviews.tsx` smoke** (§6) — code exists (122 and 417 lines respectively) but both pages are UNKNOWN until exercised by at least a page-load assertion.
5. **AI response streaming pipeline** (§10) — request/response works but there's no token-streaming UI. Biggest perceived-latency issue in the product. Blocks on AI Roadmap Phase A.
6. **Confirmation-flow UI inside ScoutLauncher** (§10) — backend returns `confirmation_required: true` on gated writes but the panel has no affordance to confirm, so users re-ask in plain English.
7. **Parent payout bonus / penalty handlers** (§4) — UI buttons are rendered but "not implemented yet". Blocked on backend endpoints landing.
8. **Dev-mode ingestion button prod audit** (§3) — the `DEV_MODE` gate has not been validated against the production Vercel build; behavior is UNKNOWN.
9. **RexOS / Exxir personal-surface panels** (§3) — product decision: build, remove, or re-label as "coming soon". Placeholder copy only today.
10. **Production error reporting (Sentry or equivalent)** (§13) — production JS errors are currently invisible. No provider chosen.

See the full `Front-end Deferred Ledger` table above for the long tail (skeleton loaders, Web Vitals, accessibility, mobile-web, multi-member session switching, offline/PWA, etc.).

---

## 5 Strongest Frontend Surfaces

Ranked by evidence strength and launch-readiness:

1. **Auth UX** (§2) — 5 smoke tests (adult login, child login, bad password, sign-out, invalid-token recovery). Most-covered surface in the repo.
2. **Settings — Accounts & Access** (§8) — role visibility asserted both ways (adult sees, child does not); session management flows exist; page loads asserted for both roles.
3. **App Shell / Nav / Scout Launcher** (§1) — transitively smoked by every surface test; role-gated nav verified; shell has been stable across all releases.
4. **Deployment / Web Readiness** (§13) — Docker + Vercel + Railway all green; deployed smoke passing at `scout-ui-gamma.vercel.app`; 9/9 deployed smoke pass per `release_candidate_report.md` at commit `c29a5d0`; 12/12 at preflight `549723b`.
5. **Shared UX / Platform Systems** (§14) — `lib/auth.tsx`, `lib/api.ts` with trace IDs, reusable components (`ActionInbox`, `NeedSomething`, `TaskCard`, `StepList`, `DataCard`); used across every surface and stable.

---

## 5 Weakest or Least-Verified Frontend Areas

Ranked by verification gap and product risk:

1. **AI Panel / ScoutLauncher** (§10) — 3 local smoke tests + conditional AI round-trip + confirmation round-trip when enabled. Still no conversation resume coverage, no streaming. Biggest remaining risk is deploy drift (local-only smoke; deployed-URL run is operator-only).
2. **Write paths across Parent / Grocery / Child surfaces** (§4, §5, §7) — 6 write-path tests now cover approve grocery, approve meal plan, run payout, convert purchase request, child task completion, child meal-review. Any new write flow added after this still lacks smoke until added explicitly.
3. **Meals subpages `prep.tsx` + `reviews.tsx`** (§6) — page-load smoke landed; generation-loop still not smoke-tested.
4. **Loading / Error / Retry states** (§11) — per-component handling + global `ErrorBoundary` in `_layout.tsx`. Error reporting provider not wired (Sentry-equivalent is Sprint 2 item).
5. **Personal surface placeholder panels** (§3) — RexOS + Exxir panels are stub copy; dev-mode ingestion verified safe in prod (`DEV_MODE = !EXPO_PUBLIC_API_URL`, baked at compile time, asserted by `dev-mode.spec.ts`).

---

## File summary

**Scope:** 14 sections covering every shipped frontend surface + platform system, each with `status`, `what exists`, `evidence`, `missing verification`, `missing UX / product work`, and `recommended next step`.

**Status distribution** (of the 14 sections):
- `VERIFIED`: 10 (shell/nav, auth, personal, parent, child, grocery, settings, action inbox, deployment, shared platform)
- `IMPLEMENTED`: 3 (meals, AI panel, loading/error/retry)
- `VERIFIED as launch gate / PARTIAL for depth`: 1 (smoke coverage)

Meals is labeled "VERIFIED (core) / IMPLEMENTED (subpages)" reflecting the mixed state of `this-week.tsx` (VERIFIED) vs `prep.tsx` / `reviews.tsx` (UNKNOWN without a smoke or audit).

**Key reconciliation notes:**
- The frontend is **private-launch ready** (12/12 smoke passing at commit `549723b`, all critical surfaces covered by at least a page-load test, all role-gating verified both ways).
- It is **not strategically complete** — the gap between "launch-sufficient" and "complete" is primarily write-path smoke coverage, AI panel depth, and the global error boundary.
- AI panel is the single biggest verification risk per surface area.
- Backend coverage (320 tests per preflight) partially offsets the frontend write-path gap, but regressions in UI wiring would still escape CI.

**Freshness:**
- Branch: `docs/roadmap-reconciliation`
- Last reconciled: 2026-04-13
- Reference commits: `c527fdf` (previous reconciliation), `9481f8f` (AI chat schema fix, added `X-Scout-Trace-Id`), `549723b` (launch preflight)
