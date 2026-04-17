import { useEffect, useMemo, useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { colors, fonts, shared } from "../../lib/styles";
import { useIsDesktop } from "../../lib/breakpoint";
import { useAuth } from "../../lib/auth";
import {
  fetchTopPersonalTasks,
  fetchRecentNotes,
  fetchUnpaidBills,
  fetchEvents,
} from "../../lib/api";
import type { PersonalTask, Note, Bill, Event } from "../../lib/types";

// ---------------------------------------------------------------------------
// Avatar / dot colour maps
// ---------------------------------------------------------------------------

const DOT_COLOR: Record<string, string> = {
  purple: colors.purple, teal: colors.teal, amber: colors.amber,
};

const BILL_TONE = {
  due:      { dot: colors.red,   text: colors.red },
  upcoming: { dot: colors.amber, text: colors.amber },
  paid:     { dot: colors.green, text: colors.green },
} as const;

// ---------------------------------------------------------------------------
// Week helpers
// ---------------------------------------------------------------------------

/**
 * Returns ISO date strings for the start (Monday) and end (Sunday) of the
 * week containing today.
 */
function currentWeekRange(): { start: string; end: string } {
  const today = new Date();
  const monday = new Date(today);
  monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);

  const fmt = (d: Date) => d.toISOString().split("T")[0];
  return { start: fmt(monday), end: fmt(sunday) };
}

/**
 * Returns the 7-day grid for the calendar week strip, marking today.
 */
function buildCalendarDays() {
  const today = new Date();
  const monday = new Date(today);
  monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));

  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return {
      label: (["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"] as const)[i],
      num: d.getDate(),
      isToday: d.toDateString() === today.toDateString(),
    };
  });
}

// ---------------------------------------------------------------------------
// Format helpers
// ---------------------------------------------------------------------------

function formatEventTime(event: Event): string {
  if (event.all_day) return "All day";
  try {
    return new Date(event.starts_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function formatNoteDate(note: Note): string {
  try {
    return new Date(note.updated_at).toLocaleDateString([], { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

function formatBillDue(bill: Bill): string {
  try {
    return new Date(bill.due_date).toLocaleDateString([], { month: "short", day: "numeric" });
  } catch {
    return bill.due_date;
  }
}

function billStatus(bill: Bill): "due" | "upcoming" | "paid" {
  if (bill.status === "paid") return "paid";
  try {
    const due = new Date(bill.due_date);
    const now = new Date();
    const diffDays = Math.ceil((due.getTime() - now.getTime()) / 86_400_000);
    return diffDays <= 3 ? "due" : "upcoming";
  } catch {
    return "upcoming";
  }
}

function taskPriority(task: PersonalTask): "green" | "amber" | "purple" | "muted" {
  if (task.status === "done" || task.completed_at) return "green";
  switch (task.priority) {
    case "high":   return "amber";
    case "medium": return "purple";
    default:       return "muted";
  }
}

function taskPriorityLabel(task: PersonalTask): string {
  if (task.status === "done" || task.completed_at) return "Done";
  switch (task.priority) {
    case "high":   return "High";
    case "medium": return "Medium";
    default:       return task.priority ?? "—";
  }
}

// ---------------------------------------------------------------------------
// Personal
// ---------------------------------------------------------------------------

export default function Personal() {
  const isDesktop = useIsDesktop();
  const { member } = useAuth();
  const memberId = member?.member_id ?? null;

  // ---- Calendar days (derived dynamically from today's date) ----
  const calDays = useMemo(() => buildCalendarDays(), []);

  // ---- Calendar events — real data from fetchEvents for current week ----
  const [events, setEvents] = useState<Event[]>([]);

  useEffect(() => {
    const { start, end } = currentWeekRange();
    fetchEvents(start, end)
      .then((evts) => setEvents(evts))
      .catch(() => setEvents([]));
  }, []);

  // ---- Top 5 tasks — real data from fetchTopPersonalTasks ----
  const [tasks, setTasks] = useState<PersonalTask[]>([]);

  useEffect(() => {
    if (!memberId) return;
    fetchTopPersonalTasks(memberId, 5)
      .then((t) => setTasks(t))
      .catch(() => setTasks([]));
  }, [memberId]);

  // ---- Recent notes — real data from fetchRecentNotes ----
  const [notes, setNotes] = useState<Note[]>([]);

  useEffect(() => {
    if (!memberId) return;
    fetchRecentNotes(memberId, 10)
      .then((n) => setNotes(n))
      .catch(() => setNotes([]));
  }, [memberId]);

  // ---- Bills — real data from fetchUnpaidBills ----
  const [bills, setBills] = useState<Bill[]>([]);

  useEffect(() => {
    fetchUnpaidBills()
      .then((b) => setBills(b))
      .catch(() => setBills([]));
  }, []);

  const totalDue = bills.reduce((s, b) => s + b.amount_cents / 100, 0);

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>
        {member?.first_name ? `${member.first_name}'s Dashboard` : "My Dashboard"}
      </Text>

      <View style={[styles.grid2, !isDesktop && styles.grid2Stack]}>
        {/* ---- Calendar · This week ---- */}
        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Calendar · This week</Text>
            <Text style={shared.cardAction}> </Text>
          </View>
          <View style={styles.calRow}>
            {calDays.map((d) => (
              <View key={d.label} style={styles.calDay}>
                <Text style={styles.calLabel}>{d.label}</Text>
                <View style={[styles.calNum, d.isToday && styles.calNumToday]}>
                  <Text style={[styles.calNumText, d.isToday && styles.calNumTextToday]}>{d.num}</Text>
                </View>
                {/* Show dot if there's any event on this weekday */}
                {events.some((e) => {
                  try {
                    const evtDay = new Date(e.starts_at).getDay();
                    // d.label index → JS getDay: MON=1,TUE=2,WED=3,THU=4,FRI=5,SAT=6,SUN=0
                    const labelToJS: Record<string, number> = {
                      MON: 1, TUE: 2, WED: 3, THU: 4, FRI: 5, SAT: 6, SUN: 0,
                    };
                    return evtDay === labelToJS[d.label];
                  } catch { return false; }
                }) && <View style={styles.calDot} />}
              </View>
            ))}
          </View>
          {events.length === 0 ? (
            <Text style={styles.emptyText}>No events this week.</Text>
          ) : (
            events.slice(0, 5).map((e) => (
              <View key={e.id} style={shared.rowDivider}>
                <View style={[styles.eventDot, { backgroundColor: colors.purple }]} />
                <Text style={styles.eventTitle}>{e.title}</Text>
                <Text style={styles.eventTime}>{formatEventTime(e)}</Text>
              </View>
            ))
          )}
        </View>

        {/* ---- Top 5 tasks ---- */}
        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Top 5 tasks</Text>
            <Text style={shared.cardAction}> </Text>
          </View>
          {tasks.length === 0 ? (
            <Text style={styles.emptyText}>No tasks — you're all caught up!</Text>
          ) : (
            tasks.map((t) => {
              const done = !!(t.status === "done" || t.completed_at);
              return (
                <View key={t.id} style={styles.taskRow}>
                  <View style={[styles.check, done && styles.checkDone]}>
                    {done && <Text style={styles.checkMark}>✓</Text>}
                  </View>
                  <Text style={[styles.taskTitle, done && { color: colors.muted }]}>{t.title}</Text>
                  <TaskTag tone={taskPriority(t)}>{taskPriorityLabel(t)}</TaskTag>
                </View>
              );
            })
          )}
        </View>
      </View>

      <View style={[styles.grid2, !isDesktop && styles.grid2Stack]}>
        {/* ---- Recent notes ---- */}
        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Recent notes</Text>
            <Text style={shared.cardAction}> </Text>
          </View>
          {notes.length === 0 ? (
            <Text style={styles.emptyText}>No notes yet.</Text>
          ) : (
            notes.map((n) => (
              <View key={n.id} style={styles.noteRow}>
                <Text style={styles.noteTitle}>{n.title}</Text>
                <Text style={styles.notePreview} numberOfLines={2}>{n.body}</Text>
                <Text style={styles.noteDate}>{formatNoteDate(n)}</Text>
              </View>
            ))
          )}
        </View>

        {/* ---- Bills ---- */}
        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Bills</Text>
            <Text style={shared.cardAction}> </Text>
          </View>
          {bills.length === 0 ? (
            <Text style={styles.emptyText}>No unpaid bills.</Text>
          ) : (
            bills.map((b) => {
              const status = billStatus(b);
              const tone = BILL_TONE[status];
              return (
                <View key={b.id} style={shared.rowDivider}>
                  <View style={[styles.eventDot, { backgroundColor: tone.dot }]} />
                  <Text style={styles.billName}>{b.title}</Text>
                  <Text style={[styles.billAmount, { color: tone.text }]}>
                    ${(b.amount_cents / 100).toLocaleString()} · {formatBillDue(b)}
                  </Text>
                </View>
              );
            })
          )}
          {bills.length > 0 && (
            <View style={styles.totalBox}>
              <Text style={styles.totalLabel}>Due this month</Text>
              <Text style={styles.totalNum}>${totalDue.toLocaleString()}</Text>
            </View>
          )}
        </View>
      </View>
    </ScrollView>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  h1: { fontSize: 22, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  grid2: { flexDirection: "row", gap: 12 },
  grid2Stack: { flexDirection: "column" },

  emptyText: { fontSize: 12, color: colors.muted, fontFamily: fonts.body, paddingVertical: 8 },

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
