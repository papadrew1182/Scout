/**
 * Quick-action suggestions shown above the Scout chat composer,
 * keyed by surface. These are static UX suggestions, not live AI
 * output. The historical SAMPLE_THREAD / mockScoutResponse / keyword
 * reply fixtures were removed in PR #39 (real AI resume shipped) and
 * this Batch-1 PR 2 cleanup (dead export removal).
 */

export type ScoutSurface =
  | "dashboard"
  | "personal"
  | "parent"
  | "meals"
  | "grocery"
  | "child"
  | "settings";

export const QUICK_ACTIONS_BY_SURFACE: Record<ScoutSurface, string[]> = {
  dashboard: ["Remind River about chores", "Approve paper towels", "Check next week's meals"],
  personal:  ["Add a task", "New note", "View full calendar"],
  parent:    ["Nudge River + Tyler", "Open morning brief", "Award Townes bonus pts"],
  meals:     ["Build grocery list from plan", "Edit tonight's dinner", "View last week's ratings"],
  grocery:   ["Clear all checked items", "Add eggs to list", "Share list with Sally"],
  child:     ["Help me with math homework", "What's for dinner tonight?", "How close am I to a reward?"],
  settings:  ["Add family member", "Change chore schedule", "Reconnect YNAB"],
};
