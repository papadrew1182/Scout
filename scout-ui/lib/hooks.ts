/**
 * Lightweight shared data-loading hooks for Scout.
 *
 * Not a state management library. Just reusable fetch lifecycles
 * to normalize loading / error / empty / reload across surfaces.
 */

import { useCallback, useEffect, useState } from "react";
import { fetchMembers } from "./api";
import type { FamilyMember } from "./types";

// ---- Generic async data hook ----

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/**
 * Fetches data on mount and provides loading/error/reload state.
 * Re-runs when `deps` change.
 */
export function useAsync<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = []
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetcher()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message ?? "Failed to load");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, ...deps]);

  return { data, loading, error, reload };
}

// ---- Family members hook ----

interface FamilyMembersState {
  adults: FamilyMember[];
  children: FamilyMember[];
  all: FamilyMember[];
  loading: boolean;
  error: string | null;
}

/**
 * Fetches and categorizes family members on mount.
 * Returns adults and children separately.
 */
export function useFamilyMembers(): FamilyMembersState {
  const { data, loading, error } = useAsync(() => fetchMembers(), []);

  const all = data ?? [];
  const adults = all.filter((m) => m.role === "adult" && m.is_active);
  const children = all.filter((m) => m.role === "child" && m.is_active);

  return { adults, children, all, loading, error };
}
