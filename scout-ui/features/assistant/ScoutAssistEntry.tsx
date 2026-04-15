/**
 * ScoutAssistEntry — Session 3 Block 3 thin assist starter.
 *
 * Lightweight launcher that answers a small set of pre-canned
 * household-status questions LOCALLY by reading the AppContext slices
 * that are already loaded for Today / Rewards / Calendar / Control
 * Plane. No new AI dependency, no new network call, no backend
 * mutation.
 *
 * The five chips:
 *   - What is due next?
 *   - Who is late?
 *   - Am I on track for a Daily Win?
 *   - What will Hearth show tonight?
 *   - What needs parent attention?
 *
 * Each chip computes its answer from existing state and renders it as
 * an inline AnswerCard. Tap again to collapse.
 *
 * The surface is intentionally a thin starter — when a real assistant
 * backend lands later in the lane, the chips can route to it instead
 * of running locally, with no other UI changes.
 */

import { Pressable, StyleSheet, Text, View } from "react-native";

import { CalendarExport } from "../lib/contracts";
import {
  useCalendarExports,
  useConnectorsHealth,
  useControlPlaneSummary,
  useFamilyContext,
  useHouseholdToday,
  useIsParent,
  useMe,
  useRewardsWeek,
} from "../hooks";
import { useRouter } from "expo-router";
import { colors } from "../../lib/styles";
import { formatTime } from "../lib/formatters";
import {
  ChipId,
  CHIPS,
  SuggestionChips,
  useChipSelection,
} from "./SuggestionChips";
import { NotificationPreferences } from "../notifications/NotificationPreferences";
import { ActionCenter } from "../notifications/ActionCenter";

export function ScoutAssistEntry() {
  const me = useMe();
  const family = useFamilyContext();
  const today = useHouseholdToday();
  const rewards = useRewardsWeek();
  const calendar = useCalendarExports();
  const health = useConnectorsHealth();
  const summary = useControlPlaneSummary();
  const isParent = useIsParent();

  const { selected, setSelected } = useChipSelection();

  return (
    <View>
      <Text style={styles.eyebrow}>Scout assist</Text>
      <Text style={styles.title}>Ask, suggest, intervene</Text>
      <Text style={styles.subtle}>
        Tap a question. Scout answers from what it can already see — no
        AI roundtrip yet.
      </Text>

      <SuggestionChips selected={selected} onSelect={setSelected} />

      {selected && <AnswerCard chipId={selected} ctx={{ me, family, today, rewards, calendar, health, summary, isParent }} />}

      <ActionCenter />

      <NotificationPreferences />

      <Text style={styles.footnote}>
        Scout owns chores, routines, completion, and Daily Wins. Hearth
        is display only. Greenlight is the payout rail. This surface
        will route to a real assistant later in the lane — local
        computation is the starter.
      </Text>
    </View>
  );
}

// ---------------------------------------------------------------------------
// AnswerCard — runs the selected chip's local computation.
// ---------------------------------------------------------------------------

interface AnswerContext {
  me: ReturnType<typeof useMe>;
  family: ReturnType<typeof useFamilyContext>;
  today: ReturnType<typeof useHouseholdToday>;
  rewards: ReturnType<typeof useRewardsWeek>;
  calendar: ReturnType<typeof useCalendarExports>;
  health: ReturnType<typeof useConnectorsHealth>;
  summary: ReturnType<typeof useControlPlaneSummary>;
  isParent: boolean;
}

function AnswerCard({ chipId, ctx }: { chipId: ChipId; ctx: AnswerContext }) {
  const router = useRouter();
  const chip = CHIPS.find((c) => c.id === chipId)!;
  const { lines, deepLink } = computeAnswer(chipId, ctx);

  return (
    <View style={styles.answer}>
      <Text style={styles.answerLabel}>{chip.label}</Text>
      {lines.length === 0 ? (
        <Text style={styles.answerEmpty}>
          Nothing to surface yet — try again later.
        </Text>
      ) : (
        lines.map((l, i) => (
          <View key={i} style={styles.answerRow}>
            <Text style={styles.answerBullet}>·</Text>
            <Text style={styles.answerLine}>{l}</Text>
          </View>
        ))
      )}
      {deepLink && (
        <Pressable
          style={styles.deepLink}
          onPress={() => router.push(deepLink as any)}
          accessibilityRole="link"
          accessibilityLabel={`Open ${deepLink}`}
        >
          <Text style={styles.deepLinkText}>Open ↗</Text>
        </Pressable>
      )}
    </View>
  );
}

interface AnswerResult {
  lines: string[];
  deepLink?: string;
}

function computeAnswer(chipId: ChipId, ctx: AnswerContext): AnswerResult {
  switch (chipId) {
    case "due_next":
      return computeDueNext(ctx);
    case "who_late":
      return computeWhoLate(ctx);
    case "daily_win_track":
      return computeDailyWinTrack(ctx);
    case "hearth_tonight":
      return computeHearthTonight(ctx);
    case "parent_attention":
      return computeParentAttention(ctx);
  }
}

function computeDueNext(ctx: AnswerContext): AnswerResult {
  const today = ctx.today.data;
  if (!today) return { lines: ["Today's snapshot hasn't loaded yet."] };
  const all = [
    ...today.blocks.flatMap((b) => b.occurrences),
    ...today.standalone_chores,
    ...today.weekly_items,
  ].filter((o) => o.status !== "complete" && o.due_at);
  const now = Date.now();
  const upcoming = all
    .filter((o) => new Date(o.due_at!).getTime() >= now)
    .sort((a, b) => new Date(a.due_at!).getTime() - new Date(b.due_at!).getTime())
    .slice(0, 3);
  if (upcoming.length === 0) {
    return { lines: ["Nothing else due today."], deepLink: "/today" };
  }
  return {
    lines: upcoming.map(
      (o) =>
        `${o.owner_name ?? "Unassigned"} · ${o.label} · ${formatTime(o.due_at!)}`,
    ),
    deepLink: "/today",
  };
}

function computeWhoLate(ctx: AnswerContext): AnswerResult {
  const today = ctx.today.data;
  if (!today) return { lines: ["Today's snapshot hasn't loaded yet."] };
  const lateByMember = new Map<string, string[]>();
  const all = [
    ...today.blocks.flatMap((b) => b.occurrences),
    ...today.standalone_chores,
    ...today.weekly_items,
  ];
  for (const o of all) {
    if (o.status === "late") {
      const k = o.owner_name ?? "Unassigned";
      const arr = lateByMember.get(k) ?? [];
      arr.push(o.label);
      lateByMember.set(k, arr);
    }
  }
  if (lateByMember.size === 0) {
    return { lines: ["Nobody is late right now. Quiet enforcement holds."] };
  }
  const lines: string[] = [];
  for (const [name, items] of lateByMember.entries()) {
    lines.push(`${name}: ${items.length} late · ${items.slice(0, 2).join(" · ")}`);
  }
  return { lines, deepLink: "/today" };
}

function computeDailyWinTrack(ctx: AnswerContext): AnswerResult {
  const today = ctx.today.data;
  const family = ctx.family.data;
  const me = ctx.me.data;
  if (!today || !family || !me) {
    return { lines: ["Snapshot still loading."] };
  }
  // If the actor is a child, answer for them. If parent, summarize all kids.
  const actorMemberId = me.user.family_member_id;
  const actorIsKid = family.kids.some((k) => k.family_member_id === actorMemberId);

  const summarize = (memberId: string, displayName: string): string => {
    const all = [
      ...today.blocks.flatMap((b) => b.occurrences),
      ...today.standalone_chores,
    ];
    const mine = all.filter((o) => o.owner_family_member_id === memberId);
    const completed = mine.filter((o) => o.status === "complete").length;
    const late = mine.filter((o) => o.status === "late").length;
    const remaining = mine.length - completed;
    if (mine.length === 0) {
      return `${displayName}: no required items`;
    }
    if (remaining === 0) {
      return `${displayName}: all clear (${completed}/${mine.length}) — Daily Win locked`;
    }
    if (late > 0) {
      return `${displayName}: ${late} late · ${completed}/${mine.length} done · OFF TRACK`;
    }
    return `${displayName}: ${completed}/${mine.length} done · ${remaining} to go · on track`;
  };

  if (actorIsKid) {
    const k = family.kids.find((k) => k.family_member_id === actorMemberId)!;
    return { lines: [summarize(k.family_member_id, k.name)], deepLink: "/today" };
  }
  return {
    lines: family.kids.map((k) => summarize(k.family_member_id, k.name)),
    deepLink: "/today",
  };
}

function computeHearthTonight(ctx: AnswerContext): AnswerResult {
  const exports = ctx.calendar.data?.items ?? [];
  if (exports.length === 0) {
    if (ctx.calendar.status === "error") {
      return {
        lines: [
          "Calendar export feed is unavailable. Hearth will only show what was published before the feed went stale.",
        ],
        deepLink: "/calendar",
      };
    }
    return { lines: ["No anchor blocks queued for tonight."] };
  }
  // Tonight = today, after 17:00 local.
  const tonight = exports.filter((e: CalendarExport) => {
    const d = new Date(e.starts_at);
    if (Number.isNaN(d.getTime())) return false;
    const today = new Date();
    return (
      d.getFullYear() === today.getFullYear() &&
      d.getMonth() === today.getMonth() &&
      d.getDate() === today.getDate() &&
      d.getHours() >= 17 &&
      e.hearth_visible
    );
  });
  if (tonight.length === 0) {
    return {
      lines: ["No Hearth-visible blocks scheduled for tonight."],
      deepLink: "/calendar",
    };
  }
  return {
    lines: tonight.map(
      (e) => `${formatTime(e.starts_at)} · ${e.label}`,
    ),
    deepLink: "/calendar",
  };
}

function computeParentAttention(ctx: AnswerContext): AnswerResult {
  if (!ctx.isParent) {
    return {
      lines: [
        "Parent-only view. Sign in as a PARENT or PRIMARY_PARENT to see this.",
      ],
    };
  }
  const lines: string[] = [];
  const summary = ctx.summary.data;

  // Pending reward approvals
  const pendingApprovals = summary?.rewards.pending_approval_count ?? 0;
  if (pendingApprovals > 0) {
    lines.push(`${pendingApprovals} reward approval${pendingApprovals === 1 ? "" : "s"} waiting`);
  }

  // Sync errors
  const syncFailed = summary?.sync_jobs.failed_count ?? 0;
  if (syncFailed > 0) {
    lines.push(`${syncFailed} sync job${syncFailed === 1 ? "" : "s"} failing`);
  }

  // Connector errors
  const connectorErrors = summary?.connectors.error_count ?? 0;
  if (connectorErrors > 0) {
    lines.push(`${connectorErrors} connector${connectorErrors === 1 ? "" : "s"} in error state`);
  }

  // Failed exports
  const failedExports = summary?.calendar_exports.failed_count ?? 0;
  if (failedExports > 0) {
    lines.push(`${failedExports} calendar export${failedExports === 1 ? "" : "s"} failed to publish`);
  }

  // Late kids
  const today = ctx.today.data;
  if (today) {
    const lateCount = today.summary.late_count;
    if (lateCount > 0) {
      lines.push(`${lateCount} task${lateCount === 1 ? "" : "s"} late on Today`);
    }
  }

  if (lines.length === 0) {
    lines.push("Nothing on fire. The household is on its rails.");
  }
  return { lines, deepLink: "/control-plane" };
}

const styles = StyleSheet.create({
  eyebrow: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1.6,
    textTransform: "uppercase",
  },
  title: {
    color: colors.textPrimary,
    fontSize: 30,
    fontWeight: "800",
    marginTop: 4,
    letterSpacing: -0.6,
  },
  subtle: {
    color: colors.textMuted,
    fontSize: 13,
    marginTop: 4,
    marginBottom: 4,
    lineHeight: 18,
  },

  answer: {
    backgroundColor: colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 14,
    marginBottom: 14,
  },
  answerLabel: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 1.4,
    marginBottom: 8,
  },
  answerRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: 4,
  },
  answerBullet: {
    color: colors.accent,
    fontSize: 16,
    fontWeight: "800",
    width: 12,
  },
  answerLine: {
    flex: 1,
    color: colors.textPrimary,
    fontSize: 13,
    lineHeight: 18,
  },
  answerEmpty: { color: colors.textMuted, fontSize: 12, fontStyle: "italic" },

  deepLink: {
    alignSelf: "flex-end",
    marginTop: 8,
  },
  deepLinkText: {
    color: colors.accent,
    fontSize: 12,
    fontWeight: "800",
  },

  footnote: {
    color: colors.textPlaceholder,
    fontSize: 11,
    marginTop: 24,
    textAlign: "center",
    paddingHorizontal: 16,
    lineHeight: 16,
    fontStyle: "italic",
  },
});
