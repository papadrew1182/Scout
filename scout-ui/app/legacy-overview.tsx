/**
 * Legacy "Family Overview" widget.
 *
 * The Session 3 redirect at `app/index.tsx` sends `/` to `/today`. This
 * route preserves the per-child progress widget that used to live at
 * `/` so it is still reachable from the legacy NavBar / "More" link
 * during the Session 3 transition. Nothing in the new shell links to
 * it — it exists only as a survival net for any code or muscle memory
 * that still expects it.
 */

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { ChildProgressRow } from "../components/ChildProgressRow";
import { fetchMembers, fetchTaskInstances, generateTasks } from "../lib/api";
import { todayStr } from "../lib/format";
import { shared, colors } from "../lib/styles";
import type { FamilyMember, TaskInstance } from "../lib/types";

export default function LegacyOverview() {
  const [children, setChildren] = useState<FamilyMember[]>([]);
  const [tasks, setTasks] = useState<TaskInstance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const today = todayStr();

      const members = await fetchMembers();
      const kids = members.filter((m) => m.role === "child" && m.is_active);
      setChildren(kids);

      let todayTasks = await fetchTaskInstances(today);
      if (todayTasks.length === 0) {
        todayTasks = await generateTasks(today);
      }
      setTasks(todayTasks);
    } catch (e: any) {
      setError(e.message ?? "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <View style={shared.pageCenter}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={shared.pageCenter}>
        <Text style={shared.errorLarge}>{error}</Text>
      </View>
    );
  }

  return (
    <View style={local.container}>
      <Text style={local.heading}>Family Overview (legacy)</Text>
      <Text style={local.date}>{todayStr()}</Text>
      <FlatList
        data={children}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => {
          const memberTasks = tasks.filter((t) => t.family_member_id === item.id);
          const completed = memberTasks.filter((t) => t.is_completed).length;
          return (
            <ChildProgressRow
              member={item}
              totalTasks={memberTasks.length}
              completedTasks={completed}
            />
          );
        }}
        contentContainerStyle={local.list}
      />
    </View>
  );
}

const local = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg, padding: 20 },
  heading: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: "700",
    marginBottom: 4,
  },
  date: {
    color: colors.textMuted,
    fontSize: 13,
    marginBottom: 20,
  },
  list: { gap: 12 },
});
