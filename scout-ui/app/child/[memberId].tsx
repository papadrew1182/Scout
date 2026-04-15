import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";

import { colors, fonts, shared } from "../../lib/styles";
import { getMember, LEADERBOARD, ALLOWANCE } from "../../lib/seedData";
import { fetchTaskInstances, markTaskComplete, fetchChoreTemplates, fetchRoutines } from "../../lib/api";
import { todayStr } from "../../lib/format";
import { TaskCard } from "../../components/TaskCard";
import type { TaskInstance, ChoreTemplate, Routine } from "../../lib/types";

const TINT_BG: Record<string, string> = {
  purple: colors.avPurpleBg, teal: colors.avTealBg, amber: colors.avAmberBg, coral: colors.avCoralBg,
};
const TINT_TEXT: Record<string, string> = {
  purple: colors.avPurpleText, teal: colors.avTealText, amber: colors.avAmberText, coral: colors.avCoralText,
};

export default function Child() {
  const params = useLocalSearchParams<{ memberId: string }>();
  // Always show Townes for the demo regardless of route param.
  const member = getMember(params.memberId ?? "townes") ?? getMember("townes")!;
  const allowance = ALLOWANCE.find((a) => a.memberId === member.id) ?? ALLOWANCE[1];
  const leader = LEADERBOARD.find((l) => l.memberId === member.id) ?? LEADERBOARD[0];
  const pct = leader.points >= 1000 ? 100 : Math.round((leader.points / 1000) * 100);
  const remaining = Math.max(0, 1000 - leader.points);

  // Task loading state
  const [tasks, setTasks] = useState<TaskInstance[]>([]);
  const [choreMap, setChoreMap] = useState<Record<string, ChoreTemplate>>({});
  const [routineMap, setRoutineMap] = useState<Record<string, Routine>>({});
  const [tasksLoading, setTasksLoading] = useState(true);

  const loadTasks = useCallback(async () => {
    if (!params.memberId) return;
    setTasksLoading(true);
    try {
      const [ti, tmpls, routines] = await Promise.all([
        fetchTaskInstances(todayStr(), params.memberId),
        fetchChoreTemplates().catch(() => [] as ChoreTemplate[]),
        fetchRoutines(params.memberId).catch(() => [] as Routine[]),
      ]);
      setTasks(ti);
      const cMap: Record<string, ChoreTemplate> = {};
      tmpls.forEach((t) => {
        cMap[t.id] = t;
      });
      setChoreMap(cMap);
      const rMap: Record<string, Routine> = {};
      routines.forEach((r) => {
        rMap[r.id] = r;
      });
      setRoutineMap(rMap);
    } catch {
      setTasks([]);
    } finally {
      setTasksLoading(false);
    }
  }, [params.memberId]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  const handleToggleTask = useCallback(
    async (task: TaskInstance) => {
      if (task.is_completed) return;
      try {
        await markTaskComplete(task.id);
        await loadTasks();
      } catch {
        // swallow — UI can show stale state for one tick
      }
    },
    [loadTasks],
  );

  const getTaskName = (task: TaskInstance): string => {
    if (task.routine_id && routineMap[task.routine_id]) {
      return routineMap[task.routine_id].name;
    }
    if (task.chore_template_id && choreMap[task.chore_template_id]) {
      return choreMap[task.chore_template_id].name;
    }
    return "Task";
  };

  const getTaskDescription = (task: TaskInstance): string | null => {
    if (task.chore_template_id && choreMap[task.chore_template_id]) {
      return choreMap[task.chore_template_id].description ?? null;
    }
    return null;
  };

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <View style={styles.hero}>
        <View style={[styles.bigAv, { backgroundColor: TINT_BG[member.tint] }]}>
          <Text style={[styles.bigAvText, { color: TINT_TEXT[member.tint] }]}>{member.initials}</Text>
        </View>
        <Text style={styles.heroTitle}>Hey {member.firstName}!</Text>
        <Text style={styles.heroSub}>Wednesday · You finished all your chores today!</Text>
        <View style={styles.heroPill}>
          <Text style={styles.heroPillText}>{leader.points} pts total · Rank #{leader.rank} this week 🏆</Text>
        </View>
      </View>

      <View style={styles.grid2}>
        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>My chores today</Text>
            <Text style={shared.cardAction}> </Text>
          </View>
          {tasksLoading ? (
            <ActivityIndicator size="small" color={colors.purple} style={{ marginVertical: 10 }} />
          ) : tasks.length === 0 ? (
            <Text style={styles.emptyChores}>No chores today. Enjoy the day!</Text>
          ) : (
            <View style={{ gap: 6 }}>
              {tasks.map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  name={getTaskName(task)}
                  isRoutine={!!task.routine_id}
                  routineId={task.routine_id ?? null}
                  description={getTaskDescription(task)}
                  onToggle={() => handleToggleTask(task)}
                />
              ))}
            </View>
          )}
        </View>

        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>My points</Text>
            <Text style={shared.cardAction}>Rewards store</Text>
          </View>
          <View style={styles.pointsHero}>
            <Text style={styles.pointsBig}>{leader.points}</Text>
            <Text style={styles.pointsLabel}>Total points</Text>
          </View>
          <View style={styles.ptsBar}><View style={[styles.ptsFill, { width: `${pct}%` }]} /></View>
          <View style={styles.ptsRange}>
            <Text style={styles.ptsRangeText}>0</Text>
            <Text style={styles.ptsRangeText}>{remaining} more to unlock next reward</Text>
            <Text style={styles.ptsRangeText}>1000</Text>
          </View>
          <Text style={shared.sectionHead}>Recent earnings</Text>
          <View style={styles.earnRow}>
            <Text style={styles.earnLabel}>7-day streak bonus</Text>
            <View style={styles.tagGreen}><Text style={styles.tagGreenText}>+20</Text></View>
          </View>
          <View style={styles.earnRow}>
            <Text style={styles.earnLabel}>All chores today</Text>
            <View style={styles.tagGreen}><Text style={styles.tagGreenText}>+40</Text></View>
          </View>
          <View style={styles.earnRow}>
            <Text style={styles.earnLabel}>Reading — 30 min</Text>
            <View style={styles.tagPurple}><Text style={styles.tagPurpleText}>+15</Text></View>
          </View>
        </View>
      </View>

      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Allowance this week</Text>
          <Text style={shared.cardAction}> </Text>
        </View>
        <View style={styles.allowanceRow}>
          <View style={styles.fullBar}>
            <View style={[styles.fullBarFill, { width: `${(allowance.earned / allowance.max) * 100}%` }]} />
          </View>
          <Text style={styles.allowanceAmount}>${allowance.earned.toFixed(2)} / ${allowance.max.toFixed(2)}</Text>
          <View style={styles.tagGreen}><Text style={styles.tagGreenText}>Full payout!</Text></View>
        </View>
        <Text style={styles.allowanceSub}>Paid to your Greenlight card on Sunday. Keep it up!</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  hero: { alignItems: "center", paddingVertical: 16, gap: 8 },
  bigAv: { width: 72, height: 72, borderRadius: 36, alignItems: "center", justifyContent: "center" },
  bigAvText: { fontSize: 28, fontWeight: "600", fontFamily: fonts.body },
  heroTitle: { fontSize: 22, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  heroSub: { fontSize: 13, color: colors.muted, fontFamily: fonts.body },
  heroPill: { backgroundColor: colors.greenBg, borderRadius: 14, paddingHorizontal: 16, paddingVertical: 6, marginTop: 4 },
  heroPillText: { fontSize: 12, fontWeight: "600", color: colors.greenText, fontFamily: fonts.body },

  grid2: { flexDirection: "row", gap: 12 },

  emptyChores: { fontSize: 12, color: colors.muted, fontFamily: fonts.body, textAlign: "center", paddingVertical: 12 },

  tagGreen: { backgroundColor: colors.greenBg, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  tagGreenText: { fontSize: 10, fontWeight: "700", color: colors.greenText, fontFamily: fonts.body },
  tagPurple: { backgroundColor: colors.purpleLight, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  tagPurpleText: { fontSize: 10, fontWeight: "700", color: colors.purpleDeep, fontFamily: fonts.body },

  pointsHero: { alignItems: "center", paddingVertical: 8 },
  pointsBig: { fontSize: 40, fontWeight: "600", color: colors.purple, fontFamily: fonts.mono },
  pointsLabel: { fontSize: 12, color: colors.muted, fontFamily: fonts.body },
  ptsBar: { height: 8, backgroundColor: colors.border, borderRadius: 4, overflow: "hidden", marginVertical: 8 },
  ptsFill: { height: "100%", backgroundColor: colors.purple, borderRadius: 4 },
  ptsRange: { flexDirection: "row", justifyContent: "space-between", marginBottom: 10 },
  ptsRangeText: { fontSize: 10, color: colors.muted, fontFamily: fonts.body },

  earnRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 5,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  earnLabel: { flex: 1, fontSize: 12, color: colors.text, fontFamily: fonts.body },

  allowanceRow: { flexDirection: "row", alignItems: "center", gap: 14, paddingVertical: 4 },
  fullBar: { flex: 1, height: 12, backgroundColor: colors.border, borderRadius: 6, overflow: "hidden" },
  fullBarFill: { height: "100%", backgroundColor: colors.green, borderRadius: 6 },
  allowanceAmount: { fontSize: 16, fontWeight: "600", color: colors.green, fontFamily: fonts.mono },
  allowanceSub: { fontSize: 11, color: colors.muted, marginTop: 6, fontFamily: fonts.body },
});
