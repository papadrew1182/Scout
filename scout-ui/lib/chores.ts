/**
 * Chores helpers for Scout.
 *
 * useFamilyChoreRoutines — fetches all active children's per-member
 * chores.routines config plus the family-level chores.rules config in a
 * single composite hook.
 *
 * Design: one GET /members + one GET /admin/config/members/chores.routines
 * + one GET /admin/config/family pick of chores.rules.
 * Three requests (not N+1) regardless of family size.  Results are joined
 * client-side by member_id.
 */

import { useCallback, useEffect, useState } from "react";
import { fetchAllMemberConfigForKey, fetchFamilyConfigValue, fetchMembers } from "./api";
import type { FamilyMember } from "./types";

// ---------------------------------------------------------------------------
// Shapes
// ---------------------------------------------------------------------------

/** A single chore routine stored in member_config under "chores.routines" */
export interface ChoreRoutine {
  id: string;
  name: string;
  pts: number;
}

/** The config value stored under member_config key "chores.routines" */
export interface ChoresRoutinesConfig {
  routines: ChoreRoutine[];
}

/** Family-level rules stored in family_config under "chores.rules" */
export interface ChoresRules {
  streak_bonus_days: number;
  streak_bonus_pts: number;
  max_daily_pts: number;
  requires_check_off: boolean;
}

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

export const DEFAULT_CHORES_ROUTINES_CONFIG: ChoresRoutinesConfig = {
  routines: [],
};

export const DEFAULT_CHORES_RULES: ChoresRules = {
  streak_bonus_days: 7,
  streak_bonus_pts: 20,
  max_daily_pts: 100,
  requires_check_off: true,
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export interface UseFamilyChoreRoutinesResult {
  /** Map from memberId to that kid's routines array */
  routinesByMember: Record<string, ChoreRoutine[]>;
  /** Active child members (for iteration order) */
  members: FamilyMember[];
  rules: ChoresRules;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * Fetches all active child members + their chores.routines config + the
 * family chores.rules and assembles them into a unified result.
 */
export function useFamilyChoreRoutines(): UseFamilyChoreRoutinesResult {
  const [routinesByMember, setRoutinesByMember] = useState<Record<string, ChoreRoutine[]>>({});
  const [members, setMembers] = useState<FamilyMember[]>([]);
  const [rules, setRules] = useState<ChoresRules>(DEFAULT_CHORES_RULES);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const doFetch = useCallback(() => {
    setLoading(true);
    setError(null);

    Promise.all([
      fetchMembers(),
      fetchAllMemberConfigForKey("chores.routines"),
      fetchFamilyConfigValue<ChoresRules>("chores.rules"),
    ])
      .then(([allMembers, configRows, familyRules]) => {
        const kids = allMembers.filter((m) => m.role === "child" && m.is_active);

        // Build lookup: member_id → routines[]
        const byMember: Record<string, ChoreRoutine[]> = {};
        for (const row of configRows) {
          const cfg = row.value as ChoresRoutinesConfig;
          byMember[row.member_id] = Array.isArray(cfg?.routines) ? cfg.routines : [];
        }
        // Ensure every kid has an entry even if config is absent
        for (const kid of kids) {
          if (!(kid.id in byMember)) {
            byMember[kid.id] = [];
          }
        }

        setMembers(kids);
        setRoutinesByMember(byMember);
        setRules(familyRules ?? DEFAULT_CHORES_RULES);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load chore data");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [tick]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    doFetch();
  }, [doFetch]);

  const refresh = useCallback(() => setTick((t) => t + 1), []);

  return { routinesByMember, members, rules, loading, error, refresh };
}
