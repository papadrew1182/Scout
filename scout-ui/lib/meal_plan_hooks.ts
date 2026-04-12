/**
 * Shared loaders for the Meals pages.
 *
 * Single source of truth for "the current weekly meal plan" so
 * This Week, Prep Plan, Groceries, and Reviews all render from the
 * same saved backend object instead of duplicating fetch logic.
 */
import { useCallback, useEffect, useState } from "react";

import { API_BASE_URL, CURRENT_USER_ID, FAMILY_ID } from "./config";
import type { WeeklyMealPlan } from "./types";

interface CurrentPlanState {
  plan: WeeklyMealPlan | null;
  loading: boolean;
  notFound: boolean;
  error: string | null;
  reload: () => void;
}

export function useCurrentWeeklyPlan(): CurrentPlanState {
  const [plan, setPlan] = useState<WeeklyMealPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setNotFound(false);

    fetch(`${API_BASE_URL}/families/${FAMILY_ID}/meals/weekly/current?member_id=${CURRENT_USER_ID}`)
      .then(async (r) => {
        if (r.status === 404) {
          if (!cancelled) setNotFound(true);
          return null;
        }
        if (!r.ok) {
          const text = await r.text().catch(() => "");
          throw new Error(text || `status ${r.status}`);
        }
        return r.json();
      })
      .then((data) => {
        if (!cancelled && data) setPlan(data as WeeklyMealPlan);
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
  }, [tick]);

  return { plan, loading, notFound, error, reload };
}

export const WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"] as const;

export function formatWeekStart(weekStart: string): string {
  const d = new Date(weekStart + "T00:00:00");
  return d.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" });
}
