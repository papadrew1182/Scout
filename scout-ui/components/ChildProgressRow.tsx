import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "../lib/styles";
import type { FamilyMember } from "../lib/types";

interface Props {
  member: FamilyMember;
  totalTasks: number;
  completedTasks: number;
}

export function ChildProgressRow({ member, totalTasks, completedTasks }: Props) {
  const router = useRouter();
  const allDone = totalTasks > 0 && completedTasks === totalTasks;
  const pct = totalTasks > 0 ? (completedTasks / totalTasks) * 100 : 0;

  return (
    <Pressable
      style={styles.row}
      onPress={() => router.push(`/child/${member.id}`)}
    >
      <View style={styles.top}>
        <Text style={styles.name}>{member.first_name}</Text>
        <Text style={[styles.count, allDone && styles.countDone]}>
          {completedTasks}/{totalTasks}
        </Text>
      </View>
      <View style={styles.barTrack}>
        <View
          style={[
            styles.barFill,
            { width: `${pct}%` },
            allDone && styles.barDone,
          ]}
        />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 16,
  },
  top: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 10,
  },
  name: { color: colors.textPrimary, fontSize: 18, fontWeight: "600" },
  count: { color: colors.textMuted, fontSize: 16 },
  countDone: { color: colors.positive },
  barTrack: {
    height: 6,
    backgroundColor: colors.surfaceMuted,
    borderRadius: 3,
    overflow: "hidden",
  },
  barFill: {
    height: 6,
    backgroundColor: colors.accent,
    borderRadius: 3,
  },
  barDone: { backgroundColor: colors.positive },
});
