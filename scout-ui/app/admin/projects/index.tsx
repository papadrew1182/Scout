import { useState } from "react";
import { useRouter } from "expo-router";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { useHasPermission } from "../../../lib/permissions";
import { useProjects, useProjectTemplates } from "../../../lib/projects";
import { colors, fonts, shared } from "../../../lib/styles";

type Tab = "all" | "templates" | "health";

export default function AdminProjects() {
  const router = useRouter();
  const canManageAny = useHasPermission("projects.manage_any");
  const [tab, setTab] = useState<Tab>("all");
  const { projects, loading } = useProjects({ status: "all" });
  const { templates, loading: tplLoading } = useProjectTemplates();

  if (!canManageAny) {
    return (
      <View style={{ padding: 20 }}>
        <Text style={{ color: colors.muted, fontFamily: fonts.body }}>
          You need projects.manage_any to view this page.
        </Text>
      </View>
    );
  }

  const active = projects.filter((p) => p.status === "active" || p.status === "draft");

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Projects (admin)</Text>

      <View style={styles.tabsRow}>
        {(["all", "templates", "health"] as Tab[]).map((t) => (
          <Pressable
            key={t}
            style={[styles.tab, tab === t && styles.tabActive]}
            onPress={() => setTab(t)}
            accessibilityRole="button"
            accessibilityLabel={`${t} tab`}
          >
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>
              {t === "all" ? "All projects" : t === "templates" ? "Family templates" : "Health"}
            </Text>
          </Pressable>
        ))}
      </View>

      {tab === "all" && (
        <View style={{ gap: 8 }}>
          {loading ? (
            <ActivityIndicator color={colors.purple} />
          ) : projects.length === 0 ? (
            <Text style={styles.muted}>No projects yet.</Text>
          ) : (
            projects.map((p) => (
              <Pressable
                key={p.id}
                style={shared.card}
                onPress={() => router.push(`/projects/${p.id}` as any)}
                accessibilityRole="link"
                accessibilityLabel={`Open ${p.name}`}
              >
                <Text style={styles.name}>{p.name}</Text>
                <Text style={styles.muted}>
                  {p.category} · {p.status} · starts {p.start_date}
                </Text>
              </Pressable>
            ))
          )}
        </View>
      )}

      {tab === "templates" && (
        <View style={{ gap: 8 }}>
          {tplLoading ? (
            <ActivityIndicator color={colors.purple} />
          ) : templates.length === 0 ? (
            <View style={shared.card}>
              <Text style={shared.cardTitle}>No templates yet</Text>
              <Text style={styles.muted}>
                Built-in templates ship in a later sprint. For now, create family-local
                templates through the API.
              </Text>
            </View>
          ) : (
            templates.map((t) => (
              <View key={t.id} style={shared.card}>
                <Text style={styles.name}>{t.name}</Text>
                <Text style={styles.muted}>
                  {t.category}
                  {t.estimated_duration_days
                    ? ` · ${t.estimated_duration_days} days`
                    : ""}
                </Text>
                {t.description && <Text style={styles.body}>{t.description}</Text>}
              </View>
            ))
          )}
        </View>
      )}

      {tab === "health" && (
        <View style={shared.card}>
          <Text style={shared.cardTitle}>Active projects</Text>
          <Text style={styles.muted}>
            {active.length} project{active.length === 1 ? "" : "s"} running.
          </Text>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 12, paddingBottom: 48 },
  h1: { fontSize: 22, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  muted: { fontSize: 12, color: colors.muted, fontFamily: fonts.body },
  body: { fontSize: 12, color: colors.text, fontFamily: fonts.body, marginTop: 6 },
  name: { fontSize: 14, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  tabsRow: { flexDirection: "row", gap: 6 },
  tab: {
    flex: 1,
    alignItems: "center",
    paddingVertical: 8,
    borderBottomWidth: 2,
    borderBottomColor: "transparent",
  },
  tabActive: { borderBottomColor: colors.purple },
  tabText: { fontSize: 12, color: colors.muted, fontFamily: fonts.body },
  tabTextActive: { color: colors.purple, fontWeight: "600" },
});
