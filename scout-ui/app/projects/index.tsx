import { useRouter } from "expo-router";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { useProjects } from "../../lib/projects";
import { colors, fonts, shared } from "../../lib/styles";

const CATEGORY_LABEL: Record<string, string> = {
  birthday: "Birthday",
  holiday: "Holiday",
  trip: "Trip",
  school_event: "School event",
  home_project: "Home project",
  weekend_reset: "Weekend reset",
  custom: "Custom",
};

export default function ProjectsList() {
  const router = useRouter();
  const { projects, loading, error } = useProjects({ status: "active" });

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <View style={styles.headerRow}>
        <Text style={styles.h1}>Projects</Text>
        <Pressable
          style={styles.btnPrimary}
          onPress={() => router.push("/projects/new")}
          accessibilityRole="button"
          accessibilityLabel="New project"
        >
          <Text style={styles.btnPrimaryText}>New project</Text>
        </Pressable>
      </View>

      {loading ? (
        <ActivityIndicator color={colors.purple} />
      ) : error ? (
        <Text style={styles.errorText}>{error}</Text>
      ) : projects.length === 0 ? (
        <View style={shared.card}>
          <Text style={shared.cardTitle}>No active projects yet</Text>
          <Text style={styles.muted}>
            Family projects are multi-week efforts with tasks, deadlines, and budgets.
            Tap New project to create your first one.
          </Text>
        </View>
      ) : (
        projects.map((p) => (
          <Pressable
            key={p.id}
            style={shared.card}
            onPress={() => router.push(`/projects/${p.id}` as any)}
            accessibilityRole="link"
            accessibilityLabel={`Open ${p.name}`}
          >
            <Text style={styles.projectName}>{p.name}</Text>
            <Text style={styles.muted}>
              {CATEGORY_LABEL[p.category] ?? p.category} · status {p.status} · starts{" "}
              {p.start_date}
              {p.target_end_date ? ` → ${p.target_end_date}` : ""}
            </Text>
            {p.description && <Text style={styles.description}>{p.description}</Text>}
          </Pressable>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 12, paddingBottom: 48 },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  h1: { fontSize: 22, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  projectName: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.text,
    fontFamily: fonts.body,
    marginBottom: 4,
  },
  description: { fontSize: 12, color: colors.text, marginTop: 6, fontFamily: fonts.body },
  muted: { fontSize: 12, color: colors.muted, fontFamily: fonts.body },
  errorText: { fontSize: 12, color: colors.red, fontFamily: fonts.body },
  btnPrimary: {
    backgroundColor: colors.purple,
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  btnPrimaryText: { color: "#FFFFFF", fontSize: 12, fontWeight: "500", fontFamily: fonts.body },
});
