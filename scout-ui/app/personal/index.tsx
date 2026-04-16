import { ScrollView, StyleSheet, Text, View } from "react-native";

import { colors, fonts, shared } from "../../lib/styles";
import { useIsDesktop } from "../../lib/breakpoint";
import { PERSONAL_TASKS, RECENT_NOTES, BILLS, CALENDAR_EVENTS } from "../../lib/seedData";

const DAYS = [
  { label: "MON", num: 13, dot: false },
  { label: "TUE", num: 14, dot: true },
  { label: "WED", num: 15, today: true },
  { label: "THU", num: 16, dot: false },
  { label: "FRI", num: 17, dot: true },
  { label: "SAT", num: 18, dot: false },
  { label: "SUN", num: 19, dot: false },
] as const;

const DOT_COLOR: Record<string, string> = {
  purple: colors.purple, teal: colors.teal, amber: colors.amber,
};

const BILL_TONE = {
  due:      { dot: colors.red,   text: colors.red },
  upcoming: { dot: colors.amber, text: colors.amber },
  paid:     { dot: colors.green, text: colors.green },
} as const;

export default function Personal() {
  const isDesktop = useIsDesktop();
  const totalDue = BILLS.filter((b) => b.status !== "paid").reduce((s, b) => s + b.amount, 0);

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Andrew's Dashboard</Text>

      <View style={[styles.grid2, !isDesktop && styles.grid2Stack]}>
        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Calendar · This week</Text>
            <Text style={shared.cardAction}> </Text>
          </View>
          <View style={styles.calRow}>
            {DAYS.map((d) => (
              <View key={d.label} style={styles.calDay}>
                <Text style={styles.calLabel}>{d.label}</Text>
                <View style={[styles.calNum, ("today" in d) && styles.calNumToday]}>
                  <Text style={[styles.calNumText, ("today" in d) && styles.calNumTextToday]}>{d.num}</Text>
                </View>
                {("dot" in d) && d.dot && <View style={styles.calDot} />}
              </View>
            ))}
          </View>
          {CALENDAR_EVENTS.map((e) => (
            <View key={e.title} style={shared.rowDivider}>
              <View style={[styles.eventDot, { backgroundColor: DOT_COLOR[e.dot] }]} />
              <Text style={styles.eventTitle}>{e.title}</Text>
              <Text style={styles.eventTime}>{e.time}</Text>
            </View>
          ))}
        </View>

        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Top 5 tasks</Text>
            <Text style={shared.cardAction}> </Text>
          </View>
          {PERSONAL_TASKS.map((t) => (
            <View key={t.title} style={styles.taskRow}>
              <View style={[styles.check, t.done && styles.checkDone]}>
                {t.done && <Text style={styles.checkMark}>✓</Text>}
              </View>
              <Text style={[styles.taskTitle, t.done && { color: colors.muted }]}>{t.title}</Text>
              <TaskTag tone={t.tagTone}>{t.tag}</TaskTag>
            </View>
          ))}
        </View>
      </View>

      <View style={[styles.grid2, !isDesktop && styles.grid2Stack]}>
        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Recent notes</Text>
            <Text style={shared.cardAction}> </Text>
          </View>
          {RECENT_NOTES.map((n) => (
            <View key={n.title} style={styles.noteRow}>
              <Text style={styles.noteTitle}>{n.title}</Text>
              <Text style={styles.notePreview} numberOfLines={2}>{n.preview}</Text>
              <Text style={styles.noteDate}>{n.date}</Text>
            </View>
          ))}
        </View>

        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Bills</Text>
            <Text style={shared.cardAction}> </Text>
          </View>
          {BILLS.map((b) => {
            const tone = BILL_TONE[b.status];
            return (
              <View key={b.name} style={shared.rowDivider}>
                <View style={[styles.eventDot, { backgroundColor: tone.dot }]} />
                <Text style={styles.billName}>{b.name}</Text>
                <Text style={[styles.billAmount, { color: tone.text }]}>
                  ${b.amount.toLocaleString()} · {b.dueLabel}
                </Text>
              </View>
            );
          })}
          <View style={styles.totalBox}>
            <Text style={styles.totalLabel}>Due this month</Text>
            <Text style={styles.totalNum}>${totalDue.toLocaleString()}</Text>
          </View>
        </View>
      </View>
    </ScrollView>
  );
}

function TaskTag({ tone, children }: { tone: "green" | "amber" | "purple" | "muted"; children: string }) {
  const palette = {
    green:  { bg: colors.greenBg,    fg: colors.greenText },
    amber:  { bg: colors.amberBg,    fg: colors.amberText },
    purple: { bg: colors.purpleLight,fg: colors.purpleDeep },
    muted:  { bg: "transparent",     fg: colors.muted },
  }[tone];
  return (
    <View style={[styles.tag, { backgroundColor: palette.bg }]}>
      <Text style={[styles.tagText, { color: palette.fg }]}>{children}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  h1: { fontSize: 22, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  grid2: { flexDirection: "row", gap: 12 },
  grid2Stack: { flexDirection: "column" },

  calRow: { flexDirection: "row", marginBottom: 10 },
  calDay: { flex: 1, alignItems: "center", gap: 4 },
  calLabel: { fontSize: 10, color: colors.muted, fontWeight: "500", fontFamily: fonts.body },
  calNum: { width: 28, height: 28, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  calNumToday: { backgroundColor: colors.purple },
  calNumText: { fontSize: 12, color: colors.text, fontFamily: fonts.body },
  calNumTextToday: { color: "#FFFFFF", fontWeight: "600" },
  calDot: { width: 5, height: 5, borderRadius: 3, backgroundColor: colors.purple },

  eventDot: { width: 8, height: 8, borderRadius: 4 },
  eventTitle: { fontSize: 12, color: colors.text, flex: 1, fontFamily: fonts.body },
  eventTime: { fontSize: 11, color: colors.muted, fontFamily: fonts.body },

  taskRow: {
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
  taskTitle: { fontSize: 12, color: colors.text, flex: 1, fontFamily: fonts.body },
  tag: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  tagText: { fontSize: 10, fontWeight: "700", fontFamily: fonts.body },

  noteRow: { paddingVertical: 7, borderBottomWidth: 1, borderBottomColor: colors.border, gap: 2 },
  noteTitle: { fontSize: 12, fontWeight: "500", color: colors.text, fontFamily: fonts.body },
  notePreview: { fontSize: 11, color: colors.muted, fontFamily: fonts.body, lineHeight: 15 },
  noteDate: { fontSize: 10, color: colors.muted, marginTop: 3, fontFamily: fonts.body },

  billName: { fontSize: 12, color: colors.text, flex: 1, fontFamily: fonts.body },
  billAmount: { fontSize: 11, fontWeight: "500", fontFamily: fonts.body },
  totalBox: {
    marginTop: 10,
    backgroundColor: colors.bg,
    borderRadius: 8,
    padding: 10,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  totalLabel: { fontSize: 12, color: colors.muted, fontFamily: fonts.body },
  totalNum: { fontSize: 16, fontWeight: "600", color: colors.text, fontFamily: fonts.mono },
});
