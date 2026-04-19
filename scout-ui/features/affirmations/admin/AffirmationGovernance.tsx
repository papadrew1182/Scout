import React, { useEffect, useState } from "react";
import { Pressable, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import { colors, fonts, shared } from "../../../lib/styles";
import { fetchAffirmationConfig, updateAffirmationConfig } from "../../../lib/affirmations";

const DEFAULT_CONFIG = {
  enabled: true,
  cooldown_days: 3,
  max_repeat_window_days: 30,
  weight_heart_boost: 1.5,
  weight_preference_match: 1.3,
  dynamic_generation_enabled: false,
  moderation_required: false,
};

export function AffirmationGovernance() {
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchAffirmationConfig()
      .then((res) => setConfig({ ...DEFAULT_CONFIG, ...res.value }))
      .catch(() => {});
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      await updateAffirmationConfig(config);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      // keep state
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={[shared.card, styles.container]}>
      <Row label="Feature enabled">
        <Switch value={config.enabled} onValueChange={(v) => setConfig({ ...config, enabled: v })} />
      </Row>
      <NumericRow label="Cooldown (days)" value={config.cooldown_days} onChange={(v) => setConfig({ ...config, cooldown_days: v })} />
      <NumericRow label="Max repeat window (days)" value={config.max_repeat_window_days} onChange={(v) => setConfig({ ...config, max_repeat_window_days: v })} />
      <NumericRow label="Heart boost weight" value={config.weight_heart_boost} onChange={(v) => setConfig({ ...config, weight_heart_boost: v })} step={0.1} />
      <NumericRow label="Preference match weight" value={config.weight_preference_match} onChange={(v) => setConfig({ ...config, weight_preference_match: v })} step={0.1} />
      <Row label="Dynamic generation">
        <Switch value={config.dynamic_generation_enabled} onValueChange={(v) => setConfig({ ...config, dynamic_generation_enabled: v })} />
      </Row>
      <Row label="Moderation required">
        <Switch value={config.moderation_required} onValueChange={(v) => setConfig({ ...config, moderation_required: v })} />
      </Row>
      <Pressable style={[styles.saveBtn, saving && { opacity: 0.6 }]} onPress={save} disabled={saving} accessibilityRole="button">
        <Text style={styles.saveBtnText}>{saved ? "Saved ✓" : saving ? "Saving..." : "Save"}</Text>
      </Pressable>
    </View>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={styles.row}>
      <Text style={styles.label}>{label}</Text>
      {children}
    </View>
  );
}

function NumericRow({ label, value, onChange, step = 1 }: { label: string; value: number; onChange: (v: number) => void; step?: number }) {
  return (
    <View style={styles.row}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        style={styles.numInput}
        keyboardType="numeric"
        value={String(value)}
        onChangeText={(t) => {
          const n = step < 1 ? parseFloat(t) : parseInt(t, 10);
          if (!isNaN(n)) onChange(n);
        }}
        accessibilityLabel={label}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, gap: 2 },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border },
  label: { fontSize: 14, color: colors.text, fontFamily: fonts.body },
  numInput: { width: 70, borderWidth: 1, borderColor: colors.border, borderRadius: 6, paddingHorizontal: 10, paddingVertical: 6, textAlign: "center", fontSize: 14, fontFamily: fonts.body, color: colors.text },
  saveBtn: { marginTop: 16, backgroundColor: colors.purple, borderRadius: 8, paddingVertical: 10, alignItems: "center" },
  saveBtnText: { color: "#fff", fontWeight: "600", fontSize: 14, fontFamily: fonts.body },
});
