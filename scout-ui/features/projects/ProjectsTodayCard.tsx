/**
 * Today-surface card: project tasks due today for the current member.
 *
 * Populated directly from scout.project_tasks via /api/projects/today/me.
 * Independent of promotion into personal_tasks — see Phase 3 spec.
 */

import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import { useMyProjectTasksToday } from "../../lib/projects";
import { colors, fonts } from "../../lib/styles";

export function ProjectsTodayCard() {
  const router = useRouter();
  const { tasks, loading } = useMyProjectTasksToday();

  if (loading || tasks.length === 0) return null;

  return (
    <View style={styles.card} testID="projects-today-card">
      <Text style={styles.header}>Projects due today</Text>
      {tasks.map((t) => (
        <Pressable
          key={t.id}
          style={styles.row}
          onPress={() => router.push(`/projects/${t.project_id}` as any)}
          accessibilityRole="link"
          accessibilityLabel={`Open project task ${t.title}`}
        >
          <Text style={styles.title}>{t.title}</Text>
          <Text style={styles.muted}>
            {t.status}
            {t.due_date ? ` · due ${t.due_date}` : ""}
          </Text>
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderRadius: 14,
    padding: 14,
    gap: 8,
    marginBottom: 12,
  },
  header: {
    fontSize: 13,
    fontWeight: "600",
    color: colors.text,
    fontFamily: fonts.body,
  },
  row: {
    paddingVertical: 6,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  title: { fontSize: 13, color: colors.text, fontFamily: fonts.body, fontWeight: "500" },
  muted: { fontSize: 11, color: colors.muted, fontFamily: fonts.body },
});
