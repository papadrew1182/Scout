# Phase 1 Handoff - Interaction Contract + Dead-Tap Audit

**Branch:** `sprint/operability-phase-1-interaction-contract`
**Final commit:** see `git log --oneline sprint/operability-phase-1-interaction-contract ^main`
**Date:** 2026-04-19

---

## Migrations added

None. Phase 1 is frontend-only.

## Permission keys added

None.

## Tables / columns added

None.

## Endpoints added / modified / permission-gated

None. Phase 1 is frontend-only.

## Frontend files added

| File | Purpose |
|------|---------|
| `docs/architecture/interaction_contract.md` | Interaction contract spec (5 classes) |
| `scout-ui/app/(scout)/members/[id]/index.tsx` | Placeholder child master card route (Phase 3 stub) |
| `smoke-tests/tests/interaction-contract.spec.ts` | Playwright smoke tests for all tap-target classes |
| `docs/verification/scout_operability_verification_harness.md` | Verification harness (Phase 1 section) |

## Frontend files modified

| File | Change |
|------|--------|
| `docs/architecture/ARCHITECTURE.md` | Added interaction_contract.md to Canonical File Locations |
| `scripts/architecture-check.js` | Added Check 5 (dead-tap detection) with enforcement |
| `scout-ui/features/today/TodayHome.tsx` | Wired Daily Win pills to /members/{id} |
| `scout-ui/features/rewards/DailyWinCard.tsx` | Made card tappable, navigates to /members/{id}?tab=wins |
| `scout-ui/features/rewards/WeeklyPayoutCard.tsx` | Made card tappable, navigates to /members/{id}?tab=payout |
| `scout-ui/features/rewards/RewardsHome.tsx` | Made approval pill interactive for permissioned parents, documented footer no-op |
| `scout-ui/app/meals/this-week.tsx` | Added inline expand on meal day cells |
| `scout-ui/app/grocery/index.tsx` | Made item checkboxes functional (mark purchased) |
| `scout-ui/features/calendar/HouseholdBlocksPreview.tsx` | Made anchor block rows expandable inline |
| `scout-ui/features/calendar/CalendarPreview.tsx` | Wired health banner to /control-plane |
| `scout-ui/features/today/CompletionSheet.tsx` | Fixed menu-rollup defect (touch responder) |

## Smoke tests added

| File | Count | Coverage |
|------|-------|----------|
| `smoke-tests/tests/interaction-contract.spec.ts` | 7 tests | navigate-detail (3), execute-action (1), expand-inline (2), no-op-documented (1), plus CompletionSheet regression |

## Arch-check script output delta

| Check | Before | After |
|-------|--------|-------|
| Check 1: Backend missing permission | 65 WARN | 65 WARN (unchanged, pre-existing) |
| Check 2: Frontend missing gate | 0 WARN | 0 WARN |
| Check 3: seedData drift | 1 INFO | 1 INFO |
| Check 4: Permission key format | 0 WARN | 0 WARN |
| Check 5: Dead tap-target (NEW) | N/A | 0 WARN |

**Net change:** Zero new WARN findings. One new check (Check 5) added
and enforced with zero violations.

## Known follow-ups

- The 65 pre-existing Check 1 backend WARNs are from Known Gaps in
  ARCHITECTURE.md. Phase 2 will address several of these (personal_tasks,
  calendar, meals permission gating).
- The `/members/{id}` placeholder will be fully implemented in Phase 3
  (child master card with today's tasks, streak, scope contracts).
- The approval pill action panel on RewardsHome is a placeholder until
  the `allowance.run_payout` endpoint ships.
- seedData drift (Check 3 INFO) is tracked but not blocking.

## Narrative summary

Phase 1 established the interaction contract for Scout's frontend: a
project-wide rule that every tappable element belongs to one of five
defined interaction classes. The architecture-check script was extended
with Check 5 (dead-tap detection) in report-only mode, all dead taps
were fixed, and enforcement was enabled. Every dashboard card and row
across /today, /rewards, /meals, /grocery, /calendar, and /admin now
has a defined tap target per the sprint spec's Appendix A. A placeholder
/members/{id} route was added for Phase 3's child master card. The
CompletionSheet menu-rollup defect was fixed by claiming the touch
responder on the sheet's outer View. Seven Playwright smoke tests cover
all interaction classes plus a regression test for the sheet stability
fix.
