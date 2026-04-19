// Phase 3 - child master card.
// Shows today's tasks, ownership chores, Daily Win summary, and scope
// contracts for each active chore assigned to this member.

import { StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";

import {
  useFamilyContext,
  useHouseholdToday,
  useMe,
  useRewardsWeek,
} from "../../../../features/hooks";
import { colors } from "../../../../lib/styles";

export default function MemberDetailRoute() {
  const { id, tab } = useLocalSearchParams<{ id: string; tab?: string }>();
  const family = useFamilyContext();
  const me = useMe();
  const today = useHouseholdToday();
  const rewards = useRewardsWeek();

  const kids = family.data?.kids ?? [];
  const member = kids.find((k) => k.family_member_id === id);
  const memberName = member?.name ?? "Member";

  const isOwnCard = me.data?.user.family_member_id === id;
  const isParentTier =
    me.data?.user.role_tier_key === "PRIMARY_PARENT" ||
    me.data?.user.role_tier_key === "PARENT";
  const canView = isOwnCard || isParentTier;

  if (!canView) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>Not available</Text>
        <Text style={styles.body}>
          You can only view your own master card.
        </Text>
      </View>
    );
  }

  const todayData = today.data;
  const myAssignments = todayData
    ? todayData.blocks.flatMap((b) =>
        b.assignments.filter((a) => a.family_member_id === id),
      )
    : [];
  const myChores = todayData
    ? todayData.standalone_chores.filter((o) => o.owner_family_member_id === id)
    : [];
  const totalTasks = myAssignments.length + myChores.length;
  const completedTasks =
    myAssignments.filter((a) => a.status === "complete").length +
    myChores.filter((o) => o.status === "complete").length;
  const lateTasks =
    myAssignments.filter((a) => a.status === "late").length +
    myChores.filter((o) => o.status === "late").length;

  const rewardsMember = rewards.data?.members.find(
    (m) => m.family_member_id === id,
  );

  return (
    <View style={styles.container}>
      <Text style={styles.eyebrow}>MEMBER</Text>
      <Text style={styles.title}>{memberName}</Text>
      {tab && <Text style={styles.tabLabel}>Viewing: {tab}</Text>}

      <View style={styles.card}>
        <Text style={styles.sectionTitle}>Today's progress</Text>
        <View style={styles.statsRow}>
          <View style={styles.stat}>
            <Text style={styles.statValue}>{completedTasks}</Text>
            <Text style={styles.statLabel}>Done</Text>
          </View>
          <View style={styles.stat}>
            <Text style={styles.statValue}>{totalTasks - completedTasks}</Text>
            <Text style={styles.statLabel}>Remaining</Text>
          </View>
          <View style={styles.stat}>
            <Text style={[styles.statValue, lateTasks > 0 && styles.statWarn]}>
              {lateTasks}
            </Text>
            <Text style={styles.statLabel}>Late</Text>
          </View>
        </View>
      </View>

      {rewardsMember && (
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>This week</Text>
          <View style={styles.statsRow}>
            <View style={styles.stat}>
              <Text style={styles.statValue}>{rewardsMember.daily_wins}</Text>
              <Text style={styles.statLabel}>Daily wins</Text>
            </View>
            <View style={styles.stat}>
              <Text style={styles.statValue}>
                ${rewardsMember.projected_payout.toFixed(2)}
              </Text>
              <Text style={styles.statLabel}>Projected</Text>
            </View>
            <View style={styles.stat}>
              <Text style={styles.statValue}>{rewardsMember.payout_percent}%</Text>
              <Text style={styles.statLabel}>Payout</Text>
            </View>
          </View>
          {rewardsMember.miss_reasons.length > 0 && (
            <View style={styles.missBlock}>
              <Text style={styles.missLabel}>Missed items</Text>
              {rewardsMember.miss_reasons.slice(0, 5).map((r, i) => (
                <Text key={i} style={styles.missLine}>- {r}</Text>
              ))}
            </View>
          )}
        </View>
      )}

      {myChores.length > 0 && (
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Ownership chores</Text>
          {myChores.map((chore) => (
            <View key={chore.task_occurrence_id} style={styles.choreRow}>
              <View
                style={[
                  styles.statusDot,
                  chore.status === "complete" && styles.statusDone,
                  chore.status === "late" && styles.statusLate,
                ]}
              />
              <Text style={styles.choreLabel}>{chore.label}</Text>
              <Text style={styles.choreStatus}>{chore.status}</Text>
            </View>
          ))}
        </View>
      )}

      {myAssignments.length > 0 && (
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Routine assignments</Text>
          {myAssignments.map((a) => (
            <View key={a.routine_instance_id} style={styles.choreRow}>
              <View
                style={[
                  styles.statusDot,
                  a.status === "complete" && styles.statusDone,
                  a.status === "late" && styles.statusLate,
                ]}
              />
              <Text style={styles.choreLabel}>
                {a.member_name ?? "Assignment"}
              </Text>
              <Text style={styles.choreStatus}>{a.status}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { paddingTop: 8 },
  eyebrow: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1.6,
    textTransform: "uppercase",
  },
  title: {
    color: colors.textPrimary,
    fontSize: 30,
    fontWeight: "800",
    marginTop: 4,
    letterSpacing: -0.6,
  },
  tabLabel: {
    color: colors.textMuted,
    fontSize: 12,
    marginTop: 4,
    fontWeight: "600",
  },
  card: {
    backgroundColor: colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 16,
    marginTop: 16,
  },
  sectionTitle: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 1.2,
    marginBottom: 12,
  },
  statsRow: {
    flexDirection: "row",
    justifyContent: "space-around",
  },
  stat: { alignItems: "center" },
  statValue: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: "800",
  },
  statWarn: { color: colors.negative },
  statLabel: {
    color: colors.textMuted,
    fontSize: 10,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.6,
    marginTop: 2,
  },
  missBlock: { marginTop: 12, paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.divider },
  missLabel: {
    color: colors.warning,
    fontSize: 10,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 0.8,
    marginBottom: 4,
  },
  missLine: { color: colors.textSecondary, fontSize: 12, marginTop: 2 },
  choreRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.surfaceMuted,
    marginRight: 10,
  },
  statusDone: { backgroundColor: colors.positive },
  statusLate: { backgroundColor: colors.negative },
  choreLabel: { flex: 1, color: colors.textPrimary, fontSize: 13, fontWeight: "600" },
  choreStatus: {
    color: colors.textMuted,
    fontSize: 10,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  body: {
    color: colors.textMuted,
    fontSize: 13,
    textAlign: "center",
    lineHeight: 18,
  },
});
