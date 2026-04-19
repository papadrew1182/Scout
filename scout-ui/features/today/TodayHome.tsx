/**
 * TodayHome — Session 3 default landing surface.
 *
 * Answers the questions the operating surface MUST answer:
 *   - what is active now
 *   - what is due next
 *   - who still has work left
 *   - what can be completed in one tap
 *   - what is blocked or late
 *   - whether each child is still on track for a Daily Win
 *
 * Data sources
 *   - kids list:           /api/family/context/current → `kids`
 *   - household snapshot:  /api/household/today        → blocks + standalone_chores + weekly_items
 *   - daily-win counts:    derived client-side from the household snapshot
 *
 * Daily-win derivation: the canonical /api/household/today response
 * does NOT include a daily_win_preview field. To honor the
 * "on track for a Daily Win" requirement we count, per kid, the number
 * of routine assignments + ownership chores they own today. Each
 * routine block contributes ONE assignment per kid (matching the family
 * file's "morning + after-school + evening" daily-win semantic), and
 * each standalone chore contributes one occurrence. Once the backend
 * ships a real daily-win read model we replace this block with the API
 * value with no other UI changes.
 */

import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import {
  BlockAssignment,
  FamilyKid,
  HouseholdTodayResponse,
  OccurrenceStatus,
} from "../lib/contracts";
import {
  useFamilyContext,
  useHouseholdToday,
  useUiCompletionSheet,
  useUiFocusMember,
  useUiToast,
} from "../hooks";
import { colors } from "../../lib/styles";
import { HouseholdBoard } from "./HouseholdBoard";
import { CompletionSheet } from "./CompletionSheet";
import { AffirmationCard } from "../affirmations/AffirmationCard";

interface KidWinSummary {
  kid: FamilyKid;
  required: number;
  completed: number;
  remaining: number;
  late: number;
  on_track: boolean;
  all_done: boolean;
}

export function TodayHome() {
  const router = useRouter();
  const today = useHouseholdToday();
  const family = useFamilyContext();
  const { focused_member_id, setFocus } = useUiFocusMember();
  const { occurrence_id: sheetOccId, close: closeSheet } = useUiCompletionSheet();
  const { toast, dismiss } = useUiToast();

  if (today.status === "idle" || today.status === "loading") {
    return <SkeletonState />;
  }
  if (today.status === "error" || !today.data) {
    return <ErrorState message={today.error ?? "Couldn't load today"} onRetry={today.refresh} />;
  }

  const data = today.data;
  const kids = family.data?.kids ?? [];
  const dateLabel = formatDateHeader(data.date);

  // Filter view if a child is focused.
  const filtered: HouseholdTodayResponse = focused_member_id
    ? {
        ...data,
        blocks: data.blocks
          .map((b) => ({
            ...b,
            assignments: b.assignments.filter(
              (a) => a.family_member_id === focused_member_id,
            ),
          }))
          .filter((b) => b.assignments.length > 0),
        standalone_chores: data.standalone_chores.filter(
          (o) => o.owner_family_member_id === focused_member_id,
        ),
        weekly_items: data.weekly_items.filter(
          (o) => o.owner_family_member_id === focused_member_id,
        ),
      }
    : data;

  const winSummaries = kids.map((k) => summarizeForKid(k, data));
  const empty =
    filtered.blocks.every((b) => b.assignments.length === 0) &&
    filtered.standalone_chores.length === 0 &&
    filtered.weekly_items.length === 0;

  return (
    <View>
      <Text style={styles.eyebrow}>{family.data?.family.name ?? "Household"}</Text>
      <Text style={styles.title}>Today</Text>
      <Text style={styles.subtitle}>{dateLabel}</Text>

      {/* Summary strip */}
      <View style={styles.summaryRow}>
        <SummaryCell label="Due" value={data.summary.due_count} />
        <SummaryCell label="Done" value={data.summary.completed_count} />
        <SummaryCell
          label="Late"
          value={data.summary.late_count}
          warn={data.summary.late_count > 0}
        />
      </View>

      {/* Daily Win strip - derived client-side; see file header note. */}
      <View style={styles.winRow}>
        {winSummaries.map((s) => (
          <Pressable
            key={s.kid.family_member_id}
            style={[
              styles.winPill,
              s.all_done && styles.winPillDone,
              !s.all_done && !s.on_track && styles.winPillRisk,
            ]}
            onPress={() => router.push(`/members/${s.kid.family_member_id}`)}
            accessible
            accessibilityRole="link"
            accessibilityLabel={`${s.kid.name} ${s.completed} of ${s.required} complete`}
          >
            <Text
              style={[
                styles.winName,
                s.all_done && styles.winNameDone,
                !s.all_done && !s.on_track && styles.winNameRisk,
              ]}
            >
              {s.kid.name}
            </Text>
            <Text style={styles.winCount}>
              {s.completed} / {s.required}
              {s.late > 0 ? `  . ${s.late} late` : ""}
            </Text>
          </Pressable>
        ))}
      </View>

      <AffirmationCard />

      {/* Filter chips: household + per child */}
      <View style={styles.chipRow}>
        <FilterChip
          label="Household"
          active={focused_member_id === null}
          onPress={() => setFocus(null)}
        />
        {kids.map((k) => (
          <FilterChip
            key={k.family_member_id}
            label={k.name}
            active={focused_member_id === k.family_member_id}
            onPress={() => setFocus(k.family_member_id)}
          />
        ))}
      </View>

      {empty ? (
        <EmptyState
          title={
            focused_member_id ? "No work for this child today" : "No work for today"
          }
          body={
            focused_member_id
              ? "Either everything is done or no chores were generated."
              : "Either everything is done or no chores were generated. Check the control plane if this seems wrong."
          }
        />
      ) : (
        <HouseholdBoard data={filtered} />
      )}

      <CompletionSheet
        occurrenceId={sheetOccId}
        onClose={closeSheet}
        source={data}
      />

      {toast && (
        <Pressable
          onPress={dismiss}
          accessible
          accessibilityRole="button"
          accessibilityLabel={`${toast.kind === "error" ? "Error" : "Success"}: ${toast.message}. Tap to dismiss.`}
          accessibilityLiveRegion="polite"
          style={[
            styles.toast,
            toast.kind === "error" ? styles.toastErr : styles.toastOk,
          ]}
        >
          <Text style={styles.toastText}>{toast.message}</Text>
        </Pressable>
      )}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function summarizeForKid(
  kid: FamilyKid,
  data: HouseholdTodayResponse,
): KidWinSummary {
  // Per family_chore_system.md a Daily Win = morning + after-school +
  // evening + ownership chore + (rotating common-area chore if assigned).
  // Each routine block contributes ONE assignment per kid (the
  // assignment's status reflects the whole routine), and each standalone
  // chore is one occurrence. weekly_items are excluded — Power 60 is
  // not a daily win.
  const myAssignments: BlockAssignment[] = data.blocks.flatMap((b) =>
    b.assignments.filter((a) => a.family_member_id === kid.family_member_id),
  );
  const myStandalone = data.standalone_chores.filter(
    (o) => o.owner_family_member_id === kid.family_member_id,
  );
  const items: { status: OccurrenceStatus }[] = [
    ...myAssignments.map((a) => ({ status: a.status })),
    ...myStandalone.map((o) => ({ status: o.status })),
  ];
  const completed = items.filter((o) => o.status === "complete").length;
  const late = items.filter((o) => o.status === "late").length;
  const remaining = items.length - completed;
  return {
    kid,
    required: items.length,
    completed,
    remaining,
    late,
    on_track: late === 0,
    all_done: items.length > 0 && remaining === 0,
  };
}

function formatDateHeader(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

// ---------------------------------------------------------------------------
// Inner subcomponents
// ---------------------------------------------------------------------------

function SummaryCell({
  label,
  value,
  warn,
}: {
  label: string;
  value: number;
  warn?: boolean;
}) {
  return (
    <View style={styles.summaryCell}>
      <Text style={[styles.summaryValue, warn && styles.summaryValueWarn]}>{value}</Text>
      <Text style={styles.summaryLabel}>{label}</Text>
    </View>
  );
}

function FilterChip({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      style={[styles.chip, active && styles.chipActive]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`Filter ${label}`}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

function SkeletonState() {
  return (
    <View>
      <Text style={styles.eyebrow}>Household</Text>
      <Text style={styles.title}>Today</Text>
      <View style={styles.skeletonRow}>
        <View style={styles.skeletonChip} />
        <View style={styles.skeletonChip} />
        <View style={styles.skeletonChip} />
      </View>
      <View style={styles.skeletonCard} />
      <View style={styles.skeletonCard} />
      <View style={styles.skeletonCard} />
    </View>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <View style={styles.emptyState}>
      <Text style={styles.emptyTitle}>{title}</Text>
      <Text style={styles.emptyBody}>{body}</Text>
    </View>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <View style={styles.center} accessible accessibilityLiveRegion="polite">
      <Text style={styles.error}>{message}</Text>
      <Pressable
        style={styles.retry}
        onPress={onRetry}
        accessibilityRole="button"
        accessibilityLabel="Retry loading Today"
        hitSlop={10}
      >
        <Text style={styles.retryText}>Try again</Text>
      </Pressable>
    </View>
  );
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
  subtitle: {
    color: colors.textMuted,
    fontSize: 13,
    marginTop: 4,
    marginBottom: 16,
  },

  summaryRow: {
    flexDirection: "row",
    backgroundColor: colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingVertical: 12,
    marginBottom: 12,
  },
  summaryCell: { flex: 1, alignItems: "center" },
  summaryValue: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: "800",
    fontVariant: ["tabular-nums"] as any,
  },
  summaryValueWarn: { color: colors.negative },
  summaryLabel: {
    color: colors.textMuted,
    fontSize: 10,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.8,
    marginTop: 2,
  },

  winRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: 14,
  },
  winPill: {
    flexBasis: "30%",
    flexGrow: 1,
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingHorizontal: 12,
    paddingVertical: 10,
    minWidth: 100,
  },
  winPillDone: { backgroundColor: colors.positiveBg, borderColor: colors.positive },
  winPillRisk: { backgroundColor: colors.warningBg, borderColor: colors.warning },
  winName: { color: colors.textPrimary, fontSize: 13, fontWeight: "700" },
  winNameDone: { color: "#00866B" },
  winNameRisk: { color: "#A2660C" },
  winCount: {
    color: colors.textMuted,
    fontSize: 11,
    marginTop: 2,
    fontWeight: "600",
  },

  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 18 },
  chip: {
    backgroundColor: colors.card,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  chipActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  chipText: { color: colors.textSecondary, fontSize: 12, fontWeight: "700" },
  chipTextActive: { color: colors.buttonPrimaryText },

  emptyState: { marginTop: 30, alignItems: "center", paddingHorizontal: 12 },
  emptyTitle: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: "700",
    marginBottom: 6,
  },
  emptyBody: {
    color: colors.textMuted,
    fontSize: 13,
    textAlign: "center",
    lineHeight: 18,
  },

  center: { alignItems: "center", paddingTop: 80 },
  error: { color: colors.negative, fontSize: 14, marginBottom: 12 },
  retry: {
    backgroundColor: colors.accent,
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  retryText: { color: colors.buttonPrimaryText, fontWeight: "700" },

  skeletonRow: { flexDirection: "row", gap: 8, marginVertical: 12 },
  skeletonChip: {
    flex: 1,
    height: 40,
    borderRadius: 12,
    backgroundColor: colors.surfaceMuted,
  },
  skeletonCard: {
    height: 120,
    borderRadius: 14,
    backgroundColor: colors.surfaceMuted,
    marginBottom: 12,
  },

  toast: {
    position: "absolute",
    bottom: -12,
    left: 0,
    right: 0,
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 12,
    marginHorizontal: 16,
    alignItems: "center",
  },
  toastOk: { backgroundColor: colors.positive },
  toastErr: { backgroundColor: colors.negative },
  toastText: { color: colors.buttonPrimaryText, fontWeight: "700", fontSize: 13 },
});
