/**
 * Sprint 05 Phase 2 - /admin/ai/nudges
 *
 * Admin surface for managing family-wide proactive-nudge quiet hours.
 * Gated by `quiet_hours.manage` (PARENT + PRIMARY_PARENT per migration 050).
 *
 * Reads via GET /api/admin/family-config/quiet-hours and writes via PUT
 * on the same path. Per-member overrides are not in scope for Phase 2.
 */

import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useRouter } from "expo-router";

import {
  getFamilyQuietHours,
  putFamilyQuietHours,
  type QuietHoursConfig,
} from "../../../lib/nudges";
import { useHasPermission } from "../../../lib/permissions";
import { colors, fonts, shared } from "../../../lib/styles";

function minuteToHHMM(m: number): string {
  const hh = Math.floor(m / 60).toString().padStart(2, "0");
  const mm = (m % 60).toString().padStart(2, "0");
  return `${hh}:${mm}`;
}

function hhmmToMinute(s: string): number | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(s.trim());
  if (!match) return null;
  const h = parseInt(match[1], 10);
  const m = parseInt(match[2], 10);
  if (h < 0 || h > 23 || m < 0 || m > 59) return null;
  return h * 60 + m;
}

export default function AdminNudges() {
  const router = useRouter();
  const canManage = useHasPermission("quiet_hours.manage");

  const [config, setConfig] = useState<QuietHoursConfig | null>(null);
  const [startStr, setStartStr] = useState("22:00");
  const [endStr, setEndStr] = useState("07:00");
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!canManage) return;
    getFamilyQuietHours()
      .then((c) => {
        setConfig(c);
        setStartStr(minuteToHHMM(c.start_local_minute));
        setEndStr(minuteToHHMM(c.end_local_minute));
      })
      .catch(() => setError("Failed to load quiet hours."));
  }, [canManage]);

  const handleSave = async () => {
    setError(null);
    const start = hhmmToMinute(startStr);
    const end = hhmmToMinute(endStr);
    if (start === null || end === null) {
      setError("Use HH:MM format (00:00 to 23:59).");
      return;
    }
    if (start === end) {
      setError("Start and end must differ.");
      return;
    }
    setSaving(true);
    try {
      const updated = await putFamilyQuietHours(start, end);
      setConfig(updated);
      setSavedAt(new Date());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  };

  if (!canManage) {
    return (
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.h1}>Not available</Text>
        <Text style={styles.blurb}>
          Nudges admin requires the
          <Text style={styles.code}> quiet_hours.manage</Text> permission.
        </Text>
      </ScrollView>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <View style={styles.headerRow}>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <Text style={styles.backLink}>&larr; Admin</Text>
        </Pressable>
        <Text style={styles.h1}>Nudges</Text>
      </View>

      <View style={shared.card}>
        <Text style={shared.cardTitle}>Quiet hours</Text>
        <Text style={styles.blurb}>
          During quiet hours, low-severity nudges are suppressed and
          normal-severity nudges are held until the window ends.
          High-severity nudges are delivered anyway. Per-family window;
          per-member overrides ship in a later phase.
        </Text>

        {config === null && !error && (
          <ActivityIndicator color={colors.muted} style={{ marginTop: 8 }} />
        )}

        {config !== null && (
          <>
            <View style={styles.row}>
              <View style={styles.col}>
                <Text style={styles.label}>Start (local time)</Text>
                <TextInput
                  style={styles.input}
                  value={startStr}
                  onChangeText={setStartStr}
                  placeholder="22:00"
                  accessibilityLabel="Quiet hours start (HH:MM)"
                />
              </View>
              <View style={styles.col}>
                <Text style={styles.label}>End (local time)</Text>
                <TextInput
                  style={styles.input}
                  value={endStr}
                  onChangeText={setEndStr}
                  placeholder="07:00"
                  accessibilityLabel="Quiet hours end (HH:MM)"
                />
              </View>
            </View>

            {error && <Text style={styles.errorText}>{error}</Text>}

            <Pressable
              style={[styles.saveBtn, saving && styles.saveBtnBusy]}
              onPress={handleSave}
              disabled={saving}
              accessibilityRole="button"
              accessibilityLabel="Save quiet hours"
            >
              <Text style={styles.saveBtnText}>
                {saving ? "Saving..." : "Save"}
              </Text>
            </Pressable>

            {savedAt !== null && !error && (
              <Text style={styles.savedText}>
                Saved at {savedAt.toLocaleTimeString()}
              </Text>
            )}

            {config.is_default && (
              <Text style={styles.helperText}>
                Currently using the default 22:00 - 07:00 window. Your next
                save will persist a custom window for your family.
              </Text>
            )}
          </>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  headerRow: { gap: 6 },
  backLink: { color: colors.muted, fontSize: 14, fontFamily: fonts.body },
  h1: {
    fontSize: 22,
    fontWeight: "600",
    color: colors.text,
    fontFamily: fonts.body,
  },
  blurb: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
    fontFamily: fonts.body,
  },
  code: {
    fontFamily: "monospace",
    color: colors.text,
  },
  row: { flexDirection: "row", gap: 12, marginTop: 8 },
  col: { flex: 1 },
  label: {
    color: colors.muted,
    fontSize: 12,
    marginBottom: 4,
    fontFamily: fonts.body,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: 8,
    fontSize: 14,
    color: colors.text,
    fontFamily: fonts.body,
  },
  errorText: {
    color: "#dc2626",
    fontSize: 13,
    marginTop: 8,
    fontFamily: fonts.body,
  },
  saveBtn: {
    marginTop: 14,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 8,
    backgroundColor: "#1f2937",
    alignSelf: "flex-start",
  },
  saveBtnBusy: { opacity: 0.6 },
  saveBtnText: {
    color: "#ffffff",
    fontSize: 14,
    fontFamily: fonts.body,
  },
  savedText: {
    color: "#16a34a",
    fontSize: 13,
    marginTop: 10,
    fontFamily: fonts.body,
  },
  helperText: {
    color: colors.muted,
    fontSize: 12,
    marginTop: 10,
    fontFamily: fonts.body,
    fontStyle: "italic",
  },
});
