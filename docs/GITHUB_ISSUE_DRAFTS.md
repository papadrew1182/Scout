# GitHub Issue Drafts

Last built: 2026-04-13. Last reconciled after Sprint 1 residual closeout.
Source: `docs/EXECUTION_BACKLOG.md`.

Copy-paste ready. One section per top-priority backlog item. Ordered by
the ranked Top 25.

## Sprint 1 closeout status (do not re-open these)

Issues that have already landed in `feat/sprint1-verification-closeout`
(`5f11821`) or `feat/sprint1-residual-closeout` (follow-up):

- **#4 Render confirmation-flow UI inside ScoutPanel** — RESOLVED.
  Backend: `orchestrator.chat()` surfaces `pending_confirmation`
  structurally; new `confirm_tool` direct path. Frontend: confirm/cancel
  card in `ScoutLauncher.tsx`. Backend pytest: 2 new
  `TestPendingConfirmationPlumbing` tests. Browser pytest:
  `ai-roundtrip.spec.ts` covers the round-trip when AI is enabled.
- **#5 Add global frontend error boundary** — RESOLVED.
  `scout-ui/components/ErrorBoundary.tsx` wraps the shell. Residual
  closeout added a Playwright test gated on `EXPO_PUBLIC_SCOUT_E2E=true`.
- **#6 ScoutPanel disabled-state handling** — RESOLVED.
  `fetchReady()` + readyState machine + disabled-state card.
  `ai-panel.spec.ts` stubs `/ready` to prove it.
- **#8 Meals `prep.tsx` + `reviews.tsx` smoke coverage** — RESOLVED.
  `meals-subpages.spec.ts` (3 tests).
- **#10 Dev-mode ingestion button prod behavior** — RESOLVED.
  Audit + `dev-mode.spec.ts` assertion.
- **#2 Write-path E2E smoke suite (6 tests)** — PARTIAL.
  `write-paths.spec.ts` landed with 6 tests. The residual closeout
  tightened the draft-plan approve test so it no longer relies on a
  loud skip.

Issues that are **still open and the checklist below is current**:

- **#1** Deployed AI-panel smoke against Railway + Vercel — BLOCKED on
  operator access. See `docs/AI_OPERATOR_VERIFICATION.md`.
- **#3** Deepen AI panel smoke further — RESIDUAL (round-trip test
  landed; deeper coverage possible).
- **#7** Production error reporting (Sentry-equivalent) — unchanged.
- **#9** Wire `dietary_preferences` into generator — unchanged.

---

---

## 1. Run `ai-panel.spec.ts` against Railway + Vercel for the first time

**Problem statement**

The AI panel Playwright test (`smoke-tests/tests/ai-panel.spec.ts`) has
never been recorded as run against the deployed URLs. The 9/9 deployed
smoke pass in `docs/release_candidate_report.md` covered auth + adult
surfaces only; the AI suite was not part of that run. Deploy drift
between local main and production for the AI path is currently
invisible.

**Acceptance criteria**

- [ ] `npx playwright test smoke-tests/tests/ai-panel.spec.ts --config smoke-tests/playwright.config.ts` runs against `https://scout-ui-gamma.vercel.app` pointing at the production Railway backend and passes.
- [ ] Result recorded in `docs/release_candidate_report.md` as "10/10 deployed smoke".
- [ ] Railway logs spot-checked for one `ai_chat_success` line with the trace id from the run.

**Evidence / source**

- `AI_ROADMAP.md` §10 and §11 (Production AI Deployment State)
- `docs/ROADMAP_RECONCILIATION.md` §3 (launch-sufficient but not "done")
- `docs/release_candidate_report.md` lines covering the 9/9 deployed run

**Labels:** `ai`, `ops`, `verification`, `scope:S`, `launch-gate`

---

## 2. Add write-path E2E smoke suite (six tests)

**Problem statement**

Every main surface is exercised by read-path smoke only. Task
completion, grocery approve, weekly payout, meal-plan approve,
meal-review submit, and purchase-request convert all run through
backend unit tests but have zero UI-level verification. Any regression
in the write-path wiring in `scout-ui/` would escape CI.

**Acceptance criteria**

- [ ] `smoke-tests/tests/write-path.spec.ts` (or split across files) contains six tests:
  - [ ] Child completes a task with step-tracking.
  - [ ] Parent approves a pending grocery item.
  - [ ] Parent runs weekly payout and sees an earned-amount update.
  - [ ] Parent approves a weekly meal plan.
  - [ ] Parent or child submits a meal review.
  - [ ] Parent converts a purchase request into a grocery item.
- [ ] All six run against a seeded fresh database in CI and in local dev.
- [ ] Total Playwright count updated in `docs/release_candidate_report.md`.

**Evidence / source**

- `FRONTEND_ROADMAP.md` §12 (Smoke coverage)
- `docs/ROADMAP_RECONCILIATION.md` §2 (implemented but not strongly verified)

**Labels:** `frontend`, `verification`, `smoke-tests`, `scope:M`

---

## 3. Deepen AI panel smoke — content + tool round-trip + role variants

**Problem statement**

`smoke-tests/tests/ai-panel.spec.ts` only asserts "no 5xx and no error
banner." The test passes even if the assistant bubble is empty or the
response is a stock "I can't help right now." It covers the adult
personal surface only — no child, no parent, no confirmation, no
handoff deep-link.

**Acceptance criteria**

- [ ] Existing test is strengthened: assistant bubble contains non-empty text.
- [ ] New test: "Ask Scout to add a task" → asserts a `personal_task` handoff card renders → tap → asserts the new task appears on `/personal`.
- [ ] New test: child login → quick-action that would require a write tool → asserts a denial response and no crash.
- [ ] New test: parent-surface login → open ScoutPanel → asserts quick-actions render.
- [ ] New test (depends on #4): trigger a confirmation-required tool → asserts the panel surfaces a confirm affordance.

**Evidence / source**

- `AI_ROADMAP.md` §10 (Browser-Based AI Verification) and §5 (ScoutPanel Chat UX)
- `FRONTEND_ROADMAP.md` §10 (AI Panel UX and Handoff)

**Labels:** `ai`, `frontend`, `verification`, `scope:M`

---

## 4. Render confirmation-flow UI inside ScoutPanel

**Problem statement**

The backend marks 10 shared-write tools as confirmation-required
(`backend/app/ai/tools.py:35-47`). On the first call they return
`{confirmation_required: true, ...}`, expecting a second call with
`confirmed=true`. `ScoutLauncher.tsx` does not render any affordance for
this — users hit the gate, see nothing, and have to re-ask in plain
English. Shared-write tools effectively dead-end in the panel today.

**Acceptance criteria**

- [ ] `ScoutPanel` recognizes `result.confirmation_required` and renders a confirm + cancel affordance with the tool name + summary.
- [ ] Tapping confirm re-invokes `/api/ai/chat` with `confirmed: true`.
- [ ] Tapping cancel dismisses the affordance without firing the tool.
- [ ] Covered by the confirmation-round-trip sub-test in issue #3.

**Evidence / source**

- `AI_ROADMAP.md` §3 (Tool Registry / Confirmation / Audit) and §5
- `BACKEND_ROADMAP.md` §7 (AI Orchestration — confirmation-gated writes)

**Labels:** `ai`, `frontend`, `ux`, `scope:M`

---

## 5. Add global frontend error boundary

**Problem statement**

Expo Router / React Native Web does not use Next.js `error.tsx` /
`loading.tsx` conventions. A render crash anywhere in the tree produces
a blank screen with no recovery path.

**Acceptance criteria**

- [ ] `scout-ui/components/ErrorBoundary.tsx` exists and wraps `app/_layout.tsx`.
- [ ] Renders a "Something went wrong — reload?" fallback with a reload button.
- [ ] Playwright test forces a thrown error inside a surface and asserts the boundary fallback renders.
- [ ] Error is forwarded to the production error reporting provider (depends on issue #7).

**Evidence / source**

- `FRONTEND_ROADMAP.md` §11 (Loading / Empty / Error / Retry States)

**Labels:** `frontend`, `ux`, `reliability`, `scope:S`

---

## 6. ScoutPanel disabled-state handling

**Problem statement**

`ScoutLauncher.tsx` does not probe `/ready.ai_available` before opening
the chat modal. If the Anthropic API key is ever removed or rotated, the
user will hit a live 5xx on their first quick-action tap. The smoke
test gracefully skips in this state; the app does not.

**Acceptance criteria**

- [ ] `ScoutPanel.open()` (or the `_layout.tsx` wrapper) reads `/ready` and caches `ai_available`.
- [ ] If `ai_available === false`, the panel renders a "Scout AI is currently unavailable" state instead of the chat UI.
- [ ] Playwright test stubs `/ready` to return `ai_available: false` and asserts the disabled state.

**Evidence / source**

- `AI_ROADMAP.md` §5 (ScoutPanel Chat UX — gaps) and ledger item 11

**Labels:** `ai`, `frontend`, `reliability`, `scope:S`

---

## 7. Wire production error reporting (Sentry or equivalent)

**Problem statement**

Production JS errors in `scout-ui` are currently invisible. A broken
build on the Vercel side would be found only when a user reports it,
or indirectly via backend log noise.

**Acceptance criteria**

- [ ] Error provider configured in `scout-ui` with `dsn` via env var.
- [ ] Errors caught by the global error boundary (issue #5) report upstream.
- [ ] Unhandled promise rejections in the app also report.
- [ ] `docs/private_launch.md` documents the setup and env var.

**Evidence / source**

- `FRONTEND_ROADMAP.md` §13 (Deployment / Web Readiness) — gaps

**Labels:** `frontend`, `ops`, `reliability`, `scope:M`

---

## 8. Cover `meals/prep.tsx`, `meals/reviews.tsx`, and the weekly generation loop with smoke tests

**Problem statement**

`scout-ui/app/meals/prep.tsx` (122 lines) and `scout-ui/app/meals/reviews.tsx`
(417 lines) are real implementations with zero Playwright coverage.
The AI-driven weekly plan generation loop in `meals/this-week.tsx` is
also unsmoked.

**Acceptance criteria**

- [ ] Playwright loads `/meals/prep` and asserts either the "Sunday Prep" header or the no-plan empty state renders.
- [ ] Playwright loads `/meals/reviews` and asserts either the rating UI or the empty state renders.
- [ ] Playwright loads `/meals/this-week` after a plan exists in the seed and asserts the generation buttons render. (Does NOT drive a real AI generation — seed an approved plan instead.)

**Evidence / source**

- `FRONTEND_ROADMAP.md` §6 (Meals UX) and Unknowns list
- `AI_ROADMAP.md` §7 (Meal Generation Workflow)

**Labels:** `frontend`, `verification`, `smoke-tests`, `scope:S`

---

## 9. Wire `dietary_preferences` into the weekly meal plan generator

**Problem statement**

The `dietary_preferences` table exists (migration `005_meals.sql`) but
`backend/app/services/weekly_meal_plan_service.py` (790 lines) never
reads it. Families with real dietary restrictions get generic plans.

**Acceptance criteria**

- [ ] `weekly_meal_plan_service.build_context()` reads `dietary_preferences` rows for the target family.
- [ ] The generation prompt includes a "constraints" block describing allergies, dislikes, and diet labels.
- [ ] New test in `backend/tests/test_weekly_meal_plans.py` asserts that a plan generated for a family with `nut_allergy=true` does not surface nut-based staples.

**Evidence / source**

- `BACKEND_ROADMAP.md` §5 (Meals — gaps)
- `AI_ROADMAP.md` §7 (Meal Generation Workflow — gaps)

**Labels:** `backend`, `ai`, `scope:S`

---

## 10. Decide production behavior for dev-mode ingestion buttons

**Problem statement**

`scout-ui/app/personal/index.tsx` renders Google Calendar and YNAB
ingestion buttons behind a `DEV_MODE` flag. The flag has never been
validated against the production Vercel build — behavior is UNKNOWN.
A user clicking one in prod would fire a real ingestion request with
demo payloads.

**Acceptance criteria**

- [ ] Confirm current production behavior (visible or hidden).
- [ ] If visible, hide by default in prod builds.
- [ ] Playwright smoke test asserts the buttons are not rendered when `process.env.EXPO_PUBLIC_DEV_MODE !== "true"`.
- [ ] `docs/private_launch.md` documents the decision.

**Evidence / source**

- `FRONTEND_ROADMAP.md` §3 (Personal surface — missing UX/product work)
- `docs/ROADMAP_RECONCILIATION.md` §3

**Labels:** `frontend`, `ops`, `scope:S`, `launch-gate`
