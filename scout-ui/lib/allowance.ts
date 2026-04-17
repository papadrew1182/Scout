/**
 * Allowance helpers for Scout.
 *
 * useFamilyAllowanceTargets — fetches all active children and their
 * per-member allowance.target config in a single composite hook.
 *
 * Design: one GET /members + one GET /admin/config/members/allowance.target.
 * Two requests (not N+1) regardless of family size.  Results are joined
 * client-side by member_id.
 *
 * For the `earned` field we don't yet have a real payout ledger, so:
 *   earned = 0   (TODO: compute from daily_wins + payout ledger)
 *
 * This file is the single place that needs updating when the ledger lands.
 */

import { useCallback, useEffect, useState } from "react";
import { fetchAllMemberConfigForKey, fetchMembers } from "./api";
import type { FamilyMember } from "./types";

// Shape stored in member_config under key "allowance.target"
export interface AllowanceTarget {
  weekly_target_cents: number;
  baseline_cents: number;
  payout_schedule: "weekly" | "biweekly" | "monthly";
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
 * Fetches all active child members + their allowance.target config and joins
 * them into AllowanceRow[].  Non-child members are filtered out.
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
      fetchAllMemberConfigForKey("allowance.target"),
    ])
      .then(([members, configRows]) => {
        const kids = members.filter((m) => m.role === "child" && m.is_active);

        // Build a lookup map: member_id → config value
        const configMap = new Map<string, AllowanceTarget>();
        for (const row of configRows) {
          configMap.set(row.member_id, row.value as AllowanceTarget);
        }

        const assembled: AllowanceRow[] = kids.map((kid) => {
          const target = configMap.get(kid.id) ?? null;
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
