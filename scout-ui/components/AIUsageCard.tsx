/**
 * AI usage + approximate cost card (Tier 3 Feature 11).
 *
 * Reads /api/ai/usage and renders a small parent-facing rollup with
 * total tokens, approximate USD spend, a soft-cap warning when the
 * backend flags one, and a by-day micro-bar-chart. Parent-only — the
 * backing endpoint returns 403 for non-adult actors.
 *
 * Kept intentionally simple. This is an operational awareness card,
 * not a full analytics dashboard.
 */

import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { fetchAIUsage, type AIUsageReport } from "../lib/api";
import { colors, shared } from "../lib/styles";

export function AIUsageCard() {
  const [report, setReport] = useState<AIUsageReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetchAIUsage(7);
      setReport(r);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <View style={styles.container}>
        <Text style={shared.sectionTitle}>Scout AI usage</Text>
        <View style={shared.card}>
          <ActivityIndicator size="small" color={colors.accent} />
        </View>
      </View>
    );
  }

  if (error || !report) {
    return (
      <View style={styles.container}>
        <Text style={shared.sectionTitle}>Scout AI usage</Text>
        <View style={shared.card}>
          <Text style={shared.errorText}>{error ?? "No data"}</Text>
          <Pressable style={[shared.buttonSmall, { marginTop: 8 }]} onPress={load}>
            <Text style={shared.buttonSmallText}>Retry</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  // Short-circuit entirely when nothing has been used. A blank card
  // would just be noise on a fresh family.
  if (report.total_messages === 0) {
    return null;
  }

  const maxDayCost = report.by_day.reduce(
    (m, d) => (d.cost_usd > m ? d.cost_usd : m),
    0,
  );
  const totalIn = report.total_tokens.input.toLocaleString();
  const totalOut = report.total_tokens.output.toLocaleString();
  const costStr = `$${report.approx_cost_usd.toFixed(2)}`;

  return (
    <View style={styles.container}>
      <Text style={shared.sectionTitle}>Scout AI usage</Text>
      <View
        style={[
          shared.card,
          report.cap_warning && styles.cardWarning,
        ]}
      >
        <View style={styles.headerRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.headerLabel}>Last {report.days} days</Text>
            <Text style={styles.headerCost}>~{costStr}</Text>
            <Text style={styles.headerSub}>
              {report.total_messages.toLocaleString()} messages · {totalIn} in ·{" "}
              {totalOut} out
            </Text>
          </View>
          {report.cap_warning && (
            <View style={styles.warnPill}>
              <Text style={styles.warnPillText}>Above soft cap</Text>
            </View>
          )}
        </View>

        <View style={styles.barRow}>
          {report.by_day.map((d) => {
            const h = maxDayCost > 0 ? Math.max(2, (d.cost_usd / maxDayCost) * 36) : 2;
            return (
              <View key={d.date} style={styles.barCol}>
                <View style={[styles.bar, { height: h }]} />
                <Text style={styles.barLabel}>{d.date.slice(5)}</Text>
              </View>
            );
          })}
        </View>

        {report.by_model.length > 0 && (
          <View style={styles.breakdownBlock}>
            <Text style={styles.breakdownTitle}>By model</Text>
            {report.by_model.slice(0, 4).map((m) => (
              <View key={m.model} style={styles.breakdownRow}>
                <Text style={styles.breakdownKey} numberOfLines={1}>
                  {m.model}
                </Text>
                <Text style={styles.breakdownVal}>
                  ${m.cost_usd.toFixed(2)} · {m.messages}
                </Text>
              </View>
            ))}
          </View>
        )}

        {report.by_member.length > 0 && (
          <View style={styles.breakdownBlock}>
            <Text style={styles.breakdownTitle}>By member</Text>
            {report.by_member.slice(0, 6).map((m) => (
              <View key={m.member_id} style={styles.breakdownRow}>
                <Text style={styles.breakdownKey}>{m.first_name}</Text>
                <Text style={styles.breakdownVal}>
                  ${m.cost_usd.toFixed(2)} · {m.messages}
                </Text>
              </View>
            ))}
          </View>
        )}

        <Text style={styles.footnote}>
          Approximate cost. Real billing may differ.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginTop: 8 },
  cardWarning: {
    borderLeftWidth: 3,
    borderLeftColor: colors.warning,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
  },
  headerLabel: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  headerCost: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: "700",
    marginTop: 2,
  },
  headerSub: {
    color: colors.textMuted,
    fontSize: 12,
    marginTop: 2,
  },
  warnPill: {
    backgroundColor: colors.warning + "22",
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  warnPillText: {
    color: colors.warning,
    fontSize: 10,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  barRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: 4,
    marginTop: 14,
    height: 56,
  },
  barCol: {
    flex: 1,
    alignItems: "center",
    justifyContent: "flex-end",
    gap: 3,
  },
  bar: {
    width: "80%",
    backgroundColor: colors.accent,
    borderRadius: 2,
  },
  barLabel: {
    color: colors.textMuted,
    fontSize: 9,
  },
  breakdownBlock: {
    marginTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.cardBorder,
    paddingTop: 10,
  },
  breakdownTitle: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  breakdownRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 3,
  },
  breakdownKey: {
    color: colors.textPrimary,
    fontSize: 13,
    flex: 1,
  },
  breakdownVal: {
    color: colors.textMuted,
    fontSize: 12,
    fontVariant: ["tabular-nums"],
  },
  footnote: {
    color: colors.textMuted,
    fontSize: 10,
    fontStyle: "italic",
    marginTop: 10,
    textAlign: "center",
  },
});
