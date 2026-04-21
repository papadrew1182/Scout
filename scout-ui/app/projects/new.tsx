import { useState } from "react";
import { useRouter } from "expo-router";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { createProject, useProjectTemplates } from "../../lib/projects";
import type { ProjectCategory } from "../../lib/projects";
import { colors, fonts, shared } from "../../lib/styles";

const CATEGORIES: { id: ProjectCategory; label: string }[] = [
  { id: "birthday", label: "Birthday" },
  { id: "holiday", label: "Holiday" },
  { id: "trip", label: "Trip" },
  { id: "school_event", label: "School event" },
  { id: "home_project", label: "Home project" },
  { id: "weekend_reset", label: "Weekend reset" },
  { id: "custom", label: "Custom" },
];

export default function NewProject() {
  const router = useRouter();
  const { templates, loading: tplLoading } = useProjectTemplates();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<ProjectCategory>("custom");
  const [startDate, setStartDate] = useState(new Date().toISOString().slice(0, 10));
  const [templateId, setTemplateId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const p = await createProject({
        name,
        category,
        start_date: startDate,
        description: description || null,
        project_template_id: templateId,
        name_override: templateId ? name : null,
      });
      router.replace(`/projects/${p.id}` as any);
    } catch (e: any) {
      setError(e?.message ?? "Failed to create");
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>New project</Text>

      <View style={shared.card}>
        <Text style={shared.cardTitle}>From a template (optional)</Text>
        {tplLoading ? (
          <ActivityIndicator color={colors.purple} />
        ) : templates.length === 0 ? (
          <Text style={styles.muted}>No saved templates. Start from blank below.</Text>
        ) : (
          <View style={styles.chipRow}>
            <Pressable
              style={[styles.chip, templateId === null && styles.chipActive]}
              onPress={() => setTemplateId(null)}
              accessibilityRole="button"
              accessibilityLabel="Blank project"
            >
              <Text
                style={[styles.chipText, templateId === null && styles.chipTextActive]}
              >
                Blank
              </Text>
            </Pressable>
            {templates.map((t) => (
              <Pressable
                key={t.id}
                style={[styles.chip, templateId === t.id && styles.chipActive]}
                onPress={() => {
                  setTemplateId(t.id);
                  setCategory(t.category);
                  if (!name) setName(t.name);
                }}
                accessibilityRole="button"
                accessibilityLabel={`Template ${t.name}`}
              >
                <Text
                  style={[styles.chipText, templateId === t.id && styles.chipTextActive]}
                >
                  {t.name}
                </Text>
              </Pressable>
            ))}
          </View>
        )}
      </View>

      <View style={shared.card}>
        <Text style={shared.cardTitle}>Details</Text>
        <TextInput
          style={styles.input}
          value={name}
          onChangeText={setName}
          placeholder="Project name"
          placeholderTextColor={colors.muted}
        />
        <TextInput
          style={styles.input}
          value={description}
          onChangeText={setDescription}
          placeholder="Description (optional)"
          placeholderTextColor={colors.muted}
          multiline
        />
        <TextInput
          style={styles.input}
          value={startDate}
          onChangeText={setStartDate}
          placeholder="Start date (YYYY-MM-DD)"
          placeholderTextColor={colors.muted}
        />
        <Text style={[styles.muted, { marginBottom: 4 }]}>Category</Text>
        <View style={styles.chipRow}>
          {CATEGORIES.map((c) => (
            <Pressable
              key={c.id}
              style={[styles.chip, category === c.id && styles.chipActive]}
              onPress={() => setCategory(c.id)}
              accessibilityRole="button"
              accessibilityLabel={`Category ${c.label}`}
            >
              <Text style={[styles.chipText, category === c.id && styles.chipTextActive]}>
                {c.label}
              </Text>
            </Pressable>
          ))}
        </View>
      </View>

      {error && <Text style={styles.errorText}>{error}</Text>}

      <Pressable
        style={styles.btnPrimary}
        disabled={busy || !name || !startDate}
        onPress={submit}
        accessibilityRole="button"
        accessibilityLabel="Create project"
      >
        <Text style={styles.btnPrimaryText}>{busy ? "Creating…" : "Create project"}</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 12, paddingBottom: 48 },
  h1: { fontSize: 22, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  muted: { fontSize: 12, color: colors.muted, fontFamily: fonts.body },
  errorText: { fontSize: 12, color: colors.red, fontFamily: fonts.body },

  input: {
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 9,
    fontSize: 12,
    color: colors.text,
    marginBottom: 8,
    fontFamily: fonts.body,
  },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginBottom: 6 },
  chip: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.bg,
  },
  chipActive: { backgroundColor: colors.purple, borderColor: colors.purple },
  chipText: { color: colors.text, fontSize: 12, fontFamily: fonts.body },
  chipTextActive: { color: "#FFFFFF" },
  btnPrimary: {
    backgroundColor: colors.purple,
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: "center",
  },
  btnPrimaryText: { color: "#FFFFFF", fontSize: 12, fontWeight: "500", fontFamily: fonts.body },
});
