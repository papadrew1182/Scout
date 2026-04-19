import React, { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, fonts, shared } from "../../lib/styles";
import {
  AffirmationPreferences as PrefsType,
  getAffirmationPreferences,
  updateAffirmationPreferences,
} from "../../lib/affirmations";

const TONES = ["encouraging", "challenging", "reflective", "practical"];
const PHILOSOPHIES = ["discipline", "gratitude", "resilience", "faith-based", "family-first"];

export function AffirmationPreferences() {
  const [prefs, setPrefs] = useState<PrefsType | null>(null);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    getAffirmationPreferences()
      .then(setPrefs)
      .catch(() => {});
  }, []);

  if (!prefs) return null;

  const toggleChip = (list: string[], item: string): string[] =>
    list.includes(item) ? list.filter((i) => i !== item) : [...list, item];

  const update = (patch: Partial<PrefsType>) => {
    setPrefs({ ...prefs, ...patch });
    setDirty(true);
  };

  const save = async () => {
    if (!prefs) return;
    setSaving(true);
    try {
      const saved = await updateAffirmationPreferences({
        preferred_tones: prefs.preferred_tones,
        preferred_philosophies: prefs.preferred_philosophies,
        excluded_themes: prefs.excluded_themes,
        preferred_length: prefs.preferred_length,
      });
      setPrefs(saved);
      setDirty(false);
    } catch {
      // keep dirty state so user can retry
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={[shared.card, styles.container]}>
      <Text style={styles.title}>Affirmation Preferences</Text>

      <Text style={styles.label}>Tone</Text>
      <View style={styles.chipRow}>
        {TONES.map((t) => (
          <Chip
            key={t}
            label={t}
            selected={prefs.preferred_tones.includes(t)}
            onPress={() => update({ preferred_tones: toggleChip(prefs.preferred_tones, t) })}
          />
        ))}
      </View>

      <Text style={styles.label}>Philosophy</Text>
      <View style={styles.chipRow}>
        {PHILOSOPHIES.map((p) => (
          <Chip
            key={p}
            label={p}
            selected={prefs.preferred_philosophies.includes(p)}
            onPress={() => update({ preferred_philosophies: toggleChip(prefs.preferred_philosophies, p) })}
          />
        ))}
      </View>

      <Text style={styles.label}>Avoid</Text>
      <View style={styles.chipRow}>
        {PHILOSOPHIES.map((p) => (
          <Chip
            key={p}
            label={p}
            selected={prefs.excluded_themes.includes(p)}
            onPress={() => update({ excluded_themes: toggleChip(prefs.excluded_themes, p) })}
          />
        ))}
      </View>

      <Text style={styles.label}>Length</Text>
      <View style={styles.chipRow}>
        {["short", "medium"].map((l) => (
          <Chip
            key={l}
            label={l}
            selected={prefs.preferred_length === l}
            onPress={() => update({ preferred_length: l })}
          />
        ))}
      </View>

      {dirty && (
        <Pressable
          style={[styles.saveBtn, saving && styles.saveBtnDisabled]}
          onPress={save}
          disabled={saving}
          accessibilityRole="button"
          accessibilityLabel="Save affirmation preferences"
        >
          <Text style={styles.saveBtnText}>{saving ? "Saving..." : "Save"}</Text>
        </Pressable>
      )}
    </View>
  );
}

function Chip({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      style={[styles.chip, selected && styles.chipSelected]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected }}
    >
      <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 4 },
  title: { fontSize: 15, fontWeight: "600", color: colors.text, fontFamily: fonts.body, marginBottom: 8 },
  label: { fontSize: 13, fontWeight: "500", color: colors.muted, fontFamily: fonts.body, marginTop: 10 },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 6 },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipSelected: {
    backgroundColor: colors.purpleLight,
    borderColor: colors.purple,
  },
  chipText: { fontSize: 13, color: colors.muted, fontFamily: fonts.body },
  chipTextSelected: { color: colors.purple, fontWeight: "500" },
  saveBtn: {
    marginTop: 14,
    backgroundColor: colors.purple,
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: "center",
  },
  saveBtnDisabled: { opacity: 0.6 },
  saveBtnText: { color: "#fff", fontWeight: "600", fontSize: 14, fontFamily: fonts.body },
});
