/**
 * Allowance helpers for Scout.
 *
 * useFamilyAllowanceTargets — fetches all active children and their
 * per-member allowance targets from the canonical 022 tables via
 * GET /admin/allowance/policies (Migration 037).
 *
 * Design: one GET /members + one GET /admin/allowance/policies.
 * Two requests regardless of family size.  Results are joined
 * client-side by family_member_id.
 *
 * For the `earned` field we don't yet have a real payout ledger, so:
 *   earned = 0   (TODO: compute from daily_wins + payout ledger)
 *
 * This file is the single place that needs updating when the ledger lands.
 */

import { useCallback, useEffect, useState } from "react";
import { fetchAllowancePolicies, fetchMembers } from "./api";
import type { RewardPolicyItem } from "./api";
import type { FamilyMember } from "./types";

/**
 * Allowance target shape — mirrors what the canonical reward_policies API
 * returns (via RewardPolicyItem.payout_schedule) in a flattened form that
 * matches the existing consumer contract so no render code needs to change.
 */
export interface AllowanceTarget {
  weekly_target_cents: number;
  baseline_cents: number;
  payout_schedule: "weekly" | "biweekly" | "monthly";
}

/** Map a canonical RewardPolicyItem to the AllowanceTarget shape. */
function policyToTarget(policy: RewardPolicyItem): AllowanceTarget {
  const sched = policy.payout_schedule ?? {};
  return {
    baseline_cents: policy.baseline_amount_cents,
    weekly_target_cents: (sched as any).weekly_target_cents ?? 0,
    payout_schedule: ((sched as any).schedule ?? "weekly") as AllowanceTarget["payout_schedule"],
  };
}

// What the parent page (and any other consumer) needs per kid
export interface AllowanceRow {
  member: FamilyMember;
  /** Dollars earned this week — placeholder 0 until ledger is built */
  earned: number;
  /** Max dollars this week (weekly_target_cents / 100) */
  max: number;
  /** Underlying config record; null if not yet seeded */
  target: AllowanceTarget | null;
}

export interface UseFamilyAllowanceTargetsResult {
  rows: AllowanceRow[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

export const DEFAULT_ALLOWANCE_TARGET: AllowanceTarget = {
  weekly_target_cents: 0,
  baseline_cents: 0,
  payout_schedule: "weekly",
};

/**
 * Fetches all active child members + their reward policies from the canonical
 * 022 tables (GET /admin/allowance/policies, Migration 037) and joins them
 * into AllowanceRow[]. Non-child members are filtered out.
 */
export function useFamilyAllowanceTargets(): UseFamilyAllowanceTargetsResult {
  const [rows, setRows] = useState<AllowanceRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const doFetch = useCallback(() => {
    setLoading(true);
    setError(null);

    Promise.all([
      fetchMembers(),
      fetchAllowancePolicies(),
    ])
      .then(([members, policies]) => {
        const kids = members.filter((m) => m.role === "child" && m.is_active);

        // Build a lookup map: family_member_id → most-recent policy
        // (API already returns active policies, so first match wins)
        const policyMap = new Map<string, AllowanceTarget>();
        for (const policy of policies) {
          if (policy.family_member_id && !policyMap.has(policy.family_member_id)) {
            policyMap.set(policy.family_member_id, policyToTarget(policy));
          }
        }

        const assembled: AllowanceRow[] = kids.map((kid) => {
          const target = policyMap.get(kid.id) ?? null;
          const max = target ? target.weekly_target_cents / 100 : 0;
          return {
            member: kid,
            earned: 0, // TODO: compute from daily_wins + payout ledger
            max,
            target,
          };
        });

        setRows(assembled);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load allowance data");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [tick]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    doFetch();
  }, [doFetch]);

  const refresh = useCallback(() => setTick((t) => t + 1), []);

  return { rows, loading, error, refresh };
}
