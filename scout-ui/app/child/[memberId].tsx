import { useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { TaskCard } from "../../components/TaskCard";
import { shared, colors } from "../../lib/styles";
import {
  fetchChoreTemplates,
  fetchDailyWins,
  fetchEvents,
  fetchMeals,
  fetchMembers,
  fetchRoutines,
  fetchTaskInstances,
  markTaskComplete,
} from "../../lib/api";
import { calculatePayout, sortMealsByType } from "../../lib/constants";
import { todayStr, weekStartStr, weekEndStr, formatTimeOnly, sourceLabel } from "../../lib/format";
import type {
  ChoreTemplate,
  DailyWin,
  Event,
  Meal,
  Routine,
  TaskInstance,
} from "../../lib/types";

function isDone(t: TaskInstance): boolean {
  return !!(t.override_completed ?? t.is_completed);
}

export default function ChildDashboard() {
  const { memberId } = useLocalSearchParams<{ memberId: string }>();
  const [childName, setChildName] = useState("");
  const [routineTasks, setRoutineTasks] = useState<TaskInstance[]>([]);
  const [choreTasks, setChoreTasks] = useState<TaskInstance[]>([]);
  const [routineMap, setRoutineMap] = useState<Record<string, Routine>>({});
  const [choreMap, setChoreMap] = useState<Record<string, ChoreTemplate>>({});
  const [dailyWins, setDailyWins] = useState<DailyWin[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [meals, setMeals] = useState<Meal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!memberId) return;
    try {
      setLoading(true);
      setError(null);
      const today = todayStr();
      const now = new Date();
      const endOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59);

      const [tasks, routines, chores, members, wins, evts, mls] = await Promise.all([
        fetchTaskInstances(today, memberId),
        fetchRoutines(memberId),
        fetchChoreTemplates(),
        fetchMembers(),
        fetchDailyWins(memberId, weekStartStr(), weekEndStr()),
        fetchEvents(now.toISOString(), endOfDay.toISOString()),
        fetchMeals(today),
      ]);

      const member = members.find((m) => m.id === memberId);
      if (member) setChildName(member.first_name);

      const rMap: Record<string, Routine> = {};
      for (const r of routines) rMap[r.id] = r;
      setRoutineMap(rMap);

      const cMap: Record<string, ChoreTemplate> = {};
      for (const c of chores) cMap[c.id] = c;
      setChoreMap(cMap);

      const byDue = (a: TaskInstance, b: TaskInstance) =>
        new Date(a.due_at).getTime() - new Date(b.due_at).getTime();

      setRoutineTasks(tasks.filter((t) => t.routine_id !== null).sort(byDue));
      setChoreTasks(tasks.filter((t) => t.chore_template_id !== null).sort(byDue));
      setDailyWins(wins);
      setEvents(
        evts
          .filter((e) => !e.is_cancelled && e.is_hearth_visible)
          .sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime())
      );
      setMeals(sortMealsByType(mls));
    } catch (e: any) {
      setError(e.message ?? "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [memberId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleToggle = useCallback(
    async (task: TaskInstance) => {
      if (task.is_completed) return;
      try {
        await markTaskComplete(task.id);
        await load();
      } catch (e: any) {
        setError(e.message ?? "Failed to update");
      }
    },
    [load]
  );

  const getTaskMeta = (task: TaskInstance) => {
    if (task.routine_id && routineMap[task.routine_id]) {
      const r = routineMap[task.routine_id];
      return { name: r.name, description: null };
    }
    if (task.chore_template_id && choreMap[task.chore_template_id]) {
      const c = choreMap[task.chore_template_id];
      return { name: c.name, description: c.description };
    }
    return { name: "Task", description: null };
  };

  // Progress calculations
  const allTasks = [...routineTasks, ...choreTasks];
  const totalCount = allTasks.length;
  const doneCount = allTasks.filter(isDone).length;
  const allDone = totalCount > 0 && doneCount === totalCount;
  const winCount = dailyWins.filter((w) => w.is_win).length;
  const { baseline, amountCents: earnedCents } = calculatePayout(childName, winCount);

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

  return (
    <ScrollView style={styles.pageContainer} contentContainerStyle={styles.pageContent}>
      {/* ---- Header + Progress Summary ---- */}
      <Text style={styles.headerName}>{childName}'s Day</Text>
      <Text style={styles.headerDate}>{todayStr()}</Text>

      <View style={styles.summaryCard}>
        {allDone ? (
          <Text style={styles.summaryDone}>All done for today!</Text>
        ) : (
          <>
            <Text style={styles.summaryText}>
              {doneCount} of {totalCount} done
            </Text>
            <Text style={styles.encourageLine}>
              {totalCount - doneCount === 1
                ? "1 left — finish it"
                : `${totalCount - doneCount} left — you've got this`}
            </Text>
          </>
        )}
        <View style={styles.summaryBar}>
          <View
            style={[
              styles.summaryBarFill,
              { width: totalCount > 0 ? `${(doneCount / totalCount) * 100}%` : "0%" },
              allDone && styles.summaryBarDone,
            ]}
          />
        </View>
      </View>

      {/* ---- 1. Schedule (real) ---- */}
      <Text style={styles.sectionTitle}>Schedule</Text>
      <View style={styles.card}>
        {events.length === 0 ? (
          <Text style={styles.emptyText}>No events today</Text>
        ) : (
          <View style={styles.itemList}>
            {events.map((e) => (
              <View key={e.id} style={styles.itemRow}>
                <Text style={styles.itemTitle}>{e.title}</Text>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                  {sourceLabel(e.source) && (
                    <Text style={styles.itemBadge}>{sourceLabel(e.source)}</Text>
                  )}
                  <Text style={styles.itemMeta}>
                    {formatTimeOnly(e.starts_at, e.all_day)}
                  </Text>
                </View>
              </View>
            ))}
          </View>
        )}
      </View>

      {/* ---- 2. Responsibilities ---- */}
      <Text style={styles.sectionTitle}>Responsibilities</Text>

      {routineTasks.length > 0 && (
        <Text style={styles.groupLabel}>Routines</Text>
      )}
      {routineTasks.map((task) => {
        const meta = getTaskMeta(task);
        return (
          <TaskCard
            key={task.id}
            task={task}
            name={meta.name}
            isRoutine={true}
            routineId={task.routine_id}
            description={meta.description}
            onToggle={() => handleToggle(task)}
            onStepChange={load}
          />
        );
      })}

      {choreTasks.length > 0 && (
        <Text style={styles.groupLabel}>Chores</Text>
      )}
      {choreTasks.map((task) => {
        const meta = getTaskMeta(task);
        return (
          <TaskCard
            key={task.id}
            task={task}
            name={meta.name}
            isRoutine={false}
            routineId={null}
            description={meta.description}
            onToggle={() => handleToggle(task)}
          />
        );
      })}

      {totalCount === 0 && (
        <View style={styles.card}>
          <Text style={styles.emptyText}>No responsibilities today</Text>
        </View>
      )}

      {/* ---- 3. Meals (real) ---- */}
      <Text style={styles.sectionTitle}>Meals</Text>
      <View style={styles.card}>
        {meals.length === 0 ? (
          <Text style={styles.emptyText}>No meals planned today</Text>
        ) : (
          <View style={styles.itemList}>
            {meals.map((m) => (
              <View key={m.id} style={styles.itemRow}>
                <Text style={styles.mealType}>{m.meal_type}</Text>
                <Text style={styles.itemTitle} numberOfLines={1}>{m.title}</Text>
              </View>
            ))}
          </View>
        )}
      </View>

      {/* ---- 4. Progress ---- */}
      <Text style={styles.sectionTitle}>Progress</Text>
      <View style={styles.card}>
        <View style={styles.progressRow}>
          <Text style={styles.progressLabel}>This week</Text>
          <Text style={styles.progressValue}>
            {winCount}
            <Text style={styles.progressMuted}>/5 days</Text>
          </Text>
        </View>
        {baseline > 0 && (
          <View style={styles.progressRow}>
            <Text style={styles.progressLabel}>Earned so far</Text>
            <Text style={[styles.progressValue, earnedCents > 0 && styles.progressEarned]}>
              ${(earnedCents / 100).toFixed(2)}
              {earnedCents > 0 && (
                <Text style={styles.progressMuted}> of ${(baseline / 100).toFixed(2)}</Text>
              )}
            </Text>
          </View>
        )}
        <View style={styles.winDots}>
          {["M", "T", "W", "T", "F"].map((label, i) => {
            const hasWin = i < winCount;
            return (
              <View key={i} style={styles.winDotCol}>
                <View style={[styles.winDot, hasWin && styles.winDotFilled]} />
                <Text style={[styles.winDotLabel, hasWin && styles.winDotLabelFilled]}>
                  {label}
                </Text>
              </View>
            );
          })}
        </View>
      </View>
    </ScrollView>
  );
}

const local = StyleSheet.create({
  headerName: { color: colors.textPrimary, fontSize: 24, fontWeight: "700" },
  headerDate: { color: colors.textMuted, fontSize: 14, marginTop: 2, marginBottom: 16 },

  summaryCard: {
    backgroundColor: colors.card,
    borderRadius: 14,
    padding: 16,
    marginBottom: 8,
  },
  summaryText: { color: colors.textPrimary, fontSize: 16, fontWeight: "600" },
  summaryDone: { color: colors.positive, fontSize: 16, fontWeight: "700" },
  encourageLine: { color: colors.textMuted, fontSize: 13, marginTop: 4 },
  summaryBar: {
    height: 6,
    backgroundColor: colors.cardBorder,
    borderRadius: 3,
    marginTop: 10,
    overflow: "hidden",
  },
  summaryBarFill: { height: 6, backgroundColor: colors.accent, borderRadius: 3 },
  summaryBarDone: { backgroundColor: colors.positive },

  groupLabel: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 1,
    marginBottom: 8,
    marginTop: 4,
  },

  progressRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 6,
  },
  progressLabel: { color: colors.textSecondary, fontSize: 14 },
  progressValue: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: "600",
    fontVariant: ["tabular-nums"] as any,
  },
  progressMuted: { color: colors.textMuted, fontSize: 14, fontWeight: "500" },
  progressEarned: { color: colors.positive },

  winDots: {
    flexDirection: "row",
    justifyContent: "center",
    gap: 8,
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  winDotCol: { alignItems: "center", gap: 4 },
  winDot: { width: 14, height: 14, borderRadius: 7, backgroundColor: colors.cardBorder },
  winDotFilled: { backgroundColor: colors.positive },
  winDotLabel: {
    color: colors.textPlaceholder,
    fontSize: 9,
    fontWeight: "600",
    letterSpacing: 0.5,
  },
  winDotLabelFilled: { color: colors.textMuted },
});

const styles = { ...shared, ...local } as typeof shared & typeof local;
