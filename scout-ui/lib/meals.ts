/**
 * Meals helpers for Scout.
 *
 * useMealsConfig — aggregates the three family-level meals config keys into a
 * single composite result for easy consumption by meals screens and admin.
 *
 * Keys:
 *   meals.plan_rules      → planRules
 *   meals.rating_scale    → ratingScale
 *   meals.dietary_notes   → dietaryNotes
 */

import { useFamilyConfig } from "./config";

// ---------------------------------------------------------------------------
// Shape definitions
// ---------------------------------------------------------------------------

export interface MealsPlanRules {
  week_starts_on: "monday" | "sunday";
  dinners_per_week: number;
  batch_cook_day: string;
  generation_style: "balanced" | "kid-friendly" | "quick" | "ambitious";
}

export interface MealsRatingScale {
  max_rating: number;
  repeat_options: string[];
  require_notes_for_retire: boolean;
}

export interface MealsDietaryNotes {
  categories: string[];
}

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

export const DEFAULT_PLAN_RULES: MealsPlanRules = {
  week_starts_on: "monday",
  dinners_per_week: 7,
  batch_cook_day: "sunday",
  generation_style: "balanced",
};

export const DEFAULT_RATING_SCALE: MealsRatingScale = {
  max_rating: 5,
  repeat_options: ["repeat", "tweak", "retire"],
  require_notes_for_retire: false,
};

export const DEFAULT_DIETARY_NOTES: MealsDietaryNotes = {
  categories: [
    "No restrictions",
    "Vegetarian-lean",
    "No onions",
    "Dairy-free",
    "Gluten-free",
    "Nut-free",
  ],
};

// ---------------------------------------------------------------------------
// Composite hook
// ---------------------------------------------------------------------------

export interface UseMealsConfigResult {
  planRules: MealsPlanRules;
  ratingScale: MealsRatingScale;
  dietaryNotes: MealsDietaryNotes;
  /** True while any of the three keys are still loading */
  loading: boolean;
}

/**
 * Aggregates all three family-level meals config keys into one result.
 * Each key is fetched independently via useFamilyConfig; loading is true
 * until all three have resolved.
 */
export function useMealsConfig(): UseMealsConfigResult {
  const {
    value: planRules,
    loading: planLoading,
  } = useFamilyConfig<MealsPlanRules>("meals.plan_rules", DEFAULT_PLAN_RULES);

  const {
    value: ratingScale,
    loading: ratingLoading,
  } = useFamilyConfig<MealsRatingScale>("meals.rating_scale", DEFAULT_RATING_SCALE);

  const {
    value: dietaryNotes,
    loading: dietaryLoading,
  } = useFamilyConfig<MealsDietaryNotes>("meals.dietary_notes", DEFAULT_DIETARY_NOTES);

  return {
    planRules,
    ratingScale,
    dietaryNotes,
    loading: planLoading || ratingLoading || dietaryLoading,
  };
}
