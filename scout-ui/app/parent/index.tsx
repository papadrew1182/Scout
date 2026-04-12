import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { ActionInbox } from "../../components/ActionInbox";
import { NeedSomething } from "../../components/NeedSomething";
import {
  fetchMembers,
  fetchTaskInstances,
  fetchDailyWins,
  fetchEvents,
  fetchMeals,
  fetchUnpaidBills,
  createWeeklyPayout,
  PayoutError,
} from "../../lib/api";
import { calculatePayout, sortMealsByType } from "../../lib/constants";
import { todayStr, weekStartStr, weekEndStr, formatEventTime, formatDueDate, sourceLabel } from "../../lib/format";
import { shared, colors } from "../../lib/styles";
import type {
  Bill,
  DailyWin,
  Event,
  FamilyMember,
  Meal,
  TaskInstance,
} from "../../lib/types";

// ============================================================================
// Weekly status derivation (rule-based, no AI)
// ============================================================================

type WeeklyStatus = "on_track" | "at_risk" | "off_track" | "complete";

function deriveWeeklyStatus(wins: number): WeeklyStatus {
  // What day of the scoring week are we? Mon=1 .. Fri=5
  const dow = new Date().getDay(); // 0=Sun
  const scoringDay = dow === 0 ? 5 : Math.min(dow, 5); // clamp weekends to Friday
  const daysRemaining = 5 - scoringDay;
  const maxPossible = wins + daysRemaining;

  if (wins === 5) return "complete";
  if (maxPossible < 3) return "off_track"; // can't reach 60% payout
  if (wins >= 3 && scoringDay <= 3) return "on_track"; // 3+ by Wed
  if (wins >= 4 && scoringDay <= 4) return "on_track"; // 4+ by Thu
  if (wins >= scoringDay) return "on_track"; // winning every day so far
  if (maxPossible >= 3) return "at_risk"; // still recoverable
  return "off_track";
}

function weeklyStatusLabel(status: WeeklyStatus): string {
  switch (status) {
    case "complete": return "Complete";
    case "on_track": return "On track";
    case "at_risk": return "At risk";
    case "off_track": return "Off track";
  }
}

function weeklyStatusColor(status: WeeklyStatus): string {
  switch (status) {
    case "complete": return colors.positive;
    case "on_track": return colors.positive;
    case "at_risk": return colors.warning;
    case "off_track": return colors.negative;
  }
}

interface HouseholdInsight {
  text: string;
  tone: "positive" | "warning" | "negative" | "neutral";
}

function deriveHouseholdInsight(
  statuses: { member: FamilyMember; total: number; completed: number; wins: number }[]
): HouseholdInsight {
  if (statuses.length === 0) return { text: "", tone: "neutral" };

  const offTrack = statuses.filter((s) => deriveWeeklyStatus(s.wins) === "off_track");
  if (offTrack.length > 0) {
    const names = offTrack.map((s) => s.member.first_name).join(" and ");
    return { text: `${names} can't reach full payout this week`, tone: "negative" };
  }

  const atRisk = statuses.filter((s) => deriveWeeklyStatus(s.wins) === "at_risk");
  if (atRisk.length > 0) {
    const names = atRisk.map((s) => s.member.first_name).join(" and ");
    return { text: `${names} ${atRisk.length > 1 ? "are" : "is"} at risk this week`, tone: "warning" };
  }

  const allDoneToday = statuses.every((s) => s.total > 0 && s.completed === s.total);
  if (allDoneToday) return { text: "All kids are done for today", tone: "positive" };

  const incomplete = statuses.filter((s) => s.total - s.completed > 0);
  if (incomplete.length > 0) {
    const names = incomplete.map((s) => s.member.first_name).join(", ");
    return { text: `Still working: ${names}`, tone: "neutral" };
  }

  return { text: "Everyone is on track this week", tone: "positive" };
}

function insightBorderColor(tone: HouseholdInsight["tone"]): string {
  switch (tone) {
    case "positive": return colors.positive;
    case "warning": return colors.warning;
    case "negative": return colors.negative;
    default: return colors.accent;
  }
}

// ============================================================================
// Family Schedule — next 3 days
// ============================================================================

function FamilyScheduleSection() {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const now = new Date();
    const horizon = new Date();
    horizon.setDate(horizon.getDate() + 3);
    fetchEvents(now.toISOString(), horizon.toISOString())
      .then((data) => {
        setEvents(
          data
            .filter((e) => !e.is_cancelled)
            .sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime())
        );
      })
      .catch((e) => setError(e.message ?? "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <Text style={styles.sectionTitle}>Family Schedule</Text>
      <View style={styles.card}>
        {loading && <ActivityIndicator size="small" color={colors.accent} />}
        {!loading && error && <Text style={styles.errorText}>{error}</Text>}
        {!loading && !error && events.length === 0 && (
          <Text style={styles.emptyText}>No upcoming events</Text>
        )}
        {!loading && !error && events.length > 0 && (
          <View style={styles.itemList}>
            {events.map((e) => (
              <View key={e.id} style={styles.itemRow}>
                <View style={styles.itemMain}>
                  <Text style={styles.itemTitle}>{e.title}</Text>
                  <Text style={styles.itemMeta}>
                    {formatEventTime(e.starts_at, e.all_day)}
                  </Text>
                </View>
                {sourceLabel(e.source) && (
                  <Text style={styles.itemBadge}>{sourceLabel(e.source)}</Text>
                )}
              </View>
            ))}
          </View>
        )}
      </View>
    </>
  );
}

// ============================================================================
// Meals — today
// ============================================================================

function MealsSection() {
  const [meals, setMeals] = useState<Meal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMeals(todayStr())
      .then((data) => {
        setMeals(
          sortMealsByType(data)
        );
      })
      .catch((e) => setError(e.message ?? "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <Text style={styles.sectionTitle}>Meals</Text>
      <View style={styles.card}>
        {loading && <ActivityIndicator size="small" color={colors.accent} />}
        {!loading && error && <Text style={styles.errorText}>{error}</Text>}
        {!loading && !error && meals.length === 0 && (
          <Text style={styles.emptyText}>No meals planned today</Text>
        )}
        {!loading && !error && meals.length > 0 && (
          <View style={styles.itemList}>
            {meals.map((m) => (
              <View key={m.id} style={styles.itemRow}>
                <Text style={styles.mealType}>{m.meal_type}</Text>
                <Text style={styles.itemTitle} numberOfLines={1}>
                  {m.title}
                </Text>
              </View>
            ))}
          </View>
        )}
      </View>
    </>
  );
}

// ============================================================================
// Bills — unpaid snapshot
// ============================================================================

function BillsSection() {
  const [bills, setBills] = useState<Bill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchUnpaidBills()
      .then(setBills)
      .catch((e) => setError(e.message ?? "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <Text style={styles.sectionTitle}>Bills</Text>
      <View style={styles.card}>
        {loading && <ActivityIndicator size="small" color={colors.accent} />}
        {!loading && error && <Text style={styles.errorText}>{error}</Text>}
        {!loading && !error && bills.length === 0 && (
          <Text style={styles.emptyText}>No unpaid bills</Text>
        )}
        {!loading && !error && bills.length > 0 && (
          <>
            <View style={styles.cardRow}>
              <Text style={styles.cardSubtle}>Unpaid</Text>
              <Text style={styles.statBig}>{bills.length}</Text>
            </View>
            <View style={[styles.cardRow, { marginTop: 8 }]}>
              <Text style={styles.cardSubtle} numberOfLines={1}>
                Next: {bills[0].title}
              </Text>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                {sourceLabel(bills[0].source) && (
                  <Text style={styles.itemBadge}>{sourceLabel(bills[0].source)}</Text>
                )}
                <Text style={styles.itemMeta}>{formatDueDate(bills[0].due_date)}</Text>
              </View>
            </View>
          </>
        )}
      </View>
    </>
  );
}

// ============================================================================
// Main Parent Dashboard
// ============================================================================

interface ChildStatus {
  member: FamilyMember;
  total: number;
  completed: number;
  wins: number;
}

export default function ParentDashboard() {
  const [statuses, setStatuses] = useState<ChildStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<{ text: string; isError: boolean } | null>(null);
  const [payoutRan, setPayoutRan] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const today = todayStr();
      const wStart = weekStartStr();
      const wEnd = weekEndStr();

      const [members, tasks] = await Promise.all([
        fetchMembers(),
        fetchTaskInstances(today),
      ]);

      const children = members.filter(
        (m) => m.role === "child" && m.is_active
      );

      const results: ChildStatus[] = [];

      for (const child of children) {
        const childTasks = tasks.filter(
          (t) => t.family_member_id === child.id
        );
        const completed = childTasks.filter((t) => t.is_completed).length;

        let wins: DailyWin[] = [];
        try {
          wins = await fetchDailyWins(child.id, wStart, wEnd);
        } catch {
          // daily wins may not exist yet
        }

        results.push({
          member: child,
          total: childTasks.length,
          completed,
          wins: wins.filter((w) => w.is_win).length,
        });
      }

      setStatuses(results);
    } catch (e: any) {
      setError(e.message ?? "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleRunPayouts = async () => {
    setActionMsg(null);
    const wStart = weekStartStr();
    const results: string[] = [];
    let hasError = false;
    let allDuplicate = true;
    for (const s of statuses) {
      const { baseline } = calculatePayout(s.member.first_name, 0);
      if (baseline === 0) continue;
      try {
        await createWeeklyPayout(s.member.id, baseline, wStart);
        results.push(`${s.member.first_name}: payout created`);
        allDuplicate = false;
      } catch (e: any) {
        hasError = true;
        if (e instanceof PayoutError && e.status === 409) {
          results.push(`${s.member.first_name}: payout already exists for this week`);
        } else {
          results.push(`${s.member.first_name}: payout failed`);
          allDuplicate = false;
        }
      }
    }
    setPayoutRan(true);
    setActionMsg({
      text: allDuplicate
        ? "Payout already run for this week"
        : results.join("\n"),
      isError: hasError && !allDuplicate,
    });
  };

  const handleBonus = (name: string) => {
    setActionMsg({ text: `Bonus for ${name} — not implemented yet`, isError: false });
  };

  const handlePenalty = (name: string) => {
    setActionMsg({ text: `Penalty for ${name} — not implemented yet`, isError: false });
  };

  if (loading) {
    return (
      <View style={styles.pageCenter}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.pageCenter}>
        <Text style={styles.errorLarge}>{error}</Text>
      </View>
    );
  }

  const totalTasks = statuses.reduce((sum, s) => sum + s.total, 0);
  const totalCompleted = statuses.reduce((sum, s) => sum + s.completed, 0);

  return (
    <ScrollView style={styles.pageContainer} contentContainerStyle={styles.pageContent}>
      {/* ---- Header ---- */}
      <View style={styles.headerBlock}>
        <Text style={styles.headerTitle}>Parent Dashboard</Text>
        <Text style={styles.headerSubtitle}>{todayStr()}</Text>
      </View>

      {actionMsg && (
        <View style={[styles.msgBox, actionMsg.isError && styles.msgBoxError]}>
          <Text style={[styles.msgText, actionMsg.isError && styles.msgTextError]}>
            {actionMsg.text}
          </Text>
        </View>
      )}

      {/* ---- Household Insight ---- */}
      {statuses.length > 0 && (() => {
        const insight = deriveHouseholdInsight(statuses);
        return insight.text ? (
          <View style={[s.insightCard, { borderLeftColor: insightBorderColor(insight.tone) }]}>
            <Text style={s.insightText}>{insight.text}</Text>
          </View>
        ) : null;
      })()}

      {/* ---- Action Inbox ---- */}
      <ActionInbox />

      {/* ---- 1. Family Schedule ---- */}
      <FamilyScheduleSection />

      {/* ---- 2. Kids Status ---- */}
      <Text style={styles.sectionTitle}>Kids Today</Text>
      {statuses.map((st) => {
        const remaining = st.total - st.completed;
        const done = remaining === 0 && st.total > 0;
        return (
          <View key={st.member.id} style={styles.card}>
            <View style={styles.cardRow}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                {!done && st.total > 0 && (
                  <View style={s.attentionDot} />
                )}
                <Text style={styles.cardTitle}>{st.member.first_name}</Text>
              </View>
              <Text style={styles.statBig}>
                {st.completed}
                <Text style={styles.statBigMuted}>/{st.total}</Text>
              </Text>
            </View>
            <Text style={[styles.cardSubtle, done && styles.doneText]}>
              {done
                ? "All done for today"
                : `${st.completed}/${st.total} done — ${remaining} left`}
            </Text>
          </View>
        );
      })}

      {/* ---- 3. Weekly Progress ---- */}
      <Text style={styles.sectionTitle}>Weekly Progress</Text>
      {statuses.map((st) => {
        const { baseline, amountCents } = calculatePayout(st.member.first_name, st.wins);
        const wStatus = deriveWeeklyStatus(st.wins);
        return (
          <View key={st.member.id} style={styles.card}>
            <View style={styles.cardRow}>
              <Text style={styles.cardTitle}>{st.member.first_name}</Text>
              <Text style={styles.statBig}>
                {st.wins}
                <Text style={styles.statBigMuted}>/5</Text>
              </Text>
            </View>
            <View style={[styles.cardRow, { marginTop: 4 }]}>
              <Text style={styles.cardSubtle}>
                ${(amountCents / 100).toFixed(2)} of ${(baseline / 100).toFixed(2)}
              </Text>
              <View style={[s.statusPill, { backgroundColor: weeklyStatusColor(wStatus) + "22" }]}>
                <Text style={[s.statusPillText, { color: weeklyStatusColor(wStatus) }]}>
                  {weeklyStatusLabel(wStatus)}
                </Text>
              </View>
            </View>
          </View>
        );
      })}

      {/* ---- 4. Meals ---- */}
      <MealsSection />

      {/* ---- 5. Bills ---- */}
      <BillsSection />

      {/* ---- 6. Household Overview ---- */}
      <Text style={styles.sectionTitle}>Household</Text>
      <View style={styles.card}>
        <View style={styles.statGrid}>
          <View style={styles.statCell}>
            <Text style={styles.statNumber}>{totalTasks}</Text>
            <Text style={styles.statLabel}>tasks</Text>
          </View>
          <View style={styles.statCell}>
            <Text style={[styles.statNumber, styles.statNumberOk]}>
              {totalCompleted}
            </Text>
            <Text style={styles.statLabel}>done</Text>
          </View>
          <View style={styles.statCell}>
            <Text style={styles.statNumber}>{totalTasks - totalCompleted}</Text>
            <Text style={styles.statLabel}>left</Text>
          </View>
        </View>
        {totalTasks > 0 && totalCompleted === totalTasks && (
          <Text style={styles.householdDone}>
            Everyone's responsibilities are complete for today
          </Text>
        )}
      </View>

      {/* ---- 7. Weekly Payout ---- */}
      <Text style={styles.sectionTitle}>Weekly Payout</Text>
      {statuses.map((s) => {
        const { baseline, pct, amountCents } = calculatePayout(s.member.first_name, s.wins);
        return (
          <View key={s.member.id} style={styles.card}>
            <View style={styles.cardRow}>
              <View style={styles.cardLeft}>
                <Text style={styles.cardTitle}>{s.member.first_name}</Text>
                <Text style={styles.cardSubtle}>
                  {pct}% of ${(baseline / 100).toFixed(2)}
                </Text>
              </View>
              <Text style={styles.amount}>${(amountCents / 100).toFixed(2)}</Text>
            </View>
            <View style={styles.buttonRow}>
              <Pressable
                style={styles.buttonSmall}
                onPress={() => handleBonus(s.member.first_name)}
              >
                <Text style={styles.buttonSmallText}>Add Bonus</Text>
              </Pressable>
              <Pressable
                style={styles.buttonSmall}
                onPress={() => handlePenalty(s.member.first_name)}
              >
                <Text style={styles.buttonSmallText}>Add Penalty</Text>
              </Pressable>
            </View>
          </View>
        );
      })}

      <Pressable
        style={[styles.button, payoutRan && styles.buttonDisabled]}
        onPress={payoutRan ? undefined : handleRunPayouts}
        disabled={payoutRan}
      >
        <Text style={[styles.buttonText, payoutRan && styles.buttonTextDisabled]}>
          {payoutRan ? "Payout already run for this week" : "Run Weekly Payout"}
        </Text>
      </Pressable>

      {/* ---- Need Something? ---- */}
      <NeedSomething />
    </ScrollView>
  );
}

// Use shared.* for common styles; local `s` for parent-specific only
const s = StyleSheet.create({
  cardLeft: { flex: 1 },
  amount: {
    color: colors.positive,
    fontSize: 22,
    fontWeight: "700",
    fontVariant: ["tabular-nums"] as any,
  },
  statGrid: {
    flexDirection: "row",
    justifyContent: "space-around",
    paddingVertical: 4,
  },
  statCell: { alignItems: "center" },
  statNumber: {
    color: colors.textPrimary,
    fontSize: 26,
    fontWeight: "700",
    fontVariant: ["tabular-nums"] as any,
  },
  statNumberOk: { color: colors.positive },
  statLabel: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 1,
    marginTop: 4,
  },
  doneText: { color: colors.positive },
  householdDone: {
    color: colors.positive,
    fontSize: 13,
    textAlign: "center",
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },

  // Household Insight
  insightCard: {
    backgroundColor: colors.card,
    borderRadius: 14,
    borderLeftWidth: 3,
    borderLeftColor: colors.accent,
    padding: 16,
    marginBottom: 4,
  },
  insightText: {
    color: colors.textPrimary,
    fontSize: 15,
    fontWeight: "600",
    lineHeight: 20,
  },

  // Attention dot (per-child incomplete indicator)
  attentionDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.warning,
  },

  // Weekly status pill
  statusPill: {
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  statusPillText: {
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
});

// Merge: use `shared` by name in JSX for all common, `s` for parent-specific
const styles = { ...shared, ...s } as typeof shared & typeof s;
