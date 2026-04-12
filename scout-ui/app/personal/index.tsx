import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { DEV_MODE } from "../../lib/config";
import { useAuth } from "../../lib/auth";
import { NeedSomething as NeedSomethingWidget } from "../../components/NeedSomething";
import { shared, colors } from "../../lib/styles";
import {
  fetchEvents,
  fetchMembers,
  fetchRecentNotes,
  fetchTaskInstances,
  fetchTopPersonalTasks,
  fetchUnpaidBills,
  ingestGoogleCalendar,
  ingestYnabBill,
} from "../../lib/api";
import { todayStr, formatEventTime, formatDueAt, formatDueDate, sourceLabel } from "../../lib/format";
import type {
  Bill,
  Event,
  FamilyMember,
  Note,
  PersonalTask,
  TaskInstance,
} from "../../lib/types";

interface CollapsibleProps {
  title: string;
  defaultOpen: boolean;
  children: React.ReactNode;
}

function Collapsible({ title, defaultOpen, children }: CollapsibleProps) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <View style={styles.panel}>
      <Pressable style={styles.panelHeader} onPress={() => setOpen(!open)}>
        <Text style={styles.panelTitle}>{title}</Text>
        <Text style={styles.panelChevron}>{open ? "−" : "+"}</Text>
      </Pressable>
      {open && <View style={styles.panelBody}>{children}</View>}
    </View>
  );
}

// ============================================================================
// Today — Priority Layer
// ============================================================================

interface PriorityItem {
  id: string;
  type: "task" | "event" | "bill";
  title: string;
  subtitle: string;
  priority: "urgent" | "high" | "normal";  // visual styling only
  sortRank: number;                         // ordering only
  timestamp: number;
}

// sortRank values — higher sorts first
// Decoupled from visual priority so overdue bills can show red but sort below imminent events.
const SORT_RANK = {
  URGENT_TASK:     60,  // 1. urgent tasks due today
  HIGH_TASK:       50,  // 2. high tasks due within 48h
  IMMINENT_EVENT:  40,  // 3. events within 6 hours
  OVERDUE_BILL:    30,  // 4. overdue bills
  NORMAL_EVENT:    20,  // 5. events within 24h
  UPCOMING_BILL:   10,  // 6. upcoming bills within 7d
} as const;

function priorityColor(p: string): string {
  switch (p) {
    case "urgent": return colors.negative;
    case "high": return colors.warning;
    default: return colors.textMuted;
  }
}

/** Format an event start time with day-relative context. */
function formatEventSubtitle(iso: string, allDay: boolean): string {
  const d = new Date(iso);
  const now = new Date();
  const todayDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const tomorrowDate = new Date(todayDate.getTime() + 24 * 60 * 60 * 1000);
  const eventDate = new Date(d.getFullYear(), d.getMonth(), d.getDate());

  const timeStr = allDay
    ? "all day"
    : d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

  if (eventDate.getTime() === todayDate.getTime()) {
    return allDay ? "Today — all day" : `Today at ${timeStr}`;
  }
  if (eventDate.getTime() === tomorrowDate.getTime()) {
    return allDay ? "Tomorrow — all day" : `Tomorrow at ${timeStr}`;
  }
  const weekday = d.toLocaleDateString([], { weekday: "long" });
  return allDay ? `${weekday} — all day` : `${weekday} at ${timeStr}`;
}

function TodayCard() {
  const { member: authMember } = useAuth();
  const myId = authMember?.member_id ?? "";
  const [items, setItems] = useState<PriorityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const todayEnd = new Date(todayStart.getTime() + 24 * 60 * 60 * 1000 - 1);
    const in6h = new Date(now.getTime() + 6 * 60 * 60 * 1000);
    const in24h = new Date(now.getTime() + 24 * 60 * 60 * 1000);
    const in48h = new Date(now.getTime() + 48 * 60 * 60 * 1000);
    const in7d = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
    const todayDateStr = todayStart.toISOString().split("T")[0];

    Promise.all([
      fetchTopPersonalTasks(myId, 20),
      fetchEvents(now.toISOString(), in24h.toISOString()),
      fetchUnpaidBills(),
    ])
      .then(([tasks, events, bills]) => {
        const merged: PriorityItem[] = [];

        // 1. Urgent tasks due today
        // 2. High tasks due within 48h
        for (const t of tasks) {
          if (t.status === "done" || t.status === "cancelled") continue;
          const dueTs = t.due_at ? new Date(t.due_at).getTime() : null;
          const dueDate = t.due_at ? t.due_at.split("T")[0] : null;

          if (t.priority === "urgent" && dueDate === todayDateStr) {
            merged.push({
              id: `task-${t.id}`,
              type: "task",
              title: t.title,
              subtitle: "Due today",
              priority: "urgent",
              sortRank: SORT_RANK.URGENT_TASK,
              timestamp: dueTs ?? todayEnd.getTime(),
            });
          } else if (t.priority === "high" && dueTs && dueTs <= in48h.getTime()) {
            const isToday = dueDate === todayDateStr;
            merged.push({
              id: `task-${t.id}`,
              type: "task",
              title: t.title,
              subtitle: isToday ? "Due today" : formatDueAt(t.due_at) ?? "Due soon",
              priority: "high",
              sortRank: SORT_RANK.HIGH_TASK,
              timestamp: dueTs,
            });
          }
        }

        // 3. Events within 24 hours (split into imminent vs normal)
        for (const e of events) {
          if (e.is_cancelled) continue;
          const startTs = new Date(e.starts_at).getTime();
          if (startTs > in24h.getTime()) continue;

          const isImminent = startTs <= in6h.getTime();
          merged.push({
            id: `event-${e.id}`,
            type: "event",
            title: e.title,
            subtitle: formatEventSubtitle(e.starts_at, e.all_day),
            priority: isImminent ? "high" : "normal",
            sortRank: isImminent ? SORT_RANK.IMMINENT_EVENT : SORT_RANK.NORMAL_EVENT,
            timestamp: startTs,
          });
        }

        // 4. Overdue bills
        for (const b of bills) {
          const dueDate = new Date(b.due_date + "T00:00:00");
          if (dueDate < todayStart && b.status !== "paid") {
            merged.push({
              id: `bill-${b.id}`,
              type: "bill",
              title: b.title,
              subtitle: `Overdue — was due ${formatDueDate(b.due_date)}`,
              priority: "urgent",
              sortRank: SORT_RANK.OVERDUE_BILL,
              timestamp: dueDate.getTime(),
            });
          }
        }

        // 5. Upcoming bills (next 7 days) — fallback to fill
        if (merged.length < 5) {
          for (const b of bills) {
            if (merged.some((m) => m.id === `bill-${b.id}`)) continue;
            const dueDate = new Date(b.due_date + "T00:00:00");
            if (dueDate >= todayStart && dueDate <= in7d) {
              merged.push({
                id: `bill-${b.id}`,
                type: "bill",
                title: b.title,
                subtitle: `Due ${formatDueDate(b.due_date)}`,
                priority: "normal",
                sortRank: SORT_RANK.UPCOMING_BILL,
                timestamp: dueDate.getTime(),
              });
            }
          }
        }

        // Sort: sortRank desc, then timestamp asc
        merged.sort((a, b) => {
          if (a.sortRank !== b.sortRank) return b.sortRank - a.sortRank;
          return a.timestamp - b.timestamp;
        });

        setItems(merged.slice(0, 5));
      })
      .catch((e) => setError(e.message ?? "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  const primary = items.length > 0 ? items[0] : null;
  const secondary = items.slice(1);

  return (
    <View style={styles.todayCard}>
      <Text style={styles.todayTitle}>Today</Text>
      {loading && (
        <ActivityIndicator size="small" color={colors.accent} style={styles.spinner} />
      )}
      {!loading && error && <Text style={styles.errorText}>{error}</Text>}
      {!loading && !error && !primary && (
        <Text style={styles.todayEmpty}>No critical items today</Text>
      )}

      {/* ---- Context line ---- */}
      {!loading && !error && items.length > 0 && (
        <Text style={styles.todayContext}>
          {items.length === 1
            ? "1 item needs attention"
            : `${items.length} items need attention`}
        </Text>
      )}

      {/* ---- Primary Focus ---- */}
      {!loading && !error && primary && (
        <View style={[styles.primaryCard, { borderLeftColor: priorityColor(primary.priority) }]}>
          <Text style={styles.primaryTitle}>{primary.title}</Text>
          <Text style={styles.primarySub}>{primary.subtitle}</Text>
          {secondary.length > 0 && (
            <Text style={styles.nextUpLine}>Next up: {secondary[0].title}</Text>
          )}
        </View>
      )}

      {/* ---- Secondary Items ---- */}
      {!loading && !error && secondary.length > 0 && (
        <View style={styles.secondaryList}>
          {secondary.map((item) => (
            <View key={item.id} style={styles.secondaryRow}>
              <View style={[styles.todayDot, { backgroundColor: priorityColor(item.priority) }]} />
              <View style={styles.todayContent}>
                <Text style={styles.secondaryTitle}>{item.title}</Text>
                <Text style={styles.secondarySub}>{item.subtitle}</Text>
              </View>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

// ============================================================================
// Combined Calendar (REAL) — next 3 days
// ============================================================================

function CalendarCard() {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const now = new Date();
    const horizon = new Date();
    horizon.setDate(horizon.getDate() + 3);
    const startISO = now.toISOString();
    const endISO = horizon.toISOString();

    fetchEvents(startISO, endISO)
      .then((data) => {
        const upcoming = data
          .filter((e) => !e.is_cancelled)
          .sort(
            (a, b) =>
              new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime()
          );
        setEvents(upcoming);
      })
      .catch((e) => setError(e.message ?? "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <View style={styles.card}>
      <Text style={styles.cardTitleSpaced}>Combined Calendar</Text>
      {loading && (
        <ActivityIndicator size="small" color={colors.accent} style={styles.spinner} />
      )}
      {!loading && error && <Text style={styles.errorText}>{error}</Text>}
      {!loading && !error && events.length === 0 && (
        <Text style={styles.emptyText}>No upcoming events</Text>
      )}
      {!loading && !error && events.length > 0 && (
        <View style={styles.itemList}>
          {events.map((e) => (
            <View key={e.id} style={styles.calendarRow}>
              <Text style={styles.calendarTime}>
                {formatEventTime(e.starts_at, e.all_day)}
              </Text>
              <View style={styles.calendarMain}>
                <Text style={styles.itemTitle}>{e.title}</Text>
                {sourceLabel(e.source) && (
                  <Text style={styles.calendarSource}>{sourceLabel(e.source)}</Text>
                )}
              </View>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

// ============================================================================
// Top 5 Tasks (REAL)
// ============================================================================

function TopTasksCard() {
  const { member: authMember } = useAuth();
  const myId = authMember?.member_id ?? "";
  const [tasks, setTasks] = useState<PersonalTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTopPersonalTasks(myId, 5)
      .then(setTasks)
      .catch((e) => setError(e.message ?? "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <View style={styles.card}>
      <Text style={styles.cardTitleSpaced}>Top 5 Tasks</Text>
      {loading && (
        <ActivityIndicator size="small" color={colors.accent} style={styles.spinner} />
      )}
      {!loading && error && <Text style={styles.errorText}>{error}</Text>}
      {!loading && !error && tasks.length === 0 && (
        <Text style={styles.emptyText}>No tasks right now</Text>
      )}
      {!loading && !error && tasks.length > 0 && (
        <View style={styles.itemList}>
          {tasks.map((t) => {
            const due = formatDueAt(t.due_at);
            return (
              <View key={t.id} style={styles.taskRow}>
                <View style={[styles.taskDot, { backgroundColor: priorityStyle(t.priority).color }]} />
                <View style={styles.taskMain}>
                  <Text style={styles.itemTitle}>{t.title}</Text>
                  {due && <Text style={styles.itemMeta}>by {due}</Text>}
                </View>
              </View>
            );
          })}
        </View>
      )}
    </View>
  );
}

function priorityStyle(priority: string) {
  switch (priority) {
    case "urgent":
      return { color: colors.negative };
    case "high":
      return { color: colors.warning };
    case "medium":
      return { color: colors.accent };
    default:
      return { color: colors.textMuted };
  }
}

// ============================================================================
// Scout panel (KEEP)
// ============================================================================

interface ScoutSnapshot {
  totalMembers: number;
  childCount: number;
  totalTasks: number;
  completedTasks: number;
  kidsWithIncomplete: string[];
}

function ScoutPanelBody() {
  const [snapshot, setSnapshot] = useState<ScoutSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [members, tasks] = await Promise.all([
        fetchMembers(),
        fetchTaskInstances(todayStr()),
      ]);

      const children = members.filter(
        (m: FamilyMember) => m.role === "child" && m.is_active
      );

      const totalTasks = tasks.length;
      const completedTasks = tasks.filter(
        (t: TaskInstance) => t.is_completed || t.override_completed
      ).length;

      const kidsWithIncomplete: string[] = [];
      for (const child of children) {
        const childTasks = tasks.filter(
          (t: TaskInstance) => t.family_member_id === child.id
        );
        const hasIncomplete = childTasks.some(
          (t: TaskInstance) => !(t.is_completed || t.override_completed)
        );
        if (hasIncomplete) kidsWithIncomplete.push(child.first_name);
      }

      setSnapshot({
        totalMembers: members.length,
        childCount: children.length,
        totalTasks,
        completedTasks,
        kidsWithIncomplete,
      });
    } catch (e: any) {
      setError(e.message ?? "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <ActivityIndicator size="small" color={colors.accent} />;
  if (error) return <Text style={styles.errorText}>{error}</Text>;
  if (!snapshot) return <Text style={styles.emptyText}>No data available</Text>;

  const incompleteLine =
    snapshot.kidsWithIncomplete.length === 0
      ? "All kids are done for today"
      : `Still working: ${snapshot.kidsWithIncomplete.join(", ")}`;

  return (
    <View>
      <View style={styles.statRow}>
        <Text style={styles.statLabel}>Family members</Text>
        <Text style={styles.statValue}>{snapshot.totalMembers}</Text>
      </View>
      <View style={styles.statRow}>
        <Text style={styles.statLabel}>Children</Text>
        <Text style={styles.statValue}>{snapshot.childCount}</Text>
      </View>
      <View style={styles.statRow}>
        <Text style={styles.statLabel}>Tasks today</Text>
        <Text style={styles.statValue}>{snapshot.totalTasks}</Text>
      </View>
      <View style={styles.statRow}>
        <Text style={styles.statLabel}>Completed today</Text>
        <Text style={styles.statValue}>
          {snapshot.completedTasks}
          <Text style={styles.statValueMuted}>/{snapshot.totalTasks}</Text>
        </Text>
      </View>
      <Text style={styles.incompleteLine}>{incompleteLine}</Text>

      <FinanceSnapshot />
    </View>
  );
}

// ============================================================================
// Finance snapshot (REAL) — embedded in Scout panel
// ============================================================================

function FinanceSnapshot() {
  const [bills, setBills] = useState<Bill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchUnpaidBills()
      .then(setBills)
      .catch((e) => setError(e.message ?? "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <View style={styles.financeBlock}>
        <Text style={styles.financeLabel}>Bills</Text>
        <ActivityIndicator size="small" color={colors.accent} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.financeBlock}>
        <Text style={styles.financeLabel}>Bills</Text>
        <Text style={styles.errorText}>{error}</Text>
      </View>
    );
  }

  if (bills.length === 0) {
    return (
      <View style={styles.financeBlock}>
        <Text style={styles.financeLabel}>Bills</Text>
        <Text style={styles.emptyText}>No unpaid bills</Text>
      </View>
    );
  }

  // bills are already sorted by due_date asc from the backend
  const next = bills[0];
  return (
    <View style={styles.financeBlock}>
      <Text style={styles.financeLabel}>Bills</Text>
      <View style={styles.statRow}>
        <Text style={styles.statLabel}>Unpaid</Text>
        <Text style={styles.statValue}>{bills.length}</Text>
      </View>
      <View style={styles.statRow}>
        <Text style={styles.statLabel} numberOfLines={1}>
          Next: {next.title}
        </Text>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
          {sourceLabel(next.source) && (
            <Text style={styles.itemBadge}>{sourceLabel(next.source)}</Text>
          )}
          <Text style={styles.statValueMuted}>{formatDueDate(next.due_date)}</Text>
        </View>
      </View>
    </View>
  );
}

// ============================================================================
// Notes snapshot (REAL) — Andrew's 3 most recent notes
// ============================================================================

function NotesCard() {
  const { member: authMember } = useAuth();
  const myId = authMember?.member_id ?? "";
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRecentNotes(myId, 3)
      .then(setNotes)
      .catch((e) => setError(e.message ?? "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <View style={styles.card}>
      <Text style={styles.cardTitleSpaced}>Recent Notes</Text>
      {loading && (
        <ActivityIndicator size="small" color={colors.accent} style={styles.spinner} />
      )}
      {!loading && error && <Text style={styles.errorText}>{error}</Text>}
      {!loading && !error && notes.length === 0 && (
        <Text style={styles.emptyText}>No recent notes</Text>
      )}
      {!loading && !error && notes.length > 0 && (
        <View style={styles.itemList}>
          {notes.map((n) => (
            <View key={n.id} style={styles.noteRow}>
              <Text style={styles.noteBullet}>•</Text>
              <Text style={styles.noteTitle}>{n.title}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

// ============================================================================
// Dev Tools (operator-only ingestion triggers)
// ============================================================================

function DevToolsPanel({ onIngested }: { onIngested: () => void }) {
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleGcal = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const now = new Date();
      const start = new Date(now.getTime() + 2 * 60 * 60 * 1000);
      const end = new Date(start.getTime() + 60 * 60 * 1000);
      await ingestGoogleCalendar({
        external_id: `gcal_dev_${Date.now()}`,
        title: "Synced Meeting",
        description: "Ingested via Dev Tools",
        starts_at: start.toISOString(),
        ends_at: end.toISOString(),
      });
      const time = new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
      setMsg(`Google event ingested at ${time} — check Calendar`);
      onIngested();
    } catch (e: any) {
      setMsg(`Google ingest failed: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleYnab = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const due = new Date();
      due.setDate(due.getDate() + 7);
      const dueStr = due.toISOString().split("T")[0];
      await ingestYnabBill({
        external_id: `ynab_dev_${Date.now()}`,
        title: "Synced Bill",
        description: "Ingested via Dev Tools",
        amount_cents: 4999,
        due_date: dueStr,
      });
      const time = new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
      setMsg(`YNAB bill ingested at ${time} — check Bills`);
      onIngested();
    } catch (e: any) {
      setMsg(`YNAB ingest failed: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.devCard}>
      <Text style={styles.devLabel}>Integrations (Dev)</Text>
      <View style={styles.devButtons}>
        <Pressable
          style={styles.devButton}
          onPress={handleGcal}
          disabled={busy}
        >
          <Text style={styles.devButtonText}>
            {busy ? "..." : "Ingest Google Calendar"}
          </Text>
        </Pressable>
        <Pressable
          style={styles.devButton}
          onPress={handleYnab}
          disabled={busy}
        >
          <Text style={styles.devButtonText}>
            {busy ? "..." : "Ingest YNAB Bills"}
          </Text>
        </Pressable>
      </View>
      {msg && <Text style={styles.devMsg}>{msg}</Text>}
    </View>
  );
}

// ============================================================================
// Page
// ============================================================================

export default function PersonalDashboard() {
  const { member } = useAuth();
  const [refreshKey, setRefreshKey] = useState(0);
  const handleIngested = () => setRefreshKey((k) => k + 1);
  const myId = member?.member_id ?? "";
  const myName = member?.first_name ?? "";

  return (
    <ScrollView style={styles.pageContainer} contentContainerStyle={styles.pageContent}>
      {/* ---- Header ---- */}
      <View style={styles.headerBlock}>
        <Text style={styles.headerTitle}>{myName}'s Dashboard</Text>
        <Text style={styles.headerSubtitle}>{todayStr()}</Text>
      </View>

      {/* ---- Today — Priority Layer ---- */}
      <TodayCard key={`today-${refreshKey}`} />

      {/* ---- Combined Calendar (real) ---- */}
      <CalendarCard key={`cal-${refreshKey}`} />

      {/* ---- Top 5 Tasks (real) ---- */}
      <TopTasksCard />

      {/* ---- Notes snapshot (real) ---- */}
      <NotesCard />

      {/* ---- Scout panel (real, includes Finance snapshot) ---- */}
      <Collapsible title="Scout" defaultOpen={true}>
        <ScoutPanelBody key={`scout-${refreshKey}`} />
      </Collapsible>

      {/* ---- RexOS panel (placeholder) ---- */}
      <Collapsible title="RexOS" defaultOpen={false}>
        <Text style={styles.panelText}>
          Inbound work and project context. Active projects, closeout
          milestones, and warranty alerts will surface here.
        </Text>
      </Collapsible>

      {/* ---- Exxir panel (placeholder) ---- */}
      <Collapsible title="Exxir" defaultOpen={false}>
        <Text style={styles.panelText}>
          Business and ops context. Operational signals and decisions will
          surface here.
        </Text>
      </Collapsible>

      {/* ---- Need Something? ---- */}
      <NeedSomethingWidget />

      {/* ---- Dev Tools (hidden when DEV_MODE is false) ---- */}
      {DEV_MODE && <DevToolsPanel onIngested={handleIngested} />}
    </ScrollView>
  );
}

const local = StyleSheet.create({
  // card title with bottom margin for personal card headers
  cardTitleSpaced: {
    color: colors.textPrimary,
    fontSize: 17,
    fontWeight: "600",
    letterSpacing: -0.2,
    marginBottom: 10,
  },

  // Calendar rows
  calendarRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
  },
  calendarTime: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "600",
    width: 120,
    paddingTop: 2,
  },
  calendarMain: { flex: 1 },
  calendarSource: {
    color: colors.textPlaceholder,
    fontSize: 10,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginTop: 2,
  },

  // Task rows
  taskRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
  },
  taskDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginTop: 5,
  },
  taskMain: { flex: 1 },

  // Note rows
  noteRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
  },
  noteBullet: { color: colors.textMuted, fontSize: 14, lineHeight: 20 },
  noteTitle: { color: colors.textPrimary, fontSize: 14, fontWeight: "500", flex: 1 },

  // Collapsible panels
  panel: {
    backgroundColor: colors.card,
    borderRadius: 14,
    marginTop: 12,
    overflow: "hidden",
  },
  panelHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 18,
  },
  panelTitle: {
    color: colors.textPrimary,
    fontSize: 17,
    fontWeight: "600",
    letterSpacing: -0.2,
  },
  panelChevron: { color: colors.textMuted, fontSize: 22, fontWeight: "300" },
  panelBody: { paddingHorizontal: 18, paddingBottom: 18, paddingTop: 4 },
  panelText: { color: colors.textSecondary, fontSize: 14, lineHeight: 20 },

  // Scout panel stats
  statRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 6,
  },
  statLabel: { color: colors.textSecondary, fontSize: 14, flex: 1, paddingRight: 8 },
  statValue: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: "600",
    fontVariant: ["tabular-nums"] as any,
  },
  statValueMuted: { color: colors.textMuted, fontSize: 13, fontWeight: "500" },
  incompleteLine: {
    color: colors.textMuted,
    fontSize: 13,
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
    fontStyle: "italic",
  },

  financeBlock: {
    marginTop: 14,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  financeLabel: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 1.2,
    marginBottom: 6,
  },

  // Today — Priority Layer
  todayCard: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 20,
    marginBottom: 20,
  },
  todayTitle: {
    color: colors.accent,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 1.5,
    textTransform: "uppercase",
    marginBottom: 14,
  },
  todayEmpty: { color: colors.textPlaceholder, fontSize: 14 },
  todayContext: {
    color: colors.textMuted,
    fontSize: 12,
    marginBottom: 12,
  },

  primaryCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    borderLeftWidth: 4,
    borderLeftColor: colors.negative,
    padding: 18,
  },
  primaryTitle: {
    color: colors.textPrimary,
    fontSize: 18,
    fontWeight: "700",
    letterSpacing: -0.3,
    lineHeight: 24,
  },
  primarySub: {
    color: colors.textSecondary,
    fontSize: 13,
    marginTop: 6,
  },
  nextUpLine: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "500",
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },

  secondaryList: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: colors.cardBorder,
    gap: 12,
  },
  secondaryRow: { flexDirection: "row", alignItems: "flex-start" },
  todayDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginTop: 4,
    marginRight: 10,
  },
  todayContent: { flex: 1 },
  secondaryTitle: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: "500",
  },
  secondarySub: { color: colors.textMuted, fontSize: 12, marginTop: 2 },

  // Dev Tools
  devCard: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderStyle: "dashed",
    padding: 16,
    marginTop: 32,
  },
  devLabel: {
    color: colors.textPlaceholder,
    fontSize: 10,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 1.5,
    marginBottom: 10,
  },
  devButtons: {
    flexDirection: "row",
    gap: 8,
  },
  devButton: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: "center",
  },
  devButtonText: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "600",
  },
  devMsg: {
    color: colors.textSecondary,
    fontSize: 12,
    marginTop: 8,
  },
});

const styles = { ...shared, ...local } as typeof shared & typeof local;
