/**
 * /admin/allowance — Allowance admin screen
 *
 * Section 1: Per-kid weekly targets (editable, per-kid Save)
 * Section 2: Family bonus rules (editable)
 * Section 3: Payout history stub
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
import type { AllowanceTarget } from "../../../lib/allowance";
import { DEFAULT_ALLOWANCE_TARGET } from "../../../lib/allowance";

// ---------------------------------------------------------------------------
// Family bonus rules shape
// ---------------------------------------------------------------------------

interface AllowanceRules {
  requires_approval_for_bonus: boolean;
  max_weekly_bonus_cents: number;
  streak_bonus_days: number;
  streak_bonus_cents: number;
}

const DEFAULT_RULES: AllowanceRules = {
  requires_approval_for_bonus: true,
  max_weekly_bonus_cents: 500,
  streak_bonus_days: 7,
  streak_bonus_cents: 200,
};

// ---------------------------------------------------------------------------
// Per-kid row component (keeps its own useMemberConfig instance)
// ---------------------------------------------------------------------------

interface KidRowProps {
  kid: FamilyMember;
}

function KidAllowanceRow({ kid }: KidRowProps) {
  const { value, setValue, loading } = useMemberConfig<AllowanceTarget>(
    kid.id,
    "allowance.target",
    DEFAULT_ALLOWANCE_TARGET,
  );

  // Local draft state — dollars as strings for text input
  const [weeklyDollars, setWeeklyDollars] = useState("");
  const [baselineDollars, setBaselineDollars] = useState("");
  const [schedule, setSchedule] = useState<"weekly" | "biweekly" | "monthly">("weekly");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Sync draft when config loads
  useEffect(() => {
    if (!loading) {
      setWeeklyDollars(String(value.weekly_target_cents / 100));
      setBaselineDollars(String(value.baseline_cents / 100));
      setSchedule(value.payout_schedule);
    }
  }, [loading, value.weekly_target_cents, value.baseline_cents, value.payout_schedule]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setSaveError(null);
    try {
      await setValue({
        weekly_target_cents: Math.round(parseFloat(weeklyDollars || "0") * 100),
        baseline_cents: Math.round(parseFloat(baselineDollars || "0") * 100),
        payout_schedule: schedule,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setSaveError("Save failed");
    } finally {
      setSaving(false);
    }
  }, [setValue, weeklyDollars, baselineDollars, schedule]);

  // Avatar tint helpers — reuse the same tint logic from the parent page
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
        <View style={kidStyles.fields}>
          <View style={kidStyles.fieldGroup}>
            <Text style={kidStyles.label}>Weekly target ($)</Text>
            <TextInput
              style={kidStyles.input as any}
              value={weeklyDollars}
              onChangeText={setWeeklyDollars}
              keyboardType="decimal-pad"
              placeholder="0.00"
              placeholderTextColor={colors.muted}
            />
          </View>

          <View style={kidStyles.fieldGroup}>
            <Text style={kidStyles.label}>Baseline ($)</Text>
            <TextInput
              style={kidStyles.input as any}
              value={baselineDollars}
              onChangeText={setBaselineDollars}
              keyboardType="decimal-pad"
              placeholder="0.00"
              placeholderTextColor={colors.muted}
            />
          </View>

          <View style={kidStyles.fieldGroup}>
            <Text style={kidStyles.label}>Schedule</Text>
            <View style={kidStyles.scheduleRow}>
              {(["weekly", "biweekly", "monthly"] as const).map((opt) => (
                <Pressable
                  key={opt}
                  style={[
                    kidStyles.scheduleChip,
                    schedule === opt && kidStyles.scheduleChipActive,
                  ]}
                  onPress={() => setSchedule(opt)}
                  accessibilityRole="radio"
                  accessibilityState={{ selected: schedule === opt }}
                >
                  <Text
                    style={[
                      kidStyles.scheduleChipText,
                      schedule === opt && kidStyles.scheduleChipTextActive,
                    ]}
                  >
                    {opt.charAt(0).toUpperCase() + opt.slice(1)}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>

          <Pressable
            style={[kidStyles.saveBtn, saving && kidStyles.saveBtnDisabled]}
            onPress={handleSave}
            disabled={saving}
            accessibilityRole="button"
            accessibilityLabel={`Save allowance for ${kid.first_name}`}
          >
            <Text style={kidStyles.saveBtnText}>
              {saving ? "Saving…" : "Save"}
            </Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Main screen
// ---------------------------------------------------------------------------

export default function AllowanceAdmin() {
  const canManage = useHasPermission("allowance.manage_config");

  const [kids, setKids] = useState<FamilyMember[]>([]);
  const [membersLoading, setMembersLoading] = useState(true);

  const {
    value: rules,
    setValue: setRules,
    loading: rulesLoading,
  } = useFamilyConfig<AllowanceRules>("allowance.rules", DEFAULT_RULES);

  // Local draft for the rules card
  const [requiresApproval, setRequiresApproval] = useState(true);
  const [maxBonusDollars, setMaxBonusDollars] = useState("");
  const [streakDays, setStreakDays] = useState("");
  const [streakBonusDollars, setStreakBonusDollars] = useState("");
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
      setRequiresApproval(rules.requires_approval_for_bonus);
      setMaxBonusDollars(String(rules.max_weekly_bonus_cents / 100));
      setStreakDays(String(rules.streak_bonus_days));
      setStreakBonusDollars(String(rules.streak_bonus_cents / 100));
    }
  }, [rulesLoading, rules]);

  const handleSaveRules = useCallback(async () => {
    setRulesSaving(true);
    setRulesError(null);
    try {
      await setRules({
        requires_approval_for_bonus: requiresApproval,
        max_weekly_bonus_cents: Math.round(parseFloat(maxBonusDollars || "0") * 100),
        streak_bonus_days: parseInt(streakDays || "0", 10),
        streak_bonus_cents: Math.round(parseFloat(streakBonusDollars || "0") * 100),
      });
      setRulesSaved(true);
      setTimeout(() => setRulesSaved(false), 2000);
    } catch {
      setRulesError("Save failed");
    } finally {
      setRulesSaving(false);
    }
  }, [setRules, requiresApproval, maxBonusDollars, streakDays, streakBonusDollars]);

  if (!canManage) {
    return <Redirect href="/admin" />;
  }

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Allowance</Text>
      <Text style={styles.subtitle}>
        Configure weekly targets, payout schedules, and bonus rules for your family.
      </Text>

      {/* ------------------------------------------------------------------ */}
      {/* Section 1: Per-kid targets                                          */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Per-kid weekly targets</Text>
        </View>
        {membersLoading ? (
          <ActivityIndicator size="small" color={colors.purple} />
        ) : kids.length === 0 ? (
          <Text style={styles.empty}>No active children found.</Text>
        ) : (
          kids.map((kid, idx) => (
            <View key={kid.id}>
              {idx > 0 && <View style={styles.divider} />}
              <KidAllowanceRow kid={kid} />
            </View>
          ))
        )}
      </View>

      {/* ------------------------------------------------------------------ */}
      {/* Section 2: Family bonus rules                                       */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Family bonus rules</Text>
          {rulesSaved && <Text style={styles.savedBadge}>Saved</Text>}
          {rulesError && <Text style={styles.errorBadge}>{rulesError}</Text>}
        </View>

        {rulesLoading ? (
          <ActivityIndicator size="small" color={colors.purple} />
        ) : (
          <View style={styles.rulesBody}>
            <View style={styles.toggleRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.fieldLabel}>Requires approval for bonus</Text>
                <Text style={styles.fieldHint}>
                  Bonus payouts need parent sign-off before being issued.
                </Text>
              </View>
              <Switch
                value={requiresApproval}
                onValueChange={setRequiresApproval}
                trackColor={{ true: colors.purple, false: colors.border }}
                thumbColor={colors.card}
              />
            </View>

            <View style={styles.rulesFields}>
              <View style={styles.rulesFieldGroup}>
                <Text style={styles.fieldLabel}>Max weekly bonus ($)</Text>
                <TextInput
                  style={styles.input as any}
                  value={maxBonusDollars}
                  onChangeText={setMaxBonusDollars}
                  keyboardType="decimal-pad"
                  placeholder="0.00"
                  placeholderTextColor={colors.muted}
                />
              </View>

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
                <Text style={styles.fieldLabel}>Streak bonus amount ($)</Text>
                <TextInput
                  style={styles.input as any}
                  value={streakBonusDollars}
                  onChangeText={setStreakBonusDollars}
                  keyboardType="decimal-pad"
                  placeholder="0.00"
                  placeholderTextColor={colors.muted}
                />
              </View>
            </View>

            <Pressable
              style={[styles.saveBtn, rulesSaving && styles.saveBtnDisabled]}
              onPress={handleSaveRules}
              disabled={rulesSaving}
              accessibilityRole="button"
              accessibilityLabel="Save family bonus rules"
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
          <Text style={shared.cardTitle}>Payout history</Text>
        </View>
        <Text style={styles.stubText}>
          Coming soon — weekly payout ledger and per-kid allowance earning trends.
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
  rulesFieldGroup: { minWidth: 140, flex: 1 },

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

  fields: { gap: 10 },
  fieldGroup: {},
  label: { fontSize: 11, fontWeight: "600", color: colors.muted, fontFamily: fonts.body, marginBottom: 4, textTransform: "uppercase", letterSpacing: 0.4 },
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

  scheduleRow: { flexDirection: "row", gap: 8 },
  scheduleChip: {
    borderRadius: radii.pill,
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.card,
  },
  scheduleChipActive: {
    backgroundColor: colors.purpleLight,
    borderColor: colors.purple,
  },
  scheduleChipText: { fontSize: 12, color: colors.muted, fontFamily: fonts.body },
  scheduleChipTextActive: { color: colors.purpleDeep, fontWeight: "600" },

  saveBtn: {
    backgroundColor: colors.purple,
    borderRadius: radii.md,
    paddingVertical: 9,
    alignItems: "center",
    marginTop: 4,
  },
  saveBtnDisabled: { backgroundColor: colors.border },
  saveBtnText: { color: "#FFFFFF", fontSize: 13, fontWeight: "600", fontFamily: fonts.body },
});
