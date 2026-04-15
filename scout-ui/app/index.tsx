import { ScrollView, StyleSheet, Text, View } from "react-native";

import { colors, fonts, shared } from "../lib/styles";
import {
  CHORES_TODAY, MEALS_THIS_WEEK, GROCERY, ACTIVITY, getMember,
} from "../lib/seedData";

const TINT_BG: Record<string, string> = {
  purple: colors.avPurpleBg, teal: colors.avTealBg, amber: colors.avAmberBg, coral: colors.avCoralBg,
};
const TINT_TEXT: Record<string, string> = {
  purple: colors.avPurpleText, teal: colors.avTealText, amber: colors.avAmberText, coral: colors.avCoralText,
};
const ACTIVITY_TINT: Record<string, string> = {
  green: colors.green, purple: colors.purple, amber: colors.amber, teal: colors.teal, red: colors.red,
};

export default function Dashboard() {
  // Costco grocery for the dashboard preview (limit to 6 items)
  const previewGrocery = GROCERY[0].items.slice(0, 6);

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

      <View style={styles.grid2}>
        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Kids · Today</Text>
            <Text style={shared.cardAction}>Manage chores</Text>
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

        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Meals · This week</Text>
            <Text style={shared.cardAction}>Full plan</Text>
          </View>
          <View style={styles.mealGrid}>
            {MEALS_THIS_WEEK.map((m) => (
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
        </View>
      </View>

      <View style={styles.grid2}>
        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Grocery · This week</Text>
            <Text style={shared.cardAction}>Full list</Text>
          </View>
          <Text style={shared.sectionHead}>Produce</Text>
          {previewGrocery.filter((i) => i.section === "Produce").map((i) => (
            <CheckRow key={i.name} done={i.done}>{i.name}</CheckRow>
          ))}
          <Text style={shared.sectionHead}>Protein</Text>
          {previewGrocery.filter((i) => i.section === "Protein").map((i) => (
            <CheckRow key={i.name} done={i.done}>{i.name}</CheckRow>
          ))}
        </View>

        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Family activity</Text>
            <Text style={shared.cardAction}>View all</Text>
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
