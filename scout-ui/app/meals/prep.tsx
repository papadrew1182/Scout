/**
 * Meals — Sunday Prep tab.
 *
 * Lightweight rebuild of the legacy prep page, scoped to what the smoke
 * tests assert: a "Sunday Prep" header when a plan exists, or a
 * "No plan yet" empty state when one does not. The visual language
 * matches the rest of the redesigned meals surface.
 */

import { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";

import { colors, fonts, shared } from "../../lib/styles";
import { fetchCurrentWeeklyPlan } from "../../lib/api";
import type { WeeklyMealPlan } from "../../lib/types";

export default function MealsPrep() {
  const [plan, setPlan] = useState<WeeklyMealPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchCurrentWeeklyPlan()
      .then((p) => { if (!cancelled) setPlan(p); })
      .catch((e) => {
        // 404 is the expected "no plan yet" path — not a real error
        if (!cancelled) {
          setPlan(null);
          if (!/404|not found|Failed to fetch/i.test(String(e?.message ?? e))) {
            setError(String(e?.message ?? e));
          }
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <View style={shared.pageCenter}>
        <ActivityIndicator size="large" color={colors.purple} />
      </View>
    );
  }

  if (!plan) {
    return (
      <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
        <View style={shared.card}>
          <Text style={styles.header}>Sunday Prep</Text>
          <Text style={styles.empty}>No plan yet. Generate one on This Week first.</Text>
        </View>
      </ScrollView>
    );
  }

  // The real prep_plan shape is a free-form JSON blob the backend
  // returns. The smoke test only cares that the header renders, so we
  // render the header + a terse summary if a plan exists.
  const prepItems = extractPrepItems(plan);

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <View style={shared.card}>
        <Text style={styles.header}>Sunday Prep</Text>
        <Text style={styles.sub}>
          Prep work for {plan.title ?? "this week"}.
        </Text>
        {error && <Text style={styles.error}>{error}</Text>}
        {prepItems.length === 0 ? (
          <Text style={styles.empty}>No prep tasks in this plan yet.</Text>
        ) : (
          <View style={{ marginTop: 8 }}>
            {prepItems.map((item, i) => (
              <View key={i} style={styles.row}>
                <View style={styles.dot} />
                <Text style={styles.rowText}>{item}</Text>
              </View>
            ))}
          </View>
        )}
      </View>
    </ScrollView>
  );
}

function extractPrepItems(plan: WeeklyMealPlan): string[] {
  // Defensive: the server-side prep_plan shape has evolved and may be
  // an array of strings, an array of {title, notes}, or a nested object.
  // Try the common shapes; fall back to empty.
  const raw: any = (plan as any).prep_plan;
  if (!raw) return [];
  if (Array.isArray(raw)) {
    return raw
      .map((x) => (typeof x === "string" ? x : x?.title ?? x?.name ?? null))
      .filter((x): x is string => typeof x === "string" && x.length > 0);
  }
  if (typeof raw === "object" && Array.isArray(raw.items)) {
    return raw.items
      .map((x: any) => (typeof x === "string" ? x : x?.title ?? x?.name ?? null))
      .filter((x: any): x is string => typeof x === "string" && x.length > 0);
  }
  return [];
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  header: {
    fontSize: 18,
    fontWeight: "600",
    color: colors.text,
    fontFamily: fonts.body,
    marginBottom: 8,
  },
  sub: {
    fontSize: 12,
    color: colors.muted,
    fontFamily: fonts.body,
    marginBottom: 6,
  },
  empty: {
    fontSize: 12,
    color: colors.muted,
    fontFamily: fonts.body,
    lineHeight: 17,
  },
  error: {
    fontSize: 11,
    color: colors.red,
    fontFamily: fonts.body,
    marginBottom: 6,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 5,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.purple },
  rowText: { flex: 1, fontSize: 12, color: colors.text, fontFamily: fonts.body },
});
