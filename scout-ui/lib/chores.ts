/**
 * Chores helpers for Scout.
 *
 * useFamilyChoreRoutines — fetches all active children's per-member
 * chore routines from the canonical 022 tables via
 * GET /admin/chores/routines (Migration 036).
 *
 * Design: one GET /admin/chores/routines (returns all members grouped) +
 * one GET /admin/config/family pick of chores.rules.
 * Two requests regardless of family size.  Results are keyed by member_id.
 */

import { useCallback, useEffect, useState } from "react";
import { fetchChoreRoutines, fetchFamilyConfigValue, fetchMembers } from "./api";
import type { MemberRoutinesGroup, RoutineItem } from "./api";
import type { FamilyMember } from "./types";

// ---------------------------------------------------------------------------
// Shapes
// ---------------------------------------------------------------------------

/**
 * A single chore routine as returned by the canonical API.
 * Re-exported from api.ts for consumer convenience; the `id` field is the
 * database UUID, and `routine_key` is the stable programmatic key.
 */
export type ChoreRoutine = RoutineItem;

/**
 * Legacy config-shape alias kept for any existing consumers that still
 * reference ChoresRoutinesConfig.  The `routines` array now holds
 * RoutineItem objects from the canonical API.
 */
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
 * Fetches chore routines from the canonical 022 tables via
 * GET /admin/chores/routines (Migration 036) plus the family chores.rules.
 *
 * Returns routines keyed by owner_family_member_id so callers don't need
 * to change their rendering logic.
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
      fetchChoreRoutines(),
      fetchFamilyConfigValue<ChoresRules>("chores.rules"),
    ])
      .then(([allMembers, groups, familyRules]) => {
        const kids = allMembers.filter((m) => m.role === "child" && m.is_active);

        // Build lookup: member_id → routines[] from canonical API groups
        const byMember: Record<string, ChoreRoutine[]> = {};
        for (const group of groups) {
          if (group.member_id) {
            byMember[group.member_id] = group.routines;
          }
        }
        // Ensure every kid has an entry even if no routines have been migrated yet
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
