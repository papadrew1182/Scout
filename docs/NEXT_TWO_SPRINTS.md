# Scout — Next Two Sprints

Last built: 2026-04-13. Source: `docs/EXECUTION_BACKLOG.md`.

This document picks specific items off the ranked backlog and arranges
them into two executable sprints. It intentionally excludes items that
belong in "later / strategic" (Backlog Bucket 4) and items that need
investigation first (Backlog Bucket 5, except where the investigation
itself is sprinted).

## Sprint 1 — Close the verification gap

**Goal:** Turn private-launch-sufficient into strategically complete
for the highest-risk verification gaps. Everything here reduces
"regression could ship invisibly" risk or closes an UNKNOWN.

**Duration target:** 1 week

**Included items (in execution order):**

1. **Backlog #17, #18, #19 — Investigations (all three, parallel)**
   - Run `ai-panel.spec.ts` against the deployed URLs once.
   - Spot-check Railway logs for `ai_chat_*` lines.
   - Query `ai_tool_audit` for rows since 2026-04-12.
   - **Why first:** every other item in Sprint 1 depends on these
     answers. They take hours, not days.

2. **Backlog #1 — Deployed AI-panel smoke (promotes the result from #17)**
   - Record outcome in `docs/release_candidate_report.md` as "10/10
     deployed smoke" or as a documented failure with remediation.
   - **Scope:** S.

3. **Backlog #6 — ScoutPanel disabled-state handling**
   - Panel probes `/ready.ai_available` before mounting chat UI.
   - **Scope:** S.

4. **Backlog #16 — Dev-mode ingestion button prod-behavior audit**
   - Confirm prod behavior; hide if leaked; add a smoke assertion.
   - **Scope:** S.

5. **Backlog #5 — Global frontend error boundary**
   - Single top-level `ErrorBoundary` in `_layout.tsx`.
   - **Scope:** S.

6. **Backlog #2 — Write-path E2E smoke suite (six tests)**
   - Task complete, grocery approve, weekly payout, meal-plan approve,
     meal-review submit, purchase-request convert.
   - **Scope:** M. This is the sprint's centerpiece.

7. **Backlog #8 — Meals `prep.tsx` + `reviews.tsx` + generation-loop smoke**
   - Three lightweight Playwright tests.
   - **Scope:** S.

8. **Backlog #3 — AI panel verification depth**
   - Content assertions + tool round-trip + child denial + parent
     variant + confirmation round-trip (depends on #4 landing).
   - **Scope:** M.

9. **Backlog #4 — Confirmation-flow UI inside ScoutPanel**
   - Renders confirm/cancel affordance when
     `result.confirmation_required` is true.
   - **Scope:** M. Sequence note: #4 lands before #3's confirmation
     sub-test.

**Explicitly excluded from Sprint 1:**

- AI streaming (#10) — too large; starts Sprint 2.
- Provider retry (#9) — paired with streaming in Sprint 2.
- Bonus / penalty payout (#15) — not a verification gap; Sprint 2.
- `dietary_preferences` wiring (#11) — not launch-risk; Sprint 2.
- Production error reporting (#7) — Sprint 2. Rationale: Sprint 1's
  error boundary is the precondition; adding a provider on top belongs
  in the sprint that ships it end-to-end.
- Real integrations layer (#22) — strategic; not this sprint, not
  Sprint 2.
- Cost / latency observability (#13) — Sprint 2 tail.

**Definition of done for Sprint 1:**

- Every Bucket 1 item (1.1, 1.2, 1.3) is VERIFIED (not just
  IMPLEMENTED).
- Playwright suite grows from ~13 to ~22 tests (original 13 + 6
  write-path + 3 meals smoke = 22, give or take).
- AI panel smoke has at least one content assertion and at least one
  tool round-trip.
- The 10 confirmation-required AI tools can be completed end-to-end
  through the ScoutPanel.
- Deploy drift for AI is visible (Backlog #14 may or may not ship in
  this sprint; if not, deferred to Sprint 2).
- `docs/release_candidate_report.md` updated with the new test counts
  and a note about the deployed AI-panel run.
- At least three Bucket 5 UNKNOWNs are resolved in writing.

---

## Sprint 2 — Strategic completion + product polish

**Goal:** Convert launch-sufficient AI and launch-sufficient payout
into strategically complete. Add the polish that pays off measurably
once users are living in the product.

**Duration target:** 1–2 weeks (Sprint 2 is larger; streaming alone is L).

**Included items (in execution order):**

1. **Backlog #9 — Provider retry / fallback on upstream 5xx**
   - Pre-req for streaming to be robust.
   - **Scope:** S.

2. **Backlog #10 — AI streaming response pipeline**
   - SSE endpoint + client incremental render + typing indicator.
   - Biggest perceived-latency win in the product.
   - **Scope:** L.

3. **Backlog #11 — `dietary_preferences` → weekly meal plan generator**
   - Unblocks any family with real dietary restrictions.
   - **Scope:** S.

4. **Backlog #15 — Bonus / penalty parent payout endpoint + UI wiring**
   - Eliminates the two visible stub buttons on the parent payout card.
   - Includes migration `014_allowance_adjustments.sql`.
   - **Scope:** M.

5. **Backlog #7 — Production error reporting (Sentry-equivalent)**
   - Builds on Sprint 1's global error boundary.
   - **Scope:** M.

6. **Backlog #13 — Cost / latency observability for AI**
   - Structured log format + a minimal aggregation script.
   - Lays groundwork for dashboards later.
   - **Scope:** M.

7. **Backlog #14 — AI deploy drift watchdog**
   - Full Playwright smoke runs against deployed URLs in CI.
   - **Scope:** S.

8. **Backlog #12 — Scheduled daily brief delivery**
   - Morning brief as a `parent_action_item`.
   - Highest engagement lever outside of streaming.
   - **Scope:** M.

9. **Backlog #20 — RexOS / Exxir product decision + execution**
   - Product decision recorded in `ROADMAP_RECONCILIATION.md`;
     code change either builds the feature, removes it, or relabels.
   - **Scope:** S for decision; variable for execution.

**Explicitly excluded from Sprint 2:**

- Real integrations layer (#22) — still strategic; needs its own
  multi-sprint planning.
- Multi-instance rate limiter (#23) — blocker only on horizontal
  scale-out.
- Conversation resume in ScoutPanel (#25) — post-streaming polish.
- Notification delivery channel (#21) — deferred until integrations
  layer work decides the transport.
- Prompt caching — low value at current volume.
- Bundle-size CI gate, accessibility audit, offline/PWA, skeleton
  loaders, multi-member session switching — all Bucket 4 polish; none
  of them change the product's daily value in Sprint 2.

**Definition of done for Sprint 2:**

- Streaming ScoutPanel in production behind a feature flag.
- Provider retry measurable in a test with a mocked 5xx.
- `dietary_preferences` verifiably applied to a generated plan.
- Bonus / penalty adjustments land on the `allowance_ledger` and show
  up in the parent payout card.
- Any error thrown in production surfaces in the error-reporting
  provider within one minute.
- AI latency + token usage visible in structured logs and aggregated
  per family by a script.
- Deployed smoke runs the full Playwright suite in CI after every
  deploy and records the result in
  `docs/release_candidate_report.md`.
- Morning brief lands in the Action Inbox on a schedule.
- No visible stubs remain on the parent dashboard (bonus/penalty
  wired, RexOS/Exxir decided).
