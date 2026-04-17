/**
 * /admin/rewards — Rewards admin screen
 *
 * Section 1: Reward tiers  — editable list (id/slug, label, cost_pts, example).
 *            Add / remove / edit. Saved via useFamilyConfig.
 * Section 2: Redemption rules — require_approval toggle, max_redemptions_per_week
 *            number field, allow_negative_balance toggle.
 * Section 3: Redemption history (stub).
 *
 * Permission: rewards.manage_config (seeded in migration 033).
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
import { useFamilyConfig } from "../../../lib/config";

// ---------------------------------------------------------------------------
// Shapes
// ---------------------------------------------------------------------------

export interface RewardTier {
  id: string;
  label: string;
  cost_pts: number;
  example: string;
}

export interface RewardsTiersConfig {
  tiers: RewardTier[];
}

export interface RewardsRedemptionRules {
  require_approval: boolean;
  max_redemptions_per_week: number;
  allow_negative_balance: boolean;
}

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

const DEFAULT_TIERS: RewardsTiersConfig = {
  tiers: [
    { id: "small",  label: "Small reward",  cost_pts: 200,  example: "30 min extra screen time" },
    { id: "medium", label: "Medium reward", cost_pts: 500,  example: "Movie night pick" },
    { id: "large",  label: "Large reward",  cost_pts: 1000, example: "Day trip pick" },
  ],
};

const DEFAULT_RULES: RewardsRedemptionRules = {
  require_approval: true,
  max_redemptions_per_week: 2,
  allow_negative_balance: false,
};

// ---------------------------------------------------------------------------
// TierRow editor — one editable row in the tiers list
// ---------------------------------------------------------------------------

interface TierRowProps {
  tier: RewardTier;
  onChange: (updated: RewardTier) => void;
  onRemove: () => void;
}

function TierRow({ tier, onChange, onRemove }: TierRowProps) {
  return (
    <View style={rowStyles.container}>
      <View style={rowStyles.row}>
        <TextInput
          style={[rowStyles.input, rowStyles.inputSlug] as any}
          value={tier.id}
          onChangeText={(t) => onChange({ ...tier, id: t.toLowerCase().replace(/\s+/g, "_") })}
          placeholder="id (slug)"
          placeholderTextColor={colors.muted}
          autoCapitalize="none"
        />
        <TextInput
          style={[rowStyles.input, rowStyles.inputLabel] as any}
          value={tier.label}
          onChangeText={(t) => onChange({ ...tier, label: t })}
          placeholder="Label"
          placeholderTextColor={colors.muted}
        />
        <TextInput
          style={[rowStyles.input, rowStyles.inputPts] as any}
          value={String(tier.cost_pts)}
          onChangeText={(t) => onChange({ ...tier, cost_pts: parseInt(t || "0", 10) })}
          placeholder="pts"
          placeholderTextColor={colors.muted}
          keyboardType="number-pad"
        />
        <Pressable
          style={rowStyles.removeBtn}
          onPress={onRemove}
          accessibilityRole="button"
          accessibilityLabel={`Remove ${tier.label} tier`}
        >
          <Text style={rowStyles.removeBtnText}>×</Text>
        </Pressable>
      </View>
      <TextInput
        style={[rowStyles.input, rowStyles.inputExample] as any}
        value={tier.example}
        onChangeText={(t) => onChange({ ...tier, example: t })}
        placeholder="Example (e.g. 30 min extra screen time)"
        placeholderTextColor={colors.muted}
      />
    </View>
  );
}

// ---------------------------------------------------------------------------
// Main screen
// ---------------------------------------------------------------------------

export default function RewardsAdmin() {
  const canManage = useHasPermission("rewards.manage_config");

  // ---- Reward tiers ----
  const {
    value: tiersConfig,
    setValue: setTiersConfig,
    loading: tiersLoading,
  } = useFamilyConfig<RewardsTiersConfig>("rewards.tiers", DEFAULT_TIERS);

  const [tiers, setTiers] = useState<RewardTier[]>([]);
  const [tiersSaving, setTiersSaving] = useState(false);
  const [tiersSaved, setTiersSaved] = useState(false);
  const [tiersError, setTiersError] = useState<string | null>(null);

  useEffect(() => {
    if (!tiersLoading) {
      setTiers(
        Array.isArray(tiersConfig?.tiers) ? [...tiersConfig.tiers] : [],
      );
    }
  }, [tiersLoading, tiersConfig]);

  const handleTierChange = useCallback((index: number, updated: RewardTier) => {
    setTiers((prev) => {
      const next = [...prev];
      next[index] = updated;
      return next;
    });
  }, []);

  const handleTierRemove = useCallback((index: number) => {
    setTiers((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleAddTier = useCallback(() => {
    setTiers((prev) => [
      ...prev,
      { id: "", label: "", cost_pts: 100, example: "" },
    ]);
  }, []);

  const handleSaveTiers = useCallback(async () => {
    setTiersSaving(true);
    setTiersError(null);
    try {
      await setTiersConfig({
        tiers: tiers.filter((t) => t.id.trim() !== "" && t.label.trim() !== ""),
      });
      setTiersSaved(true);
      setTimeout(() => setTiersSaved(false), 2000);
    } catch {
      setTiersError("Save failed");
    } finally {
      setTiersSaving(false);
    }
  }, [setTiersConfig, tiers]);

  // ---- Redemption rules ----
  const {
    value: rulesConfig,
    setValue: setRulesConfig,
    loading: rulesLoading,
  } = useFamilyConfig<RewardsRedemptionRules>(
    "rewards.redemption_rules",
    DEFAULT_RULES,
  );

  const [requireApproval, setRequireApproval] = useState(true);
  const [maxRedemptions, setMaxRedemptions] = useState("2");
  const [allowNegative, setAllowNegative] = useState(false);
  const [rulesSaving, setRulesSaving] = useState(false);
  const [rulesSaved, setRulesSaved] = useState(false);
  const [rulesError, setRulesError] = useState<string | null>(null);

  useEffect(() => {
    if (!rulesLoading) {
      setRequireApproval(rulesConfig.require_approval);
      setMaxRedemptions(String(rulesConfig.max_redemptions_per_week));
      setAllowNegative(rulesConfig.allow_negative_balance);
    }
  }, [rulesLoading, rulesConfig]);

  const handleSaveRules = useCallback(async () => {
    setRulesSaving(true);
    setRulesError(null);
    try {
      await setRulesConfig({
        require_approval: requireApproval,
        max_redemptions_per_week: parseInt(maxRedemptions || "2", 10),
        allow_negative_balance: allowNegative,
      });
      setRulesSaved(true);
      setTimeout(() => setRulesSaved(false), 2000);
    } catch {
      setRulesError("Save failed");
    } finally {
      setRulesSaving(false);
    }
  }, [setRulesConfig, requireApproval, maxRedemptions, allowNegative]);

  // ---- Permission guard ----
  if (!canManage) {
    return <Redirect href="/admin" />;
  }

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Rewards</Text>
      <Text style={styles.subtitle}>
        Configure reward tiers, redemption rules, and approval workflows for your family.
      </Text>

      {/* ------------------------------------------------------------------ */}
      {/* Section 1: Reward tiers                                             */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Reward tiers</Text>
          {tiersSaved && <Text style={styles.savedBadge}>Saved</Text>}
          {tiersError && <Text style={styles.errorBadge}>{tiersError}</Text>}
        </View>
        <Text style={styles.fieldHint}>
          Define point cost brackets that kids can redeem. Each tier needs a
          unique slug (id), a display label, a point cost, and an example reward.
        </Text>

        {tiersLoading ? (
          <ActivityIndicator size="small" color={colors.purple} />
        ) : (
          <View style={styles.sectionBody}>
            <View style={styles.tierHeader}>
              <Text style={[styles.colHead, styles.colSlug]}>ID</Text>
              <Text style={[styles.colHead, styles.colLabel]}>Label</Text>
              <Text style={[styles.colHead, styles.colPts]}>Pts</Text>
              <View style={{ width: 28 }} />
            </View>

            {tiers.map((tier, idx) => (
              <TierRow
                key={idx}
                tier={tier}
                onChange={(updated) => handleTierChange(idx, updated)}
                onRemove={() => handleTierRemove(idx)}
              />
            ))}

            <Pressable
              style={styles.addBtn}
              onPress={handleAddTier}
              accessibilityRole="button"
              accessibilityLabel="Add reward tier"
            >
              <Text style={styles.addBtnText}>+ Add tier</Text>
            </Pressable>

            <Pressable
              style={[styles.saveBtn, tiersSaving && styles.saveBtnDisabled]}
              onPress={handleSaveTiers}
              disabled={tiersSaving}
              accessibilityRole="button"
              accessibilityLabel="Save reward tiers"
            >
              <Text style={styles.saveBtnText}>
                {tiersSaving ? "Saving…" : "Save Tiers"}
              </Text>
            </Pressable>
          </View>
        )}
      </View>

      {/* ------------------------------------------------------------------ */}
      {/* Section 2: Redemption rules                                         */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Redemption rules</Text>
          {rulesSaved && <Text style={styles.savedBadge}>Saved</Text>}
          {rulesError && <Text style={styles.errorBadge}>{rulesError}</Text>}
        </View>

        {rulesLoading ? (
          <ActivityIndicator size="small" color={colors.purple} />
        ) : (
          <View style={styles.sectionBody}>
            <View style={styles.toggleRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.fieldLabel}>Require parent approval</Text>
                <Text style={styles.fieldHint}>
                  Redemptions must be approved by a parent before points are
                  deducted and the reward is granted.
                </Text>
              </View>
              <Switch
                value={requireApproval}
                onValueChange={setRequireApproval}
                trackColor={{ true: colors.purple, false: colors.border }}
                thumbColor={colors.card}
              />
            </View>

            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Max redemptions per week</Text>
              <TextInput
                style={[styles.input, styles.inputNarrow] as any}
                value={maxRedemptions}
                onChangeText={setMaxRedemptions}
                keyboardType="number-pad"
                placeholder="2"
                placeholderTextColor={colors.muted}
              />
            </View>

            <View style={styles.toggleRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.fieldLabel}>Allow negative balance</Text>
                <Text style={styles.fieldHint}>
                  If enabled, kids can redeem rewards even if they don't have
                  enough points, going into a point deficit.
                </Text>
              </View>
              <Switch
                value={allowNegative}
                onValueChange={setAllowNegative}
                trackColor={{ true: colors.purple, false: colors.border }}
                thumbColor={colors.card}
              />
            </View>

            <Pressable
              style={[styles.saveBtn, rulesSaving && styles.saveBtnDisabled]}
              onPress={handleSaveRules}
              disabled={rulesSaving}
              accessibilityRole="button"
              accessibilityLabel="Save redemption rules"
            >
              <Text style={styles.saveBtnText}>
                {rulesSaving ? "Saving…" : "Save Rules"}
              </Text>
            </Pressable>
          </View>
        )}
      </View>

      {/* ------------------------------------------------------------------ */}
      {/* Section 3: Redemption history (stub)                                */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Redemption history</Text>
        </View>
        <Text style={styles.stubText}>
          Coming soon — who redeemed what, when, parent approval stats.
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
  subtitle: {
    fontSize: 13,
    color: colors.muted,
    fontFamily: fonts.body,
    lineHeight: 19,
    marginTop: -4,
  },
  savedBadge: {
    fontSize: 11,
    color: colors.greenText,
    fontWeight: "600",
    fontFamily: fonts.body,
  },
  errorBadge: { fontSize: 11, color: colors.redText, fontFamily: fonts.body },
  stubText: { fontSize: 13, color: colors.muted, fontFamily: fonts.body, lineHeight: 19 },

  sectionBody: { gap: 14 },
  fieldGroup: { gap: 6 },
  fieldLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.text,
    fontFamily: fonts.body,
  },
  fieldHint: {
    fontSize: 11,
    color: colors.muted,
    fontFamily: fonts.body,
    lineHeight: 16,
    marginBottom: 4,
  },
  toggleRow: { flexDirection: "row", alignItems: "center", gap: 12 },

  tierHeader: {
    flexDirection: "row",
    gap: 8,
    paddingBottom: 4,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  colHead: { fontSize: 10, fontWeight: "700", color: colors.muted, fontFamily: fonts.body, textTransform: "uppercase" },
  colSlug:  { width: 80 },
  colLabel: { flex: 1 },
  colPts:   { width: 52 },

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
  inputNarrow: { width: 80 },

  addBtn: {
    alignSelf: "flex-start",
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.purple,
    backgroundColor: colors.purpleLight,
  },
  addBtnText: {
    fontSize: 12,
    color: colors.purpleDeep,
    fontWeight: "600",
    fontFamily: fonts.body,
  },

  saveBtn: {
    backgroundColor: colors.purple,
    borderRadius: radii.md,
    paddingVertical: 10,
    alignItems: "center",
    marginTop: 4,
  },
  saveBtnDisabled: { backgroundColor: colors.border },
  saveBtnText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "600",
    fontFamily: fonts.body,
  },
});

// TierRow sub-styles
const rowStyles = StyleSheet.create({
  container: {
    gap: 6,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  row: { flexDirection: "row", alignItems: "center", gap: 8 },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    paddingHorizontal: 8,
    paddingVertical: 7,
    fontSize: 12,
    color: colors.text,
    fontFamily: fonts.body,
    backgroundColor: colors.bg,
    outlineWidth: 0,
  } as any,
  inputSlug:    { width: 80 },
  inputLabel:   { flex: 1 },
  inputPts:     { width: 52 },
  inputExample: { flex: 1 },
  removeBtn: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.redBg,
    alignItems: "center",
    justifyContent: "center",
  },
  removeBtnText: {
    fontSize: 16,
    color: colors.redText,
    fontWeight: "600",
    lineHeight: 20,
  },
});
