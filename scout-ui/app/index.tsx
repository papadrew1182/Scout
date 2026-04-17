import { useEffect, useState } from "react";
import { ScrollView, StyleSheet, Text, View, Pressable } from "react-native";
import { useRouter } from "expo-router";

import { colors, fonts, shared } from "../lib/styles";
import { useIsDesktop } from "../lib/breakpoint";
import {
  fetchCurrentWeeklyPlan,
  fetchGroceryItems,
} from "../lib/api";
import {
  CHORES_TODAY,
  ACTIVITY,
  getMember,
} from "../lib/seedData";
import type { WeeklyMealPlan, GroceryItem } from "../lib/types";

// ---------------------------------------------------------------------------
// TODO: Kids · Today — done-counts are still sourced from seedData (CHORES_TODAY).
//   compute done from task_instances API — e.g. fetchTaskInstances(today)
//   filtered per kid and counted. Left as seed data for now to preserve visual
//   demo while flagging the debt.
//   The TOTAL count could also be read from useFamilyChoreRoutines() once
//   member IDs are aligned between seed and live backend.
//
// TODO: Family activity — still sourced from seedData (ACTIVITY).
//   source activity from action_items API + task_instance completion events.
// ---------------------------------------------------------------------------

const TINT_BG: Record<string, string> = {
  purple: colors.avPurpleBg, teal: colors.avTealBg, amber: colors.avAmberBg, coral: colors.avCoralBg,
};
const TINT_TEXT: Record<string, string> = {
  purple: colors.avPurpleText, teal: colors.avTealText, amber: colors.avAmberText, coral: colors.avCoralText,
};
const ACTIVITY_TINT: Record<string, string> = {
  green: colors.green, purple: colors.purple, amber: colors.amber, teal: colors.teal, red: colors.red,
};

// ---------------------------------------------------------------------------
// Build the 7-day meals grid from a real WeeklyMealPlan
// ---------------------------------------------------------------------------

const DAY_KEYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"] as const;
const DAY_LABELS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"] as const;

function buildMealsWeek(plan: WeeklyMealPlan | null) {
  const today = new Date();
  const monday = new Date(today);
  monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));

  return DAY_KEYS.map((key, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    const isToday = d.toDateString() === today.toDateString();
    const title = plan?.week_plan?.dinners?.[key]?.title ?? null;
    return { day: DAY_LABELS[i], name: title ?? "—", isToday };
  });
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

export default function Dashboard() {
  const router = useRouter();
  const isDesktop = useIsDesktop();

  // ---- Meals · This week — real data via fetchCurrentWeeklyPlan ----
  const [mealPlan, setMealPlan] = useState<WeeklyMealPlan | null>(null);
  const [mealPlanMissing, setMealPlanMissing] = useState(false);

  useEffect(() => {
    fetchCurrentWeeklyPlan()
      .then((plan) => setMealPlan(plan))
      .catch(() => setMealPlanMissing(true));
  }, []);

  const mealsWeek = buildMealsWeek(mealPlan);

  // ---- Grocery preview — real data via fetchGroceryItems ----
  const [groceryItems, setGroceryItems] = useState<GroceryItem[]>([]);
  const [groceryLoaded, setGroceryLoaded] = useState(false);

  useEffect(() => {
    fetchGroceryItems()
      .then((items) => {
        // Top 6 unpurchased items
        setGroceryItems(items.filter((i) => !i.is_purchased).slice(0, 6));
        setGroceryLoaded(true);
      })
      .catch(() => {
        setGroceryItems([]);
        setGroceryLoaded(true);
      });
  }, []);

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <View style={styles.greetRow}>
        <Text style={styles.greetTitle}>Good evening, Andrew</Text>
        <Text style={styles.greetSub}>Wed, Apr 15 · 3 actions need attention</Text>
      </View>

      <View style={styles.statRow}>
        <Stat n="9" label="Chores today" />
        <Stat n="3" label="Completed" />
        <Stat n="2" label="Alerts" tone="amber" />
      </View>

      <View style={[styles.grid2, !isDesktop && styles.grid2Stack]}>
        {/* ---- Kids · Today (done counts from seed; total from seed; TODO: task_instances API) ---- */}
        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Kids · Today</Text>
            <Pressable onPress={() => router.push("/parent")} accessibilityRole="link">
              <Text style={shared.cardAction}>Manage chores</Text>
            </Pressable>
          </View>
          {CHORES_TODAY.map((c) => {
            const m = getMember(c.memberId)!;
            const pct = c.total === 0 ? 0 : Math.round((c.done / c.total) * 100);
            const tone = c.done === c.total ? "green" : c.done === 0 ? "red" : "amber";
            return (
              <View key={c.memberId} style={styles.kidRow}>
                <View style={[styles.av, { backgroundColor: TINT_BG[m.tint] }]}>
                  <Text style={[styles.avText, { color: TINT_TEXT[m.tint] }]}>{m.initials}</Text>
                </View>
                <Text style={styles.kidName}>{m.firstName}</Text>
                <View style={styles.bar}><View style={[styles.barFill, { width: `${pct}%` }]} /></View>
                <Text style={styles.frac}>{c.done}/{c.total}</Text>
                <Tag tone={tone === "green" ? "green" : tone === "red" ? "red" : "amber"}>
                  {tone === "green" ? "Done" : tone === "red" ? "None done" : `${c.total - c.done} left`}
                </Tag>
              </View>
            );
          })}
        </View>

        {/* ---- Meals · This week (real data from fetchCurrentWeeklyPlan) ---- */}
        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Meals · This week</Text>
            <Pressable onPress={() => router.push("/meals/this-week")} accessibilityRole="link">
              <Text style={shared.cardAction}>Full plan</Text>
            </Pressable>
          </View>
          {mealPlanMissing ? (
            <Text style={styles.emptyText}>No plan yet — generate one on Meals.</Text>
          ) : (
            <>
              <View style={styles.mealGrid}>
                {mealsWeek.map((m) => (
                  <View key={m.day} style={styles.mealCol}>
                    <Text style={[styles.mealDay, m.isToday && { color: colors.purple, fontWeight: "700" }]}>{m.day}</Text>
                    <View style={[styles.mealCell, m.isToday && styles.mealCellToday]}>
                      <Text style={[styles.mealName, m.isToday && { color: colors.purpleDeep, fontWeight: "500" }]}>{m.name}</Text>
                    </View>
                  </View>
                ))}
              </View>
              <View style={styles.statRow}>
                <Stat n="7" label="Dinners" />
                <Stat n="4" label="Batch items" />
                <Stat n="2" label="Costco runs" />
              </View>
            </>
          )}
        </View>
      </View>

      <View style={[styles.grid2, !isDesktop && styles.grid2Stack]}>
        {/* ---- Grocery preview (real data from fetchGroceryItems, top 6 unpurchased) ---- */}
        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Grocery · This week</Text>
            <Pressable onPress={() => router.push("/grocery")} accessibilityRole="link">
              <Text style={shared.cardAction}>Full list</Text>
            </Pressable>
          </View>
          {groceryLoaded && groceryItems.length === 0 ? (
            <Text style={styles.emptyText}>No grocery items — add some on the Grocery page.</Text>
          ) : (
            <>
              {/* Group top-6 unpurchased items by category */}
              {Array.from(new Set(groceryItems.map((i) => i.category ?? "Other"))).map((section) => (
                <View key={section}>
                  <Text style={shared.sectionHead}>{section}</Text>
                  {groceryItems
                    .filter((i) => (i.category ?? "Other") === section)
                    .map((i) => (
                      <CheckRow key={i.id} done={i.is_purchased}>{i.title}</CheckRow>
                    ))}
                </View>
              ))}
            </>
          )}
        </View>

        {/* ---- Family activity (seed data — TODO: source from action_items API) ---- */}
        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Family activity</Text>
            <Pressable onPress={() => router.push("/parent")} accessibilityRole="link">
              <Text style={shared.cardAction}>View all</Text>
            </Pressable>
          </View>
          {ACTIVITY.map((a) => (
            <View key={a.id} style={shared.rowDivider}>
              <View style={[styles.dot, { backgroundColor: ACTIVITY_TINT[a.tint] }]} />
              <Text style={styles.activityText}>{a.text}</Text>
              <Text style={styles.activityMeta}>{a.meta}</Text>
            </View>
          ))}
        </View>
      </View>
    </ScrollView>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Stat({ n, label, tone }: { n: string; label: string; tone?: "amber" }) {
  return (
    <View style={styles.stat}>
      <Text style={[styles.statN, tone === "amber" && { color: colors.amber }]}>{n}</Text>
      <Text style={styles.statL}>{label}</Text>
    </View>
  );
}

function Tag({ children, tone }: { children: string; tone: "green" | "amber" | "red" | "purple" | "teal" }) {
  const palette = {
    green:  { bg: colors.greenBg,  fg: colors.greenText },
    amber:  { bg: colors.amberBg,  fg: colors.amberText },
    red:    { bg: colors.redBg,    fg: colors.redText },
    purple: { bg: colors.purpleLight, fg: colors.purpleDeep },
    teal:   { bg: colors.tealBg,   fg: colors.tealText },
  }[tone];
  return (
    <View style={[styles.tag, { backgroundColor: palette.bg }]}>
      <Text style={[styles.tagText, { color: palette.fg }]}>{children}</Text>
    </View>
  );
}

function CheckRow({ done, children }: { done: boolean; children: string }) {
  return (
    <View style={styles.checkRow}>
      <View style={[styles.check, done && styles.checkDone]}>
        {done && <Text style={styles.checkMark}>✓</Text>}
      </View>
      <Text style={styles.checkLabel}>{children}</Text>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  greetRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" },
  greetTitle: { fontSize: 22, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  greetSub: { fontSize: 12, color: colors.muted, fontFamily: fonts.body },

  statRow: { flexDirection: "row", gap: 8 },
  stat: { flex: 1, backgroundColor: colors.bg, borderRadius: 10, padding: 12, alignItems: "center" },
  statN: { fontSize: 22, fontWeight: "700", color: colors.text, fontFamily: fonts.mono },
  statL: { fontSize: 11, color: colors.muted, marginTop: 2, fontFamily: fonts.body },

  grid2: { flexDirection: "row", gap: 12 },
  grid2Stack: { flexDirection: "column" },

  emptyText: { fontSize: 12, color: colors.muted, fontFamily: fonts.body, paddingVertical: 8 },

  kidRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  av: { width: 28, height: 28, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  avText: { fontSize: 11, fontWeight: "600", fontFamily: fonts.body },
  kidName: { fontSize: 13, color: colors.text, minWidth: 56, fontFamily: fonts.body },
  bar: { flex: 1, height: 5, backgroundColor: colors.border, borderRadius: 3, overflow: "hidden" },
  barFill: { height: "100%", backgroundColor: colors.green, borderRadius: 3 },
  frac: { fontSize: 11, color: colors.muted, fontFamily: fonts.mono, minWidth: 28, textAlign: "right" },

  tag: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  tagText: { fontSize: 10, fontWeight: "700", fontFamily: fonts.body },

  mealGrid: { flexDirection: "row", gap: 4, marginBottom: 8 },
  mealCol: { flex: 1, alignItems: "center" },
  mealDay: { fontSize: 9, color: colors.muted, fontWeight: "500", marginBottom: 4, fontFamily: fonts.body },
  mealCell: {
    width: "100%",
    backgroundColor: colors.bg,
    borderRadius: 6,
    padding: 6,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
  },
  mealCellToday: { backgroundColor: colors.purpleLight, borderColor: colors.purpleMid },
  mealName: { fontSize: 10, color: colors.text, fontFamily: fonts.body, textAlign: "center" },

  checkRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 5 },
  check: {
    width: 16, height: 16, borderRadius: 4,
    borderWidth: 1.5, borderColor: colors.border,
    alignItems: "center", justifyContent: "center",
  },
  checkDone: { backgroundColor: colors.green, borderColor: colors.green },
  checkMark: { color: "#FFFFFF", fontSize: 10, fontWeight: "700" },
  checkLabel: { fontSize: 12, color: colors.text, flex: 1, fontFamily: fonts.body },

  dot: { width: 8, height: 8, borderRadius: 4 },
  activityText: { fontSize: 12, color: colors.text, flex: 1, fontFamily: fonts.body },
  activityMeta: { fontSize: 10, color: colors.muted, fontFamily: fonts.body },
});
