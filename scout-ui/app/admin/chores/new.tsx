import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { colors, fonts, shared } from "../../../lib/styles";
import { createChoreTemplate } from "../../../lib/api";
import { useHasPermission } from "../../../lib/permissions";

const CADENCE_OPTIONS = ["daily", "weekly", "monthly", "odd-even"];

export default function NewChoreTemplate() {
  const canManage = useHasPermission("chores.manage_config");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [cadence, setCadence] = useState("daily");
  const [dueTime, setDueTime] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const submit = async () => {
    if (!name.trim()) {
      setMsg({ kind: "err", text: "Name is required" });
      return;
    }
    setSaving(true);
    setMsg(null);
    try {
      await createChoreTemplate({
        name: name.trim(),
        description: description.trim() || undefined,
        recurrence: cadence,
        due_time: dueTime.trim() || undefined,
        // Backend CHECK constraint only allows fixed/rotating_daily/rotating_weekly.
        // Default to fixed with empty rule; an assignee picker can be
        // added later to populate assignment_rule.assigned_to.
        assignment_type: "fixed",
        assignment_rule: {},
      });
      setMsg({ kind: "ok", text: "Template created" });
      setName("");
      setDescription("");
      setCadence("daily");
      setDueTime("");
    } catch (e: any) {
      setMsg({ kind: "err", text: e?.message ?? "Failed to create" });
    } finally {
      setSaving(false);
    }
  };

  if (!canManage) {
    return (
      <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
        <Text style={styles.h1}>New Chore Template</Text>
        <Text style={styles.muted}>You do not have permission to create chore templates.</Text>
      </ScrollView>
    );
  }

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>New Chore Template</Text>

      <View style={shared.card}>
        <Text style={styles.label}>Name</Text>
        <TextInput
          style={styles.input}
          value={name}
          onChangeText={setName}
          placeholder="e.g. Clean bedroom"
          placeholderTextColor={colors.muted}
          editable={!saving}
          accessibilityLabel="Chore name"
        />

        <Text style={styles.label}>Description (optional)</Text>
        <TextInput
          style={[styles.input, { minHeight: 60, textAlignVertical: "top" }]}
          value={description}
          onChangeText={setDescription}
          placeholder="What does this chore involve?"
          placeholderTextColor={colors.muted}
          multiline
          editable={!saving}
          accessibilityLabel="Chore description"
        />

        <Text style={styles.label}>Cadence</Text>
        <View style={styles.chipRow}>
          {CADENCE_OPTIONS.map((opt) => (
            <Pressable
              key={opt}
              style={[styles.chip, cadence === opt && styles.chipActive]}
              onPress={() => setCadence(opt)}
              accessibilityRole="button"
              accessibilityLabel={`Cadence: ${opt}`}
            >
              <Text style={[styles.chipText, cadence === opt && styles.chipTextActive]}>
                {opt}
              </Text>
            </Pressable>
          ))}
        </View>

        <Text style={styles.label}>Due time (optional)</Text>
        <TextInput
          style={styles.input}
          value={dueTime}
          onChangeText={setDueTime}
          placeholder="HH:MM (24h)"
          placeholderTextColor={colors.muted}
          editable={!saving}
          accessibilityLabel="Due time"
        />

        {msg && (
          <Text style={[styles.msg, msg.kind === "err" && styles.msgErr]}>{msg.text}</Text>
        )}

        <Pressable
          style={[styles.btn, saving && styles.btnDisabled]}
          onPress={submit}
          disabled={saving}
          accessibilityRole="button"
          accessibilityLabel="Create template"
        >
          {saving ? (
            <ActivityIndicator size="small" color="#FFFFFF" />
          ) : (
            <Text style={styles.btnText}>Create template</Text>
          )}
        </Pressable>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  h1: { fontSize: 22, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  muted: { fontSize: 13, color: colors.muted, fontFamily: fonts.body },
  label: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.muted,
    fontFamily: fonts.body,
    textTransform: "uppercase",
    letterSpacing: 0.8,
    marginTop: 14,
    marginBottom: 6,
  },
  input: {
    backgroundColor: colors.surfaceMuted,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 13,
    color: colors.text,
    fontFamily: fonts.body,
  },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    backgroundColor: colors.surfaceMuted,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  chipActive: { backgroundColor: colors.purple, borderColor: colors.purple },
  chipText: { fontSize: 12, color: colors.text, fontWeight: "600", fontFamily: fonts.body },
  chipTextActive: { color: "#FFFFFF" },
  msg: { fontSize: 12, color: colors.green, fontFamily: fonts.body, marginTop: 10 },
  msgErr: { color: colors.red },
  btn: {
    backgroundColor: colors.purple,
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
    marginTop: 18,
  },
  btnDisabled: { backgroundColor: colors.border },
  btnText: { color: "#FFFFFF", fontSize: 13, fontWeight: "600", fontFamily: fonts.body },
});
