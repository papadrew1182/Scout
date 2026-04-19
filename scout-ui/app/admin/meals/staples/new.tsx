import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { colors, fonts, shared } from "../../../../lib/styles";
import { useHasPermission } from "../../../../lib/permissions";

const API_BASE_URL = process.env.EXPO_PUBLIC_SCOUT_API_URL || "http://localhost:8000";

const PATTERN_CATEGORIES = [
  "assembly_line",
  "batch_cook",
  "one_pot",
  "sheet_pan",
  "slow_cooker",
  "grill",
  "stir_fry",
  "salad",
];

export default function NewMealStaple() {
  const canManage = useHasPermission("meals.manage_staples");
  const [name, setName] = useState("");
  const [baseProtein, setBaseProtein] = useState("");
  const [pattern, setPattern] = useState("one_pot");
  const [prepMinutes, setPrepMinutes] = useState("");
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
      const token = typeof localStorage !== "undefined"
        ? localStorage.getItem("scout_session_token")
        : null;
      const familyId = typeof localStorage !== "undefined"
        ? localStorage.getItem("scout_family_id")
        : null;
      if (!token || !familyId) throw new Error("Not signed in");

      const res = await fetch(`${API_BASE_URL}/families/${familyId}/meals`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          title: name.trim(),
          meal_type: "dinner",
          meal_date: new Date().toISOString().split("T")[0],
          description: [
            baseProtein.trim() ? `Protein: ${baseProtein.trim()}` : "",
            `Pattern: ${pattern}`,
            prepMinutes.trim() ? `Prep: ${prepMinutes.trim()} min` : "",
          ].filter(Boolean).join(". "),
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      setMsg({ kind: "ok", text: "Meal staple created" });
      setName("");
      setBaseProtein("");
      setPattern("one_pot");
      setPrepMinutes("");
    } catch (e: any) {
      setMsg({ kind: "err", text: e?.message ?? "Failed to create" });
    } finally {
      setSaving(false);
    }
  };

  if (!canManage) {
    return (
      <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
        <Text style={styles.h1}>Add Staple Meal</Text>
        <Text style={styles.muted}>You do not have permission to manage meal staples.</Text>
      </ScrollView>
    );
  }

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Add Staple Meal</Text>

      <View style={shared.card}>
        <Text style={styles.label}>Name</Text>
        <TextInput
          style={styles.input}
          value={name}
          onChangeText={setName}
          placeholder="e.g. Shredded Salsa Chicken"
          placeholderTextColor={colors.muted}
          editable={!saving}
          accessibilityLabel="Meal name"
        />

        <Text style={styles.label}>Base protein (optional)</Text>
        <TextInput
          style={styles.input}
          value={baseProtein}
          onChangeText={setBaseProtein}
          placeholder="e.g. chicken thighs"
          placeholderTextColor={colors.muted}
          editable={!saving}
          accessibilityLabel="Base protein"
        />

        <Text style={styles.label}>Pattern category</Text>
        <View style={styles.chipRow}>
          {PATTERN_CATEGORIES.map((opt) => (
            <Pressable
              key={opt}
              style={[styles.chip, pattern === opt && styles.chipActive]}
              onPress={() => setPattern(opt)}
              accessibilityRole="button"
              accessibilityLabel={`Pattern: ${opt.replace(/_/g, " ")}`}
            >
              <Text style={[styles.chipText, pattern === opt && styles.chipTextActive]}>
                {opt.replace(/_/g, " ")}
              </Text>
            </Pressable>
          ))}
        </View>

        <Text style={styles.label}>Estimated prep (minutes, optional)</Text>
        <TextInput
          style={styles.input}
          value={prepMinutes}
          onChangeText={setPrepMinutes}
          placeholder="e.g. 30"
          placeholderTextColor={colors.muted}
          keyboardType="numeric"
          editable={!saving}
          accessibilityLabel="Prep time in minutes"
        />

        {msg && (
          <Text style={[styles.msg, msg.kind === "err" && styles.msgErr]}>{msg.text}</Text>
        )}

        <Pressable
          style={[styles.btn, saving && styles.btnDisabled]}
          onPress={submit}
          disabled={saving}
          accessibilityRole="button"
          accessibilityLabel="Create staple meal"
        >
          {saving ? (
            <ActivityIndicator size="small" color="#FFFFFF" />
          ) : (
            <Text style={styles.btnText}>Add staple</Text>
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
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  chipActive: { backgroundColor: colors.purple, borderColor: colors.purple },
  chipText: { fontSize: 11, color: colors.text, fontWeight: "600", fontFamily: fonts.body },
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
