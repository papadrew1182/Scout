/**
 * Mock Scout AI for the redesign demo. Returns canned responses
 * keyed off prompt keywords. Replace with real Anthropic calls
 * when the redesign moves past mockup stage.
 */

interface ScoutTurn {
  user: string;
  assistant: string;
}

const KEYWORD_REPLIES: Array<{ match: RegExp; reply: string }> = [
  { match: /dinner|tonight|stir fry/i, reply: "Stir fry tonight! Townes already set the table. You have all ingredients." },
  { match: /chore|behind|nudge/i,      reply: "River (0/3) and Tyler (2/4) are still behind. Want me to send a nudge?" },
  { match: /paper towel|approve/i,     reply: "Done — added to the Tom Thumb list." },
  { match: /grocery|costco/i,          reply: "8 items: ground turkey, salmon, broccoli, tortillas, olive oil, spinach, bell peppers, rotisserie chicken." },
  { match: /points|how many/i,         reply: "840 points — you're #1 in the family this week. 160 more to unlock the next reward." },
  { match: /bill|mortgage/i,           reply: "$4,820 due Apr 18 — 3 days away. Want a reminder set?" },
  { match: /meal plan|next week/i,     reply: "Drafted next week's plan based on Sally's prefs and Costco deals. Want to review it?" },
  { match: /ynab|reauth/i,             reply: "YNAB needs re-authentication. Tap 'Needs reauth' — takes about 30 seconds." },
];

const FALLBACK = "I'm a mock right now — wire me to the real Scout backend to get real answers.";

export async function mockScoutResponse(prompt: string): Promise<string> {
  await new Promise((r) => setTimeout(r, 350));
  const hit = KEYWORD_REPLIES.find((k) => k.match.test(prompt));
  return hit ? hit.reply : FALLBACK;
}

export const SAMPLE_THREAD: ScoutTurn[] = [
  { user: "What's for dinner tonight?", assistant: "Stir fry! Townes already set the table. You have all ingredients." },
  { user: "Who hasn't done chores?",    assistant: "River (0/3) and Tyler (2/4) are still behind. Want me to send a nudge?" },
];

export const QUICK_ACTIONS_BY_SURFACE: Record<string, string[]> = {
  dashboard: ["Remind River about chores", "Approve paper towels", "Check next week's meals"],
  personal:  ["Add a task", "New note", "View full calendar"],
  parent:    ["Nudge River + Tyler", "Open morning brief", "Award Townes bonus pts"],
  meals:     ["Build grocery list from plan", "Edit tonight's dinner", "View last week's ratings"],
  grocery:   ["Clear all checked items", "Add eggs to list", "Share list with Sally"],
  child:     ["Help me with math homework", "What's for dinner tonight?", "How close am I to a reward?"],
  settings:  ["Add family member", "Change chore schedule", "Reconnect YNAB"],
};
