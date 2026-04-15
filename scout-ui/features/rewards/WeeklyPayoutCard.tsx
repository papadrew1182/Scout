/**
 * WeeklyPayoutCard — per-child weekly payout breakdown.
 *
 * Reads the member shape from /api/rewards/week/current:
 *   { family_member_id, name, baseline_allowance, daily_wins,
 *     payout_percent, projected_payout, miss_reasons[] }
 *
 * Parent-only affordances are hidden when isParent === false.
 */

import { StyleSheet, Text, View } from "react-native";

import { RewardsMember } from "../lib/contracts";
import { colors } from "../../lib/styles";

interface Props {
  member: RewardsMember;
  isParent: boolean;
}

export function WeeklyPayoutCard({ member, isParent }: Props) {
  const percentColor =
    member.payout_percent >= 100
      ? colors.positive
      : member.payout_percent >= 60
        ? colors.accent
        : member.payout_percent > 0
          ? colors.warning
          : colors.negative;

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <View style={{ flex: 1 }}>
          <Text style={styles.name}>{member.name}</Text>
          <Text style={styles.baseline}>
            Baseline ${member.baseline_allowance.toFixed(2)} · {member.daily_wins} daily wins
          </Text>
        </View>
        <View style={styles.amountCol}>
          <Text style={styles.amount}>${member.projected_payout.toFixed(2)}</Text>
          <Text style={[styles.percent, { color: percentColor }]}>
            {member.payout_percent}%
          </Text>
        </View>
      </View>

      {/* Progress bar */}
      <View style={styles.barTrack}>
        <View
          style={[
            styles.barFill,
            {
              width: `${Math.min(100, Math.max(0, member.payout_percent))}%`,
              backgroundColor: percentColor,
            },
          ]}
        />
      </View>

      {member.miss_reasons.length > 0 && (
        <View style={styles.missBlock}>
          <Text style={styles.missLabel}>Missing</Text>
          {member.miss_reasons.slice(0, 4).map((r, i) => (
            <Text key={i} style={styles.missLine} numberOfLines={1}>
              · {r}
            </Text>
          ))}
          {member.miss_reasons.length > 4 && (
            <Text style={styles.missMore}>
              +{member.miss_reasons.length - 4} more
            </Text>
          )}
        </View>
      )}

      {isParent && member.payout_percent === 0 && member.daily_wins < 3 && (
        <Text style={styles.parentNote}>
          Currently below the 3-daily-win threshold for any payout this week.
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 16,
    marginBottom: 12,
  },
  headerRow: { flexDirection: "row", alignItems: "center" },
  name: { color: colors.textPrimary, fontSize: 16, fontWeight: "700" },
  baseline: { color: colors.textMuted, fontSize: 12, marginTop: 2, fontWeight: "600" },
  amountCol: { alignItems: "flex-end" },
  amount: {
    color: colors.textPrimary,
    fontSize: 18,
    fontWeight: "800",
    fontVariant: ["tabular-nums"] as any,
  },
  percent: { fontSize: 11, fontWeight: "800", marginTop: 2 },

  barTrack: {
    marginTop: 12,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.surfaceMuted,
    overflow: "hidden",
  },
  barFill: { height: "100%" },

  missBlock: { marginTop: 12 },
  missLabel: {
    color: colors.warning,
    fontSize: 10,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 0.8,
    marginBottom: 4,
  },
  missLine: { color: colors.textSecondary, fontSize: 12, marginTop: 2 },
  missMore: { color: colors.textMuted, fontSize: 11, marginTop: 4 },

  parentNote: {
    color: colors.warning,
    fontSize: 11,
    fontWeight: "600",
    marginTop: 10,
  },
});
