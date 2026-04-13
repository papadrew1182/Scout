# Scout Frontend Roadmap

Last reconciled: 2026-04-13 against commit `4e8d2e9` on `main`.

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

## 8. Settings — Accounts & Access + AI Flags

**Status:** VERIFIED

**What exists:**
- `scout-ui/app/settings/index.tsx` — My Account (password change, session
  list, revoke others) + Accounts & Access (adults only: create / reset
  password / activate-deactivate / revoke sessions / last-login display).
- **AI settings (new):** two adult-only toggle rows for
  `allow_general_chat` and `allow_homework_help`. PATCH
  `/api/families/{id}/ai-settings`. These flags drive the child-surface
  prompt variants in `backend/app/ai/context.py`.

**Evidence:** `surfaces.spec.ts` asserts role visibility — adult sees
"Accounts & Access", child does not. `settings/index.tsx` is tracked in
git and deployed; the AI-toggle rows are reachable in the local dev
build.

**Missing verification:**
- No E2E for creating a new account or resetting a password.
- No E2E for toggling the AI flags and asserting the child prompt
  variant changes (backend variants themselves are covered by
  `test_ai_context.py`).

**Missing UX/product work:**
- No confirmation dialog before deactivating an account.
- No audit log visible to the user.

**Recommended next step:** smoke for the AI-toggle round-trip; confirmation
dialog for destructive actions; E2E for account creation.

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

**Status:** VERIFIED (Sprint 2, 2026-04-13 — SSE streaming landed in
`4e8d2e9`; all four previous gaps closed)

**What exists:**
- `scout-ui/components/ScoutLauncher.tsx` (597 lines) — slide-up chat
  modal with:
  - Quick-action chips (6 pre-canned prompts)
  - Message history (user bubbles right, assistant left)
  - **SSE streaming** via `sendChatMessageStream()` — typed
    `text` / `tool_start` / `tool_end` / `done` / `error` events patch
    the last assistant bubble as chunks arrive. Non-streaming
    `sendChatMessage()` is the automatic fallback if the stream errors
    before producing any text.
  - `X-Scout-Trace-Id` header forwarded on both streaming and
    non-streaming calls.
  - Handoff cards rendered from `result.handoff` — tap deep-links into
    the created entity via `router.push(route_hint)`.
  - **Confirmation card** rendered from `pending_confirmation` —
    confirm/cancel affordance that re-invokes `/api/ai/chat` with a
    `confirm_tool` payload (bypassing the LLM round).
  - **Disabled-state card** driven by a `readyState` state machine
    (`checking | ok | disabled | error`). On open, the panel calls
    `fetchReady()`; if `ai_available=false` the chat UI never mounts.
- `scout-ui/lib/api.ts` — `fetchReady()`, `sendChatMessage()`, and
  `sendChatMessageStream()` with typed `StreamEvent`, `AIHandoff`,
  `AIPendingConfirmation`, `SendChatOptions`.

**Evidence:**
- `smoke-tests/tests/ai-panel.spec.ts` — 3 tests: content assertion,
  disabled-state (via `page.route()` stub), child-surface open.
- `smoke-tests/tests/ai-roundtrip.spec.ts` — 2 tests: `add_grocery_item`
  quick-action round-trip with handoff tap, `create_event` confirmation
  round-trip.
- **Production backend verified** 2026-04-13 via direct HTTPS round-trip
  + one real adult-user pair captured in Railway logs (see
  `AI_ROADMAP.md` §13).

**Missing verification:**
- Streaming rendering path — the chunks arrive but no Playwright test
  asserts per-chunk updates.
- Deployed browser smoke against Railway + Vercel — direct HTTPS
  round-trip covers the backend path; full Playwright against Vercel is
  still operator-only.
- Conversation resume across panel opens.

**Missing UX/product work:**
- No conversation resume — server persists conversations but the panel
  starts blank each open.
- No per-surface quick-action overrides (same 6 chips everywhere).

**Recommended next step:** wire a CI job that runs the AI panel +
roundtrip smoke against `scout-ui-gamma.vercel.app` using the
Railway-stored smoke credentials.

## 11. Loading / Empty / Error / Retry States

**Status:** VERIFIED (Sprint 1 residual closeout, 2026-04-13 — global
error boundary landed + Playwright verification via gated `/__boom`
route)

**What exists:**
- Per-component `ActivityIndicator` (loading)
- Error text with retry button on data-fetching components
  (`ActionInbox.tsx`, `meals/prep.tsx`, parent dashboard)
- Empty-state messaging on every list view
- **Global `ErrorBoundary`** in `scout-ui/components/ErrorBoundary.tsx`,
  wrapped around `AuthProvider + AppShell` in `app/_layout.tsx`. Catches
  render-time errors anywhere below the shell and renders a
  "Something went wrong — Reload" fallback, with
  `data-testid="scout-error-boundary"`. Logs via
  `console.error("[Scout ErrorBoundary]", ...)`.
- **DEV/E2E-only `/__boom` route** (`scout-ui/app/__boom.tsx`) that
  triggers a render crash when `EXPO_PUBLIC_SCOUT_E2E=true` at build
  time, so Playwright can verify the boundary end-to-end. Production
  builds render an inert "Not available" stub.

**Evidence:** `smoke-tests/tests/error-boundary.spec.ts` exercises the
boundary via `/__boom` when the E2E flag is set.

**Missing verification:** boundary is not asserted against production
builds (expected — the gate is deliberate).

**Missing UX/product work:**
- No production error reporting provider (Sentry or equivalent) yet —
  the boundary logs to stdout only.
- No skeleton loaders — everything is `ActivityIndicator` spinners.
- No offline / stale-data banner.

**Recommended next step:** wire an error-reporting provider into
`ErrorBoundary.componentDidCatch` in Sprint 2.

## 12. Smoke Coverage

**Status:** VERIFIED locally / PARTIAL against deployed URLs (28 tests
across 8 files; not yet run through CI against `scout-ui-gamma.vercel.app`)

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
- AI tool execution that asserts the created entity is visible on its
  target screen (handoff taps verify navigation, not target content).
- Streaming rendering path — chunks arrive but no per-chunk assertion.
- Account create / password reset through the adult settings screen.
- AI-settings toggles on the Settings screen (`allow_general_chat`,
  `allow_homework_help`).
- Deployed browser smoke against Railway + Vercel in CI (backend path
  already verified via direct HTTPS round-trip; operator checklist in
  `docs/AI_OPERATOR_VERIFICATION.md`).

**Recommended next step:** wire deployed-URL smoke into CI using the
Railway-stored `SCOUT_SMOKE_ADULT_*` credentials.

## 13. Deployment / Web Readiness

**Status:** VERIFIED

**What exists:**
- `scout-ui/Dockerfile` — Node 20 slim, `expo export --platform web`, serves `dist` on port 3000
- `scout-ui/vercel.json` — `buildCommand: npm run build:web`, `outputDirectory: dist`, SPA rewrite
- `scout-ui/railway.json` — same build, serve `dist`, healthcheck `/`
- `scout-ui/app.json` — Expo config with metro web bundler, single output

**Evidence:** deployed at `https://scout-ui-gamma.vercel.app`; 9/9
deployed auth + surfaces smoke passed at initial launch 2026-04-12
(`c29a5d0`); production AI backend path VERIFIED 2026-04-13
(`782c3ef`) via direct HTTPS round-trip. Deployed-URL **browser**
Playwright in CI is the one residual — tracked as top backlog item.

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

Sprint 1 work is complete. Remaining Sprint 2 items, in priority order:

1. **Deployed browser smoke in CI** — wire the Playwright suite against
   `scout-ui-gamma.vercel.app` using the Railway-stored smoke credentials.
2. **Production error reporting (Sentry-equivalent)** — wire into
   `ErrorBoundary.componentDidCatch`.
3. **Streaming assertion depth** — one Playwright test that asserts
   per-chunk updates arrive before `done`.
4. **AI-settings toggle smoke** — verify the `allow_general_chat` /
   `allow_homework_help` flags round-trip from the Settings UI.
5. **Bonus / penalty parent payout** — blocked on backend endpoint; UI
   is already the right home.
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

- **Deployed browser smoke in CI** — 28 Playwright tests run locally
  and against a local stack; no CI job runs them against
  `scout-ui-gamma.vercel.app` yet.
- **Streaming assertion depth** — the panel uses SSE streaming but no
  test asserts per-chunk updates.
- **AI-settings toggle round-trip** — adult can toggle the flags but no
  smoke verifies the round-trip.
- **Bonus / penalty parent UX** — buttons rendered, handlers are stubs.
- **RexOS / Exxir panels** — placeholder copy only.
- **Household insight banner** — rule-based, not AI-driven (may be fine
  permanently).
- **Notification badge for Action Inbox** — does not exist.
- **Production error reporting** — global `ErrorBoundary` logs to
  stdout; no Sentry-equivalent.
- **Bundle / Web Vitals / accessibility** — unmeasured.

## Front-end Deferred Ledger

| Item | Why deferred | Launch impact | Next window |
|---|---|---|---|
| Deployed browser smoke in CI | Direct HTTPS round-trip verified the backend AI path; browser-against-Vercel run is operator-only today | Medium — deploy drift between local and Vercel can land unseen | Sprint 2 |
| Streaming assertion depth | SSE shipped and panel consumes it; basic smoke is enough for launch | Low | Sprint 2 tail |
| AI-settings toggle smoke | Backend variants covered by pytest | Low | Sprint 2 |
| Conversation resume in ScoutPanel | Server persists conversations; panel always opens blank | Low | Later |
| Handoff target-screen content assertion | Current smoke verifies navigation, not target content | Low | Sprint 2 |
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

- Does the parent household insight banner's `off_track` / `at_risk`
  logic match a product owner's intent, or is it a rough heuristic?
- Does `sendChatMessageStream` gracefully handle a 60s timeout or a
  mid-stream disconnect without tearing the panel state? No Playwright
  test forces this.
- Does the deployed Vercel bundle render every handoff entity type
  correctly (`personal_task`, `event`, `meal_plan`, `grocery_item`,
  `purchase_request`, `note`, `chore_instance`)? Local tests cover a
  subset; deployed-URL coverage is operator-only.

---

## Top 10 Frontend Deferred Items

Prioritized deferred work, worst-impact-first:

1. **Deployed browser smoke in CI** (§12, §10) — wire Playwright against
   `scout-ui-gamma.vercel.app` using the Railway-stored smoke credentials.
   Single biggest trust gap left.
2. **Production error reporting (Sentry or equivalent)** (§11, §13) —
   global `ErrorBoundary` exists and is tested; it logs to stdout only.
3. **Streaming assertion depth** (§10) — SSE path is live and used; no
   Playwright test asserts chunk-by-chunk rendering.
4. **AI-settings toggle smoke** (§8) — Settings page now has
   `allow_general_chat` / `allow_homework_help` toggles; no smoke
   verifies the PATCH round-trip or the resulting child-prompt variant.
5. **Parent payout bonus / penalty handlers** (§4) — UI buttons
   rendered; handlers are stubs. Blocked on backend endpoint landing.
6. **Conversation resume across sessions** (§10) — server persists
   conversations; panel always opens blank.
7. **Account create / password reset smoke** (§8) — adult-facing flows
   not covered by Playwright.
8. **Handoff target-screen content assertion** (§10) — taps verify
   navigation; no test asserts the new entity is visible on the target
   screen.
9. **RexOS / Exxir personal-surface panels** (§3) — product decision:
   build, remove, or re-label as "coming soon". Placeholder copy only.
10. **Bundle-size CI gate + Web Vitals** (§13) — no measurement today.

See the full `Front-end Deferred Ledger` table above for the long tail
(skeleton loaders, accessibility, mobile-web, multi-member session
switching, offline/PWA, etc.).

---

## 5 Strongest Frontend Surfaces

Ranked by evidence strength and launch-readiness:

1. **Auth UX** (§2) — 5 smoke tests covering adult login, child login,
   bad password, sign-out, and invalid-token recovery.
2. **AI Panel / ScoutLauncher** (§10) — 3 panel tests + 2 round-trip
   tests (tool + confirmation) + SSE streaming + disabled-state card
   + production backend path verified via direct HTTPS round-trip +
   one real user pair captured in Railway logs.
3. **App Shell / Nav / Scout Launcher** (§1) — transitively smoked by
   every surface test; role-gated nav verified.
4. **Error handling** (§11) — global `ErrorBoundary` with a gated
   `/__boom` test path verifying the render fallback.
5. **Settings — Accounts & Access + AI Flags** (§8) — role visibility
   asserted both ways; session management flows exist; AI-toggle rows
   wired through to backend + `test_ai_context.py` variants.

---

## 5 Weakest or Least-Verified Frontend Areas

Ranked by verification gap and product risk:

1. **Deployed browser smoke in CI** (§12) — backend is verified end-to-end
   against production; the full Playwright suite has never been run
   against `scout-ui-gamma.vercel.app` from CI. Biggest trust gap left.
2. **Streaming assertion depth** (§10) — SSE path is live in the panel;
   no Playwright test asserts per-chunk updates.
3. **Production error reporting** (§11, §13) — global `ErrorBoundary`
   logs to stdout only; no Sentry-equivalent provider.
4. **Settings AI-toggle smoke** (§8) — backend variants covered by
   pytest; the browser round-trip is not.
5. **Personal surface placeholder panels** (§3) — RexOS + Exxir panels
   are stub copy pending a product decision.

---

## File summary

**Scope:** 14 sections covering every shipped frontend surface + platform system, each with `status`, `what exists`, `evidence`, `missing verification`, `missing UX / product work`, and `recommended next step`.

**Status distribution** (of the 14 sections):
- `VERIFIED`: 10 (shell/nav, auth, personal, parent, child, grocery, settings, action inbox, deployment, shared platform)
- `IMPLEMENTED`: 3 (meals, AI panel, loading/error/retry)
- `VERIFIED as launch gate / PARTIAL for depth`: 1 (smoke coverage)

Meals is labeled "VERIFIED (core) / IMPLEMENTED (subpages)" reflecting the mixed state of `this-week.tsx` (VERIFIED) vs `prep.tsx` / `reviews.tsx` (UNKNOWN without a smoke or audit).

**Key reconciliation notes:**
- The frontend is **private-launch ready and production-verified**
  (28 local Playwright tests passing; production AI backend verified
  end-to-end via direct HTTPS round-trip + real user pair in Railway
  logs).
- It is **not strategically complete** — the gap between
  "launch-sufficient" and "complete" is primarily deployed browser
  smoke in CI, streaming assertion depth, production error reporting,
  and AI-settings toggle smoke.
- AI panel moved from "single biggest verification risk" to a solid
  middle: 5 browser tests + production round-trip + real-user logs.
  The remaining AI risk is deploy drift between local and the Vercel
  bundle.
- Backend coverage (349 tests; 58 AI-layer) now offsets most regression
  risk for business logic; UI wiring regressions would still escape CI
  until deployed-URL smoke runs on every push.

**Freshness:**
- Branch: `docs/final-roadmap-resync`
- Last reconciled: 2026-04-13
- Reference commits: `4e8d2e9` (SSE streaming + conversation kind +
  moderation alerts), `8647e00` (broad chat + homework help + moderation
  + weather), `782c3ef` (Whitfield → Roberts rename + prod AI
  verification), `5f11821` (Sprint 1 closeout: confirmation UI +
  disabled-state + ErrorBoundary), `9481f8f` (trace-id correlation
  logging)
