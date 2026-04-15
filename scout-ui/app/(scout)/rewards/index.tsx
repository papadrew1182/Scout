import { StyleSheet, Text, View } from "react-native";

import { useRewardsWeek } from "../../../features/hooks";
import { formatCents } from "../../../features/lib/formatters";
import { colors } from "../../../lib/styles";

export default function RewardsRoute() {
  const { data, status, error } = useRewardsWeek();
  if (status === "loading" || status === "idle") {
    return (
      <View style={styles.center}>
        <Text style={styles.muted}>Loading rewards…</Text>
      </View>
    );
  }
  if (status === "error") {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error ?? "Failed to load rewards"}</Text>
      </View>
    );
  }
  if (!data) return null;
  return (
    <View>
      <Text style={styles.eyebrow}>Rewards</Text>
      <Text style={styles.title}>Week of {data.week_start}</Text>
      <Text style={styles.subtle}>
        Family total preview: {formatCents(data.total_payout_cents)}
      </Text>

      {data.children.map((c) => (
        <View key={c.member_id} style={styles.card}>
          <View style={styles.cardRow}>
            <Text style={styles.cardTitle}>{c.first_name}</Text>
            <Text style={styles.cardAmount}>
              {formatCents(c.payout_cents)}{" "}
              <Text style={styles.percent}>· {c.payout_percent}%</Text>
            </Text>
          </View>
          <Text style={styles.subtle}>
            {c.win_count} of 5 daily wins · baseline {formatCents(c.baseline_cents)}
          </Text>
          <View style={styles.dotsRow}>
            {c.day_wins.map((d, i) => (
              <View
                key={i}
                style={[
                  styles.dot,
                  d === true && styles.dotWon,
                  d === false && styles.dotMissed,
                ]}
              />
            ))}
          </View>
          {c.missed_reasons.length > 0 && (
            <Text style={styles.missed}>
              Missing today: {c.missed_reasons.slice(0, 2).join(" · ")}
              {c.missed_reasons.length > 2 ? "…" : ""}
            </Text>
          )}
        </View>
      ))}

      <Text style={styles.note}>
        Approval flow lands in the next block. This is a read-only preview.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  center: { alignItems: "center", paddingTop: 60 },
  muted: { color: colors.textMuted },
  error: { color: colors.negative },
  eyebrow: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1.6,
    textTransform: "uppercase",
  },
  title: {
    color: colors.textPrimary,
    fontSize: 24,
    fontWeight: "700",
    marginTop: 4,
    marginBottom: 8,
  },
  subtle: { color: colors.textMuted, fontSize: 13, marginBottom: 4 },
  card: {
    backgroundColor: colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 16,
    marginTop: 12,
  },
  cardRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  cardTitle: { color: colors.textPrimary, fontSize: 16, fontWeight: "700" },
  cardAmount: { color: colors.textPrimary, fontSize: 16, fontWeight: "700" },
  percent: { color: colors.textMuted, fontWeight: "600" },
  dotsRow: { flexDirection: "row", gap: 6, marginTop: 10 },
  dot: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.surfaceMuted },
  dotWon: { backgroundColor: colors.positive },
  dotMissed: { backgroundColor: colors.negative },
  missed: { color: colors.warning, fontSize: 12, marginTop: 8 },
  note: {
    color: colors.textPlaceholder,
    fontSize: 11,
    marginTop: 18,
    textAlign: "center",
  },
});
