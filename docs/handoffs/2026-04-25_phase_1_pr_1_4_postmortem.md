# Postmortem - PR 1.3 Tier 5 drop-order bug (fixed in PR 1.4)

**Date:** 2026-04-25
**Severity:** Production deploy failure on the Phase 1 closing PR
**Detection:** Self-detected by direct DB query after the merge deploy didn't surface 057 in `_scout_migrations`
**Resolution:** PR 1.4 follow-up (this PR), in-place edit of migration 057
**Fix complexity:** 2-line SQL swap + comment updates; the systemic fix is a gate-scope rule change

## Summary

PR #73-#75 (Phase 1 PRs 1.1-1.3) shipped clean review-and-test artifacts; PR 1.3's migration `057_phase1_drop_public_legacy.sql` merged with arch-check green, frontend-types green, the documented backend-tests blast radius, and successful pre-push intra-tier independence checks on Tiers 1 and 2. On apply against Railway, migration 057 raised `psycopg2.errors.DependentObjectsStillExist: cannot drop table families because other objects depend on it`, the migration's `BEGIN/COMMIT` transaction rolled back atomically, and the new container failed to start.

Production was offline for the duration of the maintenance window (acceptable per v5.1 §4); database state was preserved bit-perfectly per atomic rollback. No data loss, no schema drift. The bug was a missed intra-tier FK in Tier 5, which is a single-line code fix; the underlying error was a too-narrow scope on the pre-push verification gate, which is the part worth changing for the rest of the sprint.

## Bug

**Symptom:** Migration 057 raised `cannot drop table families because other objects depend on it (DETAIL: constraint family_members_family_id_fkey on table family_members depends on table families)` at the `DROP TABLE IF EXISTS public.families;` statement in Tier 5.

**Root cause:** `public.family_members` holds an FK to `public.families` (`family_members_family_id_fkey`, ON DELETE CASCADE). Both tables are in PR 1.3's Tier 5. The migration as merged ordered Tier 5 alphabetically: `families` first, `family_members` second. PG's `DROP TABLE` blocks while any FK references the target regardless of `ON DELETE` clause, so dropping `families` first (while `family_members` still exists with the FK) fails. Plan forbids `CASCADE`. Transaction rolled back; nothing landed.

**Fix (proximate):** swap the two `DROP TABLE` lines in Tier 5 so `family_members` (the FK source) drops first, taking its FK with it; then `families` drops with no incoming references. Identical to the source-side-first rule already documented for Step A's Tier 1 mutual FK breaker - here applied via drop order rather than an explicit FK drop because the FK is single-direction (no mutual loop).

## What the gate missed

PR 1.3 scope review introduced an "intra-tier independence check" as a post-SQL verification gate after the SQL was first drafted. The gate enumerates every public->public FK with both endpoints inside a single tier and lets the migration author handle each case explicitly (drop the FK in Step A for mutual pairs; reorder within the tier for single-direction FKs; ignore self-FKs).

That gate caught a real bug in Step A's mutual breaker direction in the very same scope review (PR 1.3 first draft had the FK on the alphabetically-earlier side, which crashed Tier 1 by the same mechanism that ended up crashing Tier 5; the mutual breaker was swapped to the alphabetically-later side before push).

But the gate was scoped to **Tier 1 and Tier 2 only**, named explicitly in the gate spec. Tier 4 (2 tables) and Tier 5 (2 tables) were not run through the gate. Tier 3 has 1 table so is trivially clean. The gate's logic is correct; its scope was a subset.

**The naming was the bug.** Andrew's gate-spec text in the scope review called out "Tier 1 internal FKs" and "Tier 2 internal FKs" specifically. Code did not generalize "this should run on every multi-table tier" and instead ran exactly the two named tiers. Tier 5's intra-tier FK was therefore never checked.

## Empirical sweep - all 5 tiers (the gate that should have run pre-push)

Run against `docs/plans/_snapshots/2026-04-22_pre_rewrite_full.sql`, filtered by tier:

| Tier | Tables | Intra-tier FKs found | Disposition |
|---|---|---|---|
| **1** | 27 | 2 - `grocery_items.fk_grocery_items_purchase_request -> purchase_requests` (mutual) and `purchase_requests.purchase_requests_linked_grocery_item_id_fkey -> grocery_items` (mutual) | Mutual breaker on alphabetically-later side dropped in Step A (correct as shipped) |
| **2** | 7 | 1 - `events.events_recurrence_parent_id_fkey -> events` (self-FK) | Safe; PG handles self-FKs at DROP TABLE time |
| **3** | 1 | 0 | Trivially clean (single table) |
| **4** | 2 | **0** | Empirically clean - chore_templates and routines do not reference each other |
| **5** | 2 | **1 - `family_members.family_members_family_id_fkey -> families` (single-direction)** | **The bug.** Source-side-first ordering: `family_members` must drop before `families`. Fixed in this PR. |

This sweep is now part of the standing pre-push verification. Going forward (sprint-wide rule, below), this table is reproduced in the handoff of every destructive migration PR.

## Gate-scope rule (sprint-wide, going forward)

**Intra-tier independence check applies to every multi-table tier in any destructive PR. Single-table tiers are trivially clean. Multi-table tiers require explicit FK enumeration before push, not after.**

Concretely:

- For any migration that drops or modifies multiple tables in topological tiers, every tier with `>1` table is checked.
- The output table from the empirical sweep (Tier / # tables / intra-tier FKs found / disposition) is included in the pre-push verification output and the handoff.
- The gate's PASS criterion is: every intra-tier FK is either (a) handled by an explicit ALTER TABLE DROP CONSTRAINT in Step A, (b) resolved by within-tier ordering documented in the migration comments, or (c) determined to be a self-FK and noted as safe.
- The handoff's test plan explicitly cites the sweep ran on every multi-table tier, naming each tier examined.

This rule is a strict superset of the original PR 1.3 gate spec ("Tier 1 + Tier 2"). All future destructive PRs in this sprint follow it.

## Process notes

**What worked:**

- **Atomic transaction.** The migration's `BEGIN/COMMIT` ensured the failed `DROP TABLE families` rolled back everything else: Step A's 4 FK drops, Tiers 1-4's 37 table drops, all reverted. DB state ended bit-identical to pre-057. Verified by 4 direct DB queries (BASE TABLE count, BASE TABLE list, `_scout_migrations` top, FK constraint existence in `pg_constraint`).
- **`IF EXISTS` idempotency.** A retry of 057 (with the fix) on the same DB is safe; the fixed version starts from the same pre-057 state and proceeds cleanly.
- **The post-SQL gate concept.** The gate, on the tiers it covered, caught a real bug (Tier 1's mutual breaker direction). The same gate, applied to all multi-table tiers, would have caught this bug too.
- **Direct DB verification before fix work.** Trusting the error message ("cannot drop families") plus inferring "transaction rolled back, DB is clean" would have been wrong if the rollback had been partial. Running 4 explicit queries against `pg_constraint`, `_scout_migrations`, and `information_schema.tables` confirmed exact state before any further action.

**What didn't work:**

- **Gate scope was named, not generalized.** Naming "Tier 1 + Tier 2" in the gate spec implicitly excluded Tier 4 and Tier 5. The author (Andrew) acknowledges the gate-spec naming was the proximate cause; the executor (Code) acknowledges not generalizing was the secondary cause. Both corrections land in the forward rule above.
- **Inferring Tier-clean from "small enough to eyeball."** Code's PR 1.3 verification noted Tier 4 (2 tables) and Tier 5 (2 tables) as "verified during scope review's Gate 1 check" - but Gate 1 was about non-drop-set incoming FKs, not intra-tier ones. The intra-tier gate was simply not run on those tiers. The forward rule's "explicit FK enumeration" language is intentional: no eyeballing.

**Detection signal:**

The first signal something was wrong was the deploy log not surfacing `Applied 057_phase1_drop_public_legacy.sql` after a 10-minute polling window. The poller's filter included that exact string plus failure markers; absence of either was ambiguous (deploy could be slow, build could be retrying, etc.). Resolving the ambiguity required dropping to direct DB query, which surfaced the truth in seconds. **Future signal sharpening:** the poller's filter should also include `ERROR applying [0-9_]+\.sql` (the exact line migrate.py emits on raise), so a failed apply is caught as positively as a successful apply.

## What's deployed

- **Production:** offline (502 on `/health` and `/ready`). Maintenance window per v5.1 §4. Stays offline until PR 1.4 fix applies cleanly.
- **Database:** unchanged from end-of-PR-1.2 state. Confirmed by 4 queries.
- **Repo:** branch `sprint/phase-1-pr-1-3-drop-public-legacy` merged to main as commit `3acc328` (PR #75); this postmortem and the fix PR are on `sprint/phase-1-pr-1-4-fix-tier-5-drop-order`.

## Phase 1 status

Phase 1 stays open until the fix in PR 1.4 merges and applies cleanly. ChatGPT tertiary review of the full Phase 1 arc happens after Phase 1 actually closes (per Andrew's standing instruction).

The arc submitted to ChatGPT will include this postmortem alongside the four PR handoffs (1.1, 1.2, 1.3, 1.4). The postmortem is part of the Phase 1 record, not a footnote.
