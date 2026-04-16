import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { colors, fonts, shared } from "../../lib/styles";
import { useIsDesktop } from "../../lib/breakpoint";
import { MEALS_THIS_WEEK, BATCH_COOK, FAMILY } from "../../lib/seedData";
import { approveWeeklyPlan, fetchCurrentWeeklyPlan } from "../../lib/api";
import type { WeeklyMealPlan } from "../../lib/types";

const TINT_BG: Record<string, string> = {
  purple: colors.avPurpleBg, teal: colors.avTealBg, amber: colors.avAmberBg, coral: colors.avCoralBg,
};
const TINT_TEXT: Record<string, string> = {
  purple: colors.avPurpleText, teal: colors.avTealText, amber: colors.avAmberText, coral: colors.avCoralText,
};

const DIETARY_TONE: Record<string, "purple" | "green" | "amber"> = {
  "No restrictions": "purple",
  "Vegetarian-lean": "green",
  "No onions":       "amber",
};

export default function MealsThisWeek() {
  const isDesktop = useIsDesktop();
  const [plan, setPlan] = useState<WeeklyMealPlan | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const load = async () => {
    try {
      const p = await fetchCurrentWeeklyPlan();
      setPlan(p);
    } catch {
      setPlan(null);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleApprove = async () => {
    if (!plan || busy) return;
    setBusy(true);
    setMsg(null);
    try {
      await approveWeeklyPlan(plan.id);
      setMsg("Plan approved");
      await load();
    } catch (e: any) {
      setMsg(e?.message ?? "Approve failed");
    } finally {
      setBusy(false);
    }
  };

  const canApprove = plan && plan.status !== "approved";

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      {canApprove && (
        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>{plan?.title ?? "Current plan"}</Text>
            <Text style={shared.cardAction}>{plan?.status ?? ""}</Text>
          </View>
          <Pressable
            style={[styles.approveBtn, busy && styles.approveBtnDisabled]}
            onPress={handleApprove}
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel="Approve Plan"
          >
            <Text style={styles.approveBtnText}>{busy ? "Approving…" : "Approve Plan"}</Text>
          </Pressable>
          {msg && <Text style={styles.planMsg}>{msg}</Text>}
        </View>
      )}
      {!canApprove && msg && (
        <View style={shared.card}>
          <Text style={styles.planMsg}>{msg}</Text>
        </View>
      )}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Week of Apr 13–19</Text>
          <Text style={shared.cardAction}>Edit plan</Text>
        </View>
        <View style={styles.weekGrid}>
          {MEALS_THIS_WEEK.map((m) => (
            <View key={m.day} style={styles.dayCol}>
              <Text style={[styles.dayLabel, m.isToday && { color: colors.purple, fontWeight: "700" }]}>{m.day}</Text>
              <View style={[styles.cell, m.isToday && styles.cellToday]}>
                <Text style={[styles.cellName, m.isToday && { color: colors.purpleDeep, fontWeight: "500" }]}>{m.name}</Text>
              </View>
              <Text style={[styles.cellNote, m.isToday && { color: colors.purple }]}>{m.note}</Text>
            </View>
          ))}
        </View>
      </View>

      <View style={[styles.grid2, !isDesktop && styles.grid2Stack]}>
        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Sunday batch cook</Text>
            <Text style={shared.cardAction}>Edit</Text>
          </View>
          {BATCH_COOK.map((b) => (
            <View key={b.name} style={styles.batchRow}>
              <View style={[styles.check, b.done && styles.checkDone]}>
                {b.done && <Text style={styles.checkMark}>✓</Text>}
              </View>
              <Text style={[styles.batchName, b.done && { color: colors.muted, textDecorationLine: "line-through" }]}>{b.name}</Text>
              <Text style={styles.batchTime}>{b.minutes} min</Text>
            </View>
          ))}
        </View>

        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Dietary notes</Text>
            <Text style={shared.cardAction}>Edit</Text>
          </View>
          {FAMILY.slice(0, 5).map((m) => {
            const tone = DIETARY_TONE[m.dietary ?? "No restrictions"] ?? "purple";
            const palette = {
              purple: { bg: colors.purpleLight, fg: colors.purpleDeep },
              green:  { bg: colors.greenBg,     fg: colors.greenText },
              amber:  { bg: colors.amberBg,     fg: colors.amberText },
            }[tone];
            return (
              <View key={m.id} style={styles.dietRow}>
                <View style={[styles.av, { backgroundColor: TINT_BG[m.tint] }]}>
                  <Text style={[styles.avText, { color: TINT_TEXT[m.tint] }]}>{m.initials}</Text>
                </View>
                <Text style={styles.dietName}>{m.firstName}</Text>
                <View style={[styles.tag, { backgroundColor: palette.bg }]}>
                  <Text style={[styles.tagText, { color: palette.fg }]}>{m.dietary}</Text>
                </View>
              </View>
            );
          })}
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  weekGrid: { flexDirection: "row", gap: 6, marginTop: 4 },
  dayCol: { flex: 1, alignItems: "center", gap: 4 },
  dayLabel: { fontSize: 10, color: colors.muted, fontWeight: "500", fontFamily: fonts.body },
  cell: {
    width: "100%",
    backgroundColor: colors.bg,
    borderRadius: 7,
    padding: 8,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
  },
  cellToday: { backgroundColor: colors.purpleLight, borderColor: colors.purpleMid },
  cellName: { fontSize: 11, color: colors.text, fontFamily: fonts.body, textAlign: "center" },
  cellNote: { fontSize: 10, color: colors.muted, fontFamily: fonts.body },

  grid2: { flexDirection: "row", gap: 12 },
  grid2Stack: { flexDirection: "column" },

  batchRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  check: { width: 16, height: 16, borderRadius: 4, borderWidth: 1.5, borderColor: colors.border, alignItems: "center", justifyContent: "center" },
  checkDone: { backgroundColor: colors.green, borderColor: colors.green },
  checkMark: { color: "#FFFFFF", fontSize: 10, fontWeight: "700" },
  batchName: { flex: 1, fontSize: 12, color: colors.text, fontFamily: fonts.body },
  batchTime: { fontSize: 11, color: colors.muted, fontFamily: fonts.body },

  dietRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  av: { width: 28, height: 28, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  avText: { fontSize: 11, fontWeight: "600", fontFamily: fonts.body },
  dietName: { flex: 1, fontSize: 12, color: colors.text, fontFamily: fonts.body },
  tag: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  tagText: { fontSize: 10, fontWeight: "700", fontFamily: fonts.body },

  approveBtn: {
    backgroundColor: colors.purple,
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
  },
  approveBtnDisabled: { backgroundColor: colors.border },
  approveBtnText: { color: "#FFFFFF", fontSize: 13, fontWeight: "600", fontFamily: fonts.body },
  planMsg: {
    fontSize: 12,
    color: colors.green,
    fontFamily: fonts.body,
    textAlign: "center",
    marginTop: 8,
  },
});
