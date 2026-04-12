/**
 * Shared loaders for the Meals pages.
 *
 * Single source of truth for "the current weekly meal plan" so
 * This Week, Prep Plan, Groceries, and Reviews all render from the
 * same saved backend object instead of duplicating fetch logic.
 */
import { useCallback, useEffect, useState } from "react";

import { fetchCurrentWeeklyPlan } from "./api";
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

    fetchCurrentWeeklyPlan()
      .then((data) => {
        if (!cancelled) setPlan(data);
      })
      .catch((e) => {
        if (!cancelled) {
          // 404 = no plan yet
          if (e.message?.includes("Failed to fetch")) {
            setNotFound(true);
          } else {
            setError(e.message ?? "Failed to load");
          }
        }
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
