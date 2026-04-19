/**
 * RewardsHome — Session 3 Block 2 rewards surface.
 *
 * Reads /api/rewards/week/current and renders:
 *   - Period header (week start/end) + family total projection
 *   - DailyWinCard per child showing N daily wins (filled vs hollow dots)
 *   - WeeklyPayoutCard per child with baseline allowance, payout %,
 *     projected payout, miss reasons
 *   - Approval state pill (display only — no mutation; charter does not
 *     ship a parent-approval endpoint yet)
 *   - Loading / empty / error states
 *
 * No backend mutation is invented. Parent affordances are gated on
 * `useIsParent()` (PRIMARY_PARENT or PARENT) — never on age.
 */

import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { RewardsCurrentWeekResponse } from "../lib/contracts";
import { useIsParent, useRewardsWeek } from "../hooks";
import { useHasPermission } from "../../lib/permissions";
import { colors } from "../../lib/styles";
import { DailyWinCard } from "./DailyWinCard";
import { WeeklyPayoutCard } from "./WeeklyPayoutCard";

export function RewardsHome() {
  const rewards = useRewardsWeek();
  const isParent = useIsParent();

  if (rewards.status === "idle" || rewards.status === "loading") {
    return <SkeletonState />;
  }
  if (rewards.status === "error") {
    return (
      <ErrorState
        message={rewards.error ?? "Couldn't load this week's rewards"}
        onRetry={rewards.refresh}
      />
    );
  }
  const data = rewards.data;
  if (!data) return null;

  if (data.members.length === 0) {
    return (
      <EmptyState
        title="No rewards yet"
        body="No allowance period is active yet. Once chores are running for a week the projections will appear here."
      />
    );
  }

  const totalProjected = data.members.reduce((sum, m) => sum + m.projected_payout, 0);

  return (
    <View>
      <Text style={styles.eyebrow}>Rewards</Text>
      <Text style={styles.title}>This week</Text>
      <Text style={styles.subtle}>
        {formatPeriod(data)} · ${totalProjected.toFixed(2)} projected
      </Text>

      <ApprovalRow data={data} isParent={isParent} />

      <Text style={styles.section}>Daily Wins so far</Text>
      <View style={styles.row}>
        {data.members.map((m) => (
          <DailyWinCard key={m.family_member_id} member={m} />
        ))}
      </View>

      <Text style={styles.section}>Weekly payout</Text>
      {data.members.map((m) => (
        <WeeklyPayoutCard key={m.family_member_id} member={m} isParent={isParent} />
      ))}

      {/* no-op: informational disclosure text, not interactive */}
      <Text style={styles.note}>
        Reward calculation is owned by Scout. Greenlight is the payout-facing
        rail. Approval and settlement land later in this lane.
      </Text>
    </View>
  );
}

function ApprovalRow({
  data,
  isParent,
}: {
  data: RewardsCurrentWeekResponse;
  isParent: boolean;
}) {
  const canRunPayout = useHasPermission("allowance.run_payout");
  const [showAction, setShowAction] = useState(false);
  const state = data.approval.state;
  const label =
    state === "approved"
      ? "Approved"
      : state === "ready_for_review"
        ? "Ready for review"
        : "Draft";
  const canTap = isParent && canRunPayout && state === "ready_for_review";
  return (
    <View style={styles.approvalRow}>
      <Pressable
        style={[
          styles.approvalPill,
          state === "approved" && styles.approvalApproved,
          state === "ready_for_review" && styles.approvalReady,
        ]}
        onPress={canTap ? () => setShowAction(!showAction) : undefined}
        accessibilityRole={canTap ? "button" : "text"}
        accessibilityLabel={`Approval status: ${label}`}
        disabled={!canTap}
      >
        <Text
          style={[
            styles.approvalText,
            state === "approved" && { color: "#00866B" },
            state === "ready_for_review" && { color: "#A2660C" },
          ]}
        >
          {label.toUpperCase()}
        </Text>
      </Pressable>
      {canTap && showAction && (
        <View style={styles.approvalAction}>
          <Text style={styles.approvalHelp}>
            Parent approval flow lands in a later sprint. The period state
            is read-only until then.
          </Text>
        </View>
      )}
      {isParent && !canTap && state === "ready_for_review" && (
        <Text style={styles.approvalHelp}>
          A parent approval flow lands later in this lane. Until then the
          period state is read-only here.
        </Text>
      )}
    </View>
  );
}

function SkeletonState() {
  return (
    <View>
      <Text style={styles.eyebrow}>Rewards</Text>
      <Text style={styles.title}>This week</Text>
      <View style={styles.skeletonStrip} />
      <View style={styles.skeletonCard} />
      <View style={styles.skeletonCard} />
      <View style={styles.skeletonCard} />
    </View>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <View style={styles.empty}>
      <Text style={styles.emptyTitle}>{title}</Text>
      <Text style={styles.emptyBody}>{body}</Text>
    </View>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <View style={styles.center}>
      <Text style={styles.error}>{message}</Text>
      <Pressable style={styles.retry} onPress={onRetry} accessibilityRole="button">
        <Text style={styles.retryText}>Try again</Text>
      </Pressable>
    </View>
  );
}

function formatPeriod(d: RewardsCurrentWeekResponse): string {
  if (!d.period) return "Period not yet open";
  return `${d.period.start_date} – ${d.period.end_date}`;
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
  subtle: { color: colors.textMuted, fontSize: 13, marginTop: 4 },
  section: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 1.4,
    marginTop: 24,
    marginBottom: 8,
  },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },

  approvalRow: { marginTop: 14, marginBottom: 4 },
  approvalPill: {
    alignSelf: "flex-start",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: colors.surfaceMuted,
  },
  approvalApproved: { backgroundColor: colors.positiveBg },
  approvalReady: { backgroundColor: colors.warningBg },
  approvalText: {
    color: colors.textSecondary,
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 0.6,
  },
  approvalAction: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 10,
    padding: 12,
    marginTop: 8,
  },
  approvalHelp: {
    color: colors.textMuted,
    fontSize: 11,
    marginTop: 6,
    fontStyle: "italic",
  },

  note: {
    color: colors.textPlaceholder,
    fontSize: 11,
    marginTop: 24,
    textAlign: "center",
    paddingHorizontal: 16,
  },

  skeletonStrip: {
    height: 60,
    borderRadius: 12,
    backgroundColor: colors.surfaceMuted,
    marginVertical: 14,
  },
  skeletonCard: {
    height: 90,
    borderRadius: 14,
    backgroundColor: colors.surfaceMuted,
    marginBottom: 12,
  },

  empty: { marginTop: 30, alignItems: "center", paddingHorizontal: 12 },
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
});
