/**
 * Product constants for Scout.
 *
 * Payout tiers, meal ordering, and calculation helpers.
 * Allowance baselines are per-child product config — they live here
 * temporarily. When the backend stores per-member allowance rates,
 * these will be replaced by API data.
 */

/** Allowance baselines in cents, keyed by child first_name. */
export const BASELINES: Record<string, number> = {
  Sadie: 1200,
  Townes: 900,
  River: 700,
};

/** Payout percentage by number of daily wins (Mon-Fri). */
export const PAYOUT_TIERS: Record<number, number> = {
  5: 100,
  4: 80,
  3: 60,
  2: 0,
  1: 0,
  0: 0,
};

/** Sort order for meal types. */
export const MEAL_ORDER: Record<string, number> = {
  breakfast: 1,
  lunch: 2,
  dinner: 3,
  snack: 4,
};

/** Calculate payout amount in cents. */
export function calculatePayout(
  childName: string,
  winCount: number
): { baseline: number; pct: number; amountCents: number } {
  const baseline = BASELINES[childName] ?? 0;
  const pct = PAYOUT_TIERS[winCount] ?? 0;
  const amountCents = Math.round(baseline * (pct / 100));
  return { baseline, pct, amountCents };
}

/** Sort meals by type order. */
export function sortMealsByType<T extends { meal_type: string }>(meals: T[]): T[] {
  return [...meals].sort(
    (a, b) => (MEAL_ORDER[a.meal_type] ?? 9) - (MEAL_ORDER[b.meal_type] ?? 9)
  );
}
