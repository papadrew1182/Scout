/**
 * /admin/chores — Chores admin screen
 *
 * Section 1: Per-kid routines (editable list — name + pts, add/remove/edit)
 * Section 2: Family rules (streak config, max daily pts cap, requires_check_off toggle)
 * Section 3: Analytics stub
 */

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import { Redirect } from "expo-router";

import { shared, colors, fonts, radii } from "../../../lib/styles";
import { useHasPermission } from "../../../lib/permissions";
import { useMemberConfig } from "../../../lib/config";
import { useFamilyConfig } from "../../../lib/config";
import { fetchMembers } from "../../../lib/api";
import type { FamilyMember } from "../../../lib/types";
import type { ChoreRoutine, ChoresRoutinesConfig, ChoresRules } from "../../../lib/chores";
import { DEFAULT_CHORES_ROUTINES_CONFIG, DEFAULT_CHORES_RULES } from "../../../lib/chores";

// ---------------------------------------------------------------------------
// Per-kid routines editor component
// ---------------------------------------------------------------------------

interface KidRoutinesRowProps {
  kid: FamilyMember;
}

function KidRoutinesRow({ kid }: KidRoutinesRowProps) {
  const { value, setValue, loading } = useMemberConfig<ChoresRoutinesConfig>(
    kid.id,
    "chores.routines",
    DEFAULT_CHORES_ROUTINES_CONFIG,
  );

  // Local draft state
  const [routines, setRoutines] = useState<ChoreRoutine[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Sync draft when config loads
  useEffect(() => {
    if (!loading) {
      setRoutines(Array.isArray(value.routines) ? value.routines : []);
    }
  }, [loading, value]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setSaveError(null);
    try {
      await setValue({ routines });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setSaveError("Save failed");
    } finally {
      setSaving(false);
    }
  }, [setValue, routines]);

  const handleAddRoutine = useCallback(() => {
    const newId = `routine_${Date.now()}`;
    setRoutines((prev) => [...prev, { id: newId, name: "", pts: 10 }]);
  }, []);

  const handleRemoveRoutine = useCallback((id: string) => {
    setRoutines((prev) => prev.filter((r) => r.id !== id));
  }, []);

  const handleUpdateName = useCallback((id: string, name: string) => {
    setRoutines((prev) => prev.map((r) => (r.id === id ? { ...r, name } : r)));
  }, []);

  const handleUpdatePts = useCallback((id: string, ptsStr: string) => {
    const pts = parseInt(ptsStr || "0", 10);
    setRoutines((prev) => prev.map((r) => (r.id === id ? { ...r, pts: isNaN(pts) ? 0 : pts } : r)));
  }, []);

  const initials = kid.first_name.slice(0, 2).toUpperCase();

  return (
    <View style={kidStyles.row}>
      <View style={kidStyles.header}>
        <View style={kidStyles.avatar}>
          <Text style={kidStyles.avatarText}>{initials}</Text>
        </View>
        <Text style={kidStyles.name}>{kid.first_name}</Text>
        {saved && <Text style={kidStyles.checkBadge}>Saved</Text>}
        {saveError && <Text style={kidStyles.errBadge}>{saveError}</Text>}
      </View>

      {loading ? (
        <ActivityIndicator size="small" color={colors.purple} style={{ marginTop: 8 }} />
      ) : (
        <View style={kidStyles.body}>
          {/* Column headers */}
          {routines.length > 0 && (
            <View style={kidStyles.columnHeaders}>
              <Text style={[kidStyles.colHeader, { flex: 1 }]}>Routine</Text>
              <Text style={[kidStyles.colHeader, kidStyles.colPts]}>Pts</Text>
              <View style={kidStyles.colRemove} />
            </View>
          )}

          {/* Routine rows */}
          {routines.map((routine) => (
            <View key={routine.id} style={kidStyles.routineRow}>
              <TextInput
                style={[kidStyles.input, { flex: 1 }] as any}
                value={routine.name}
                onChangeText={(text) => handleUpdateName(routine.id, text)}
                placeholder="Routine name"
                placeholderTextColor={colors.muted}
              />
              <TextInput
                style={[kidStyles.input, kidStyles.ptsInput] as any}
                value={String(routine.pts)}
                onChangeText={(text) => handleUpdatePts(routine.id, text)}
                keyboardType="number-pad"
                placeholder="10"
                placeholderTextColor={colors.muted}
              />
              <Pressable
                style={kidStyles.removeBtn}
                onPress={() => handleRemoveRoutine(routine.id)}
                accessibilityRole="button"
                accessibilityLabel={`Remove routine ${routine.name}`}
              >
                <Text style={kidStyles.removeBtnText}>✕</Text>
              </Pressable>
            </View>
          ))}

          {routines.length === 0 && (
            <Text style={kidStyles.emptyText}>No routines yet. Add one below.</Text>
          )}

          {/* Add + Save row */}
          <View style={kidStyles.actionRow}>
            <Pressable
              style={kidStyles.addBtn}
              onPress={handleAddRoutine}
              accessibilityRole="button"
              accessibilityLabel={`Add routine for ${kid.first_name}`}
            >
              <Text style={kidStyles.addBtnText}>+ Add Routine</Text>
            </Pressable>

            <Pressable
              style={[kidStyles.saveBtn, saving && kidStyles.saveBtnDisabled]}
              onPress={handleSave}
              disabled={saving}
              accessibilityRole="button"
              accessibilityLabel={`Save routines for ${kid.first_name}`}
            >
              <Text style={kidStyles.saveBtnText}>{saving ? "Saving…" : "Save"}</Text>
            </Pressable>
          </View>
        </View>
      )}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Main screen
// ---------------------------------------------------------------------------

export default function ChoresAdmin() {
  const canManage = useHasPermission("chores.manage_config");

  const [kids, setKids] = useState<FamilyMember[]>([]);
  const [membersLoading, setMembersLoading] = useState(true);

  const {
    value: rules,
    setValue: setRules,
    loading: rulesLoading,
  } = useFamilyConfig<ChoresRules>("chores.rules", DEFAULT_CHORES_RULES);

  // Local draft for rules card
  const [streakDays, setStreakDays] = useState("");
  const [streakPts, setStreakPts] = useState("");
  const [maxDailyPts, setMaxDailyPts] = useState("");
  const [requiresCheckOff, setRequiresCheckOff] = useState(true);
  const [rulesSaving, setRulesSaving] = useState(false);
  const [rulesSaved, setRulesSaved] = useState(false);
  const [rulesError, setRulesError] = useState<string | null>(null);

  useEffect(() => {
    fetchMembers()
      .then((all) => setKids(all.filter((m) => m.role === "child" && m.is_active)))
      .catch(() => {})
      .finally(() => setMembersLoading(false));
  }, []);

  // Sync rules draft on load
  useEffect(() => {
    if (!rulesLoading) {
      setStreakDays(String(rules.streak_bonus_days));
      setStreakPts(String(rules.streak_bonus_pts));
      setMaxDailyPts(String(rules.max_daily_pts));
      setRequiresCheckOff(rules.requires_check_off);
    }
  }, [rulesLoading, rules]);

  const handleSaveRules = useCallback(async () => {
    setRulesSaving(true);
    setRulesError(null);
    try {
      await setRules({
        streak_bonus_days: parseInt(streakDays || "0", 10),
        streak_bonus_pts: parseInt(streakPts || "0", 10),
        max_daily_pts: parseInt(maxDailyPts || "0", 10),
        requires_check_off: requiresCheckOff,
      });
      setRulesSaved(true);
      setTimeout(() => setRulesSaved(false), 2000);
    } catch {
      setRulesError("Save failed");
    } finally {
      setRulesSaving(false);
    }
  }, [setRules, streakDays, streakPts, maxDailyPts, requiresCheckOff]);

  if (!canManage) {
    return <Redirect href="/admin" />;
  }

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Chores</Text>
      <Text style={styles.subtitle}>
        Configure per-kid routines, point values, and family streak rules.
      </Text>

      {/* ------------------------------------------------------------------ */}
      {/* Section 1: Per-kid routines                                         */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Per-kid routines</Text>
        </View>
        {membersLoading ? (
          <ActivityIndicator size="small" color={colors.purple} />
        ) : kids.length === 0 ? (
          <Text style={styles.empty}>No active children found.</Text>
        ) : (
          kids.map((kid, idx) => (
            <View key={kid.id}>
              {idx > 0 && <View style={styles.divider} />}
              <KidRoutinesRow kid={kid} />
            </View>
          ))
        )}
      </View>

      {/* ------------------------------------------------------------------ */}
      {/* Section 2: Family rules                                             */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Family chore rules</Text>
          {rulesSaved && <Text style={styles.savedBadge}>Saved</Text>}
          {rulesError && <Text style={styles.errorBadge}>{rulesError}</Text>}
        </View>

        {rulesLoading ? (
          <ActivityIndicator size="small" color={colors.purple} />
        ) : (
          <View style={styles.rulesBody}>
            <View style={styles.toggleRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.fieldLabel}>Requires check-off</Text>
                <Text style={styles.fieldHint}>
                  Chores must be marked complete by a parent before points are awarded.
                </Text>
              </View>
              <Switch
                value={requiresCheckOff}
                onValueChange={setRequiresCheckOff}
                trackColor={{ true: colors.purple, false: colors.border }}
                thumbColor={colors.card}
              />
            </View>

            <View style={styles.rulesFields}>
              <View style={styles.rulesFieldGroup}>
                <Text style={styles.fieldLabel}>Streak bonus days</Text>
                <TextInput
                  style={styles.input as any}
                  value={streakDays}
                  onChangeText={setStreakDays}
                  keyboardType="number-pad"
                  placeholder="7"
                  placeholderTextColor={colors.muted}
                />
              </View>

              <View style={styles.rulesFieldGroup}>
                <Text style={styles.fieldLabel}>Streak bonus pts</Text>
                <TextInput
                  style={styles.input as any}
                  value={streakPts}
                  onChangeText={setStreakPts}
                  keyboardType="number-pad"
                  placeholder="20"
                  placeholderTextColor={colors.muted}
                />
              </View>

              <View style={styles.rulesFieldGroup}>
                <Text style={styles.fieldLabel}>Max daily pts cap</Text>
                <TextInput
                  style={styles.input as any}
                  value={maxDailyPts}
                  onChangeText={setMaxDailyPts}
                  keyboardType="number-pad"
                  placeholder="100"
                  placeholderTextColor={colors.muted}
                />
              </View>
            </View>

            <Pressable
              style={[styles.saveBtn, rulesSaving && styles.saveBtnDisabled]}
              onPress={handleSaveRules}
              disabled={rulesSaving}
              accessibilityRole="button"
              accessibilityLabel="Save family chore rules"
            >
              <Text style={styles.saveBtnText}>
                {rulesSaving ? "Saving…" : "Save Rules"}
              </Text>
            </Pressable>
          </View>
        )}
      </View>

      {/* ------------------------------------------------------------------ */}
      {/* Section 3: Analytics stub                                           */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Analytics</Text>
        </View>
        <Text style={styles.stubText}>
          Coming soon — chore completion trends, streak leaderboard.
        </Text>
      </View>
    </ScrollView>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  content: { padding: 20, paddingBottom: 48, gap: 14 },
  h1: { fontSize: 20, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  subtitle: { fontSize: 13, color: colors.muted, fontFamily: fonts.body, lineHeight: 19, marginTop: -4 },
  divider: { height: 1, backgroundColor: colors.border, marginVertical: 12 },
  empty: { fontSize: 13, color: colors.muted, fontFamily: fonts.body },
  savedBadge: { fontSize: 11, color: colors.greenText, fontWeight: "600", fontFamily: fonts.body },
  errorBadge: { fontSize: 11, color: colors.redText, fontFamily: fonts.body },
  stubText: { fontSize: 13, color: colors.muted, fontFamily: fonts.body, lineHeight: 19 },

  // Rules card
  rulesBody: { gap: 14 },
  toggleRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  fieldLabel: { fontSize: 12, fontWeight: "600", color: colors.text, fontFamily: fonts.body, marginBottom: 4 },
  fieldHint: { fontSize: 11, color: colors.muted, fontFamily: fonts.body, lineHeight: 16 },
  rulesFields: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  rulesFieldGroup: { minWidth: 120, flex: 1 },

  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 13,
    color: colors.text,
    fontFamily: fonts.body,
    backgroundColor: colors.bg,
    outlineWidth: 0,
  } as any,

  saveBtn: {
    backgroundColor: colors.purple,
    borderRadius: radii.md,
    paddingVertical: 10,
    alignItems: "center",
    marginTop: 4,
  },
  saveBtnDisabled: { backgroundColor: colors.border },
  saveBtnText: { color: "#FFFFFF", fontSize: 13, fontWeight: "600", fontFamily: fonts.body },
});

// Kid row styles
const kidStyles = StyleSheet.create({
  row: { paddingVertical: 4 },
  header: { flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 10 },
  avatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.purpleLight,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: { fontSize: 11, fontWeight: "600", color: colors.purpleDeep, fontFamily: fonts.body },
  name: { fontSize: 14, fontWeight: "600", color: colors.text, fontFamily: fonts.body, flex: 1 },
  checkBadge: { fontSize: 11, color: colors.greenText, fontWeight: "600", fontFamily: fonts.body },
  errBadge: { fontSize: 11, color: colors.redText, fontFamily: fonts.body },

  body: { gap: 6 },
  columnHeaders: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 2 },
  colHeader: {
    fontSize: 10,
    fontWeight: "600",
    color: colors.muted,
    fontFamily: fonts.body,
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  colPts: { width: 52, textAlign: "center" as const },
  colRemove: { width: 28 },

  routineRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    paddingHorizontal: 10,
    paddingVertical: 7,
    fontSize: 13,
    color: colors.text,
    fontFamily: fonts.body,
    backgroundColor: colors.bg,
    outlineWidth: 0,
  } as any,
  ptsInput: { width: 52, textAlign: "center" as const },

  removeBtn: {
    width: 28,
    height: 28,
    borderRadius: radii.md,
    backgroundColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  removeBtnText: { fontSize: 11, color: colors.muted, fontFamily: fonts.body },

  emptyText: { fontSize: 13, color: colors.muted, fontFamily: fonts.body, paddingVertical: 4 },

  actionRow: { flexDirection: "row", gap: 8, marginTop: 6 },
  addBtn: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.purple,
    borderRadius: radii.md,
    paddingVertical: 8,
    alignItems: "center",
  },
  addBtnText: { color: colors.purple, fontSize: 13, fontWeight: "600", fontFamily: fonts.body },

  saveBtn: {
    flex: 1,
    backgroundColor: colors.purple,
    borderRadius: radii.md,
    paddingVertical: 8,
    alignItems: "center",
  },
  saveBtnDisabled: { backgroundColor: colors.border },
  saveBtnText: { color: "#FFFFFF", fontSize: 13, fontWeight: "600", fontFamily: fonts.body },
});
