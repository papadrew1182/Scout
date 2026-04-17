/**
 * /admin/meals — Meals admin screen
 *
 * Section 1: Plan rules  (week_starts_on, dinners_per_week, batch_cook_day,
 *                          generation_style)
 * Section 2: Rating scale (max_rating, repeat_options, require_notes_for_retire)
 * Section 3: Dietary categories (editable string array)
 * Section 4: Analytics stub
 *
 * Permission: meals.manage_config (seeded in migration 027)
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
import type {
  MealsPlanRules,
  MealsRatingScale,
  MealsDietaryNotes,
} from "../../../lib/meals";
import {
  DEFAULT_PLAN_RULES,
  DEFAULT_RATING_SCALE,
  DEFAULT_DIETARY_NOTES,
} from "../../../lib/meals";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type WeekDay = "monday" | "sunday";
type GenerationStyle = "balanced" | "kid-friendly" | "quick" | "ambitious";

// ---------------------------------------------------------------------------
// Editable string array subcomponent
// ---------------------------------------------------------------------------

interface StringArrayEditorProps {
  label: string;
  items: string[];
  onChange: (items: string[]) => void;
}

function StringArrayEditor({ label, items, onChange }: StringArrayEditorProps) {
  const handleChange = (index: number, text: string) => {
    const next = [...items];
    next[index] = text;
    onChange(next);
  };

  const handleRemove = (index: number) => {
    onChange(items.filter((_, i) => i !== index));
  };

  const handleAdd = () => {
    onChange([...items, ""]);
  };

  return (
    <View style={arrStyles.container}>
      <Text style={arrStyles.label}>{label}</Text>
      {items.map((item, idx) => (
        <View key={idx} style={arrStyles.row}>
          <TextInput
            style={arrStyles.input as any}
            value={item}
            onChangeText={(text) => handleChange(idx, text)}
            placeholder="Category"
            placeholderTextColor={colors.muted}
          />
          <Pressable
            style={arrStyles.removeBtn}
            onPress={() => handleRemove(idx)}
            accessibilityRole="button"
            accessibilityLabel={`Remove ${item}`}
          >
            <Text style={arrStyles.removeBtnText}>×</Text>
          </Pressable>
        </View>
      ))}
      <Pressable
        style={arrStyles.addBtn}
        onPress={handleAdd}
        accessibilityRole="button"
        accessibilityLabel={`Add ${label.toLowerCase()}`}
      >
        <Text style={arrStyles.addBtnText}>+ Add</Text>
      </Pressable>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Selector chip row helper
// ---------------------------------------------------------------------------

interface ChipSelectorProps<T extends string> {
  options: readonly T[];
  value: T;
  onSelect: (v: T) => void;
  labelFor?: (v: T) => string;
}

function ChipSelector<T extends string>({
  options,
  value,
  onSelect,
  labelFor,
}: ChipSelectorProps<T>) {
  return (
    <View style={chipStyles.row}>
      {options.map((opt) => (
        <Pressable
          key={opt}
          style={[chipStyles.chip, value === opt && chipStyles.chipActive]}
          onPress={() => onSelect(opt)}
          accessibilityRole="radio"
          accessibilityState={{ selected: value === opt }}
        >
          <Text
            style={[
              chipStyles.chipText,
              value === opt && chipStyles.chipTextActive,
            ]}
          >
            {labelFor ? labelFor(opt) : opt.charAt(0).toUpperCase() + opt.slice(1)}
          </Text>
        </Pressable>
      ))}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Main screen
// ---------------------------------------------------------------------------

export default function MealsAdmin() {
  const canManage = useHasPermission("meals.manage_config");

  // ---- Plan rules ----
  const {
    value: planRules,
    setValue: setPlanRules,
    loading: planLoading,
  } = useFamilyConfig<MealsPlanRules>("meals.plan_rules", DEFAULT_PLAN_RULES);

  const [weekStartsOn, setWeekStartsOn] = useState<WeekDay>("monday");
  const [dinnersPerWeek, setDinnersPerWeek] = useState("");
  const [batchCookDay, setBatchCookDay] = useState("");
  const [generationStyle, setGenerationStyle] = useState<GenerationStyle>("balanced");
  const [planSaving, setPlanSaving] = useState(false);
  const [planSaved, setPlanSaved] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);

  useEffect(() => {
    if (!planLoading) {
      setWeekStartsOn(planRules.week_starts_on);
      setDinnersPerWeek(String(planRules.dinners_per_week));
      setBatchCookDay(planRules.batch_cook_day);
      setGenerationStyle(planRules.generation_style);
    }
  }, [planLoading, planRules]);

  const handleSavePlan = useCallback(async () => {
    setPlanSaving(true);
    setPlanError(null);
    try {
      await setPlanRules({
        week_starts_on: weekStartsOn,
        dinners_per_week: parseInt(dinnersPerWeek || "7", 10),
        batch_cook_day: batchCookDay,
        generation_style: generationStyle,
      });
      setPlanSaved(true);
      setTimeout(() => setPlanSaved(false), 2000);
    } catch {
      setPlanError("Save failed");
    } finally {
      setPlanSaving(false);
    }
  }, [setPlanRules, weekStartsOn, dinnersPerWeek, batchCookDay, generationStyle]);

  // ---- Rating scale ----
  const {
    value: ratingScale,
    setValue: setRatingScale,
    loading: ratingLoading,
  } = useFamilyConfig<MealsRatingScale>("meals.rating_scale", DEFAULT_RATING_SCALE);

  const [maxRating, setMaxRating] = useState("");
  const [repeatOptions, setRepeatOptions] = useState<string[]>([]);
  const [requireNotesForRetire, setRequireNotesForRetire] = useState(false);
  const [ratingSaving, setRatingSaving] = useState(false);
  const [ratingSaved, setRatingSaved] = useState(false);
  const [ratingError, setRatingError] = useState<string | null>(null);

  useEffect(() => {
    if (!ratingLoading) {
      setMaxRating(String(ratingScale.max_rating));
      setRepeatOptions([...ratingScale.repeat_options]);
      setRequireNotesForRetire(ratingScale.require_notes_for_retire);
    }
  }, [ratingLoading, ratingScale]);

  const handleSaveRating = useCallback(async () => {
    setRatingSaving(true);
    setRatingError(null);
    try {
      await setRatingScale({
        max_rating: parseInt(maxRating || "5", 10),
        repeat_options: repeatOptions.filter((s) => s.trim() !== ""),
        require_notes_for_retire: requireNotesForRetire,
      });
      setRatingSaved(true);
      setTimeout(() => setRatingSaved(false), 2000);
    } catch {
      setRatingError("Save failed");
    } finally {
      setRatingSaving(false);
    }
  }, [setRatingScale, maxRating, repeatOptions, requireNotesForRetire]);

  // ---- Dietary categories ----
  const {
    value: dietaryNotes,
    setValue: setDietaryNotes,
    loading: dietaryLoading,
  } = useFamilyConfig<MealsDietaryNotes>(
    "meals.dietary_notes",
    DEFAULT_DIETARY_NOTES,
  );

  const [categories, setCategories] = useState<string[]>([]);
  const [dietarySaving, setDietarySaving] = useState(false);
  const [dietarySaved, setDietarySaved] = useState(false);
  const [dietaryError, setDietaryError] = useState<string | null>(null);

  useEffect(() => {
    if (!dietaryLoading) {
      setCategories([...dietaryNotes.categories]);
    }
  }, [dietaryLoading, dietaryNotes]);

  const handleSaveDietary = useCallback(async () => {
    setDietarySaving(true);
    setDietaryError(null);
    try {
      await setDietaryNotes({
        categories: categories.filter((s) => s.trim() !== ""),
      });
      setDietarySaved(true);
      setTimeout(() => setDietarySaved(false), 2000);
    } catch {
      setDietaryError("Save failed");
    } finally {
      setDietarySaving(false);
    }
  }, [setDietaryNotes, categories]);

  // ---- Permission guard ----
  if (!canManage) {
    return <Redirect href="/admin" />;
  }

  const WEEK_START_OPTIONS = ["monday", "sunday"] as const;
  const BATCH_DAY_OPTIONS = [
    "sunday",
    "saturday",
    "friday",
    "monday",
  ] as const;
  const GEN_STYLE_OPTIONS = [
    "balanced",
    "kid-friendly",
    "quick",
    "ambitious",
  ] as const;

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Meals</Text>
      <Text style={styles.subtitle}>
        Configure meal planning rules, rating options, and dietary categories for your family.
      </Text>

      {/* ------------------------------------------------------------------ */}
      {/* Section 1: Plan rules                                               */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Plan rules</Text>
          {planSaved && <Text style={styles.savedBadge}>Saved</Text>}
          {planError && <Text style={styles.errorBadge}>{planError}</Text>}
        </View>

        {planLoading ? (
          <ActivityIndicator size="small" color={colors.purple} />
        ) : (
          <View style={styles.sectionBody}>
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Week starts on</Text>
              <ChipSelector
                options={WEEK_START_OPTIONS}
                value={weekStartsOn}
                onSelect={setWeekStartsOn}
              />
            </View>

            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Dinners per week</Text>
              <TextInput
                style={[styles.input, styles.inputNarrow] as any}
                value={dinnersPerWeek}
                onChangeText={setDinnersPerWeek}
                keyboardType="number-pad"
                placeholder="7"
                placeholderTextColor={colors.muted}
              />
            </View>

            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Batch cook day</Text>
              <ChipSelector
                options={BATCH_DAY_OPTIONS}
                value={batchCookDay as any}
                onSelect={(v) => setBatchCookDay(v)}
              />
            </View>

            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Generation style</Text>
              <ChipSelector
                options={GEN_STYLE_OPTIONS}
                value={generationStyle}
                onSelect={setGenerationStyle}
              />
            </View>

            <Pressable
              style={[styles.saveBtn, planSaving && styles.saveBtnDisabled]}
              onPress={handleSavePlan}
              disabled={planSaving}
              accessibilityRole="button"
              accessibilityLabel="Save plan rules"
            >
              <Text style={styles.saveBtnText}>
                {planSaving ? "Saving…" : "Save Plan Rules"}
              </Text>
            </Pressable>
          </View>
        )}
      </View>

      {/* ------------------------------------------------------------------ */}
      {/* Section 2: Rating scale                                             */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Rating scale</Text>
          {ratingSaved && <Text style={styles.savedBadge}>Saved</Text>}
          {ratingError && <Text style={styles.errorBadge}>{ratingError}</Text>}
        </View>

        {ratingLoading ? (
          <ActivityIndicator size="small" color={colors.purple} />
        ) : (
          <View style={styles.sectionBody}>
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Max rating (1–10)</Text>
              <TextInput
                style={[styles.input, styles.inputNarrow] as any}
                value={maxRating}
                onChangeText={setMaxRating}
                keyboardType="number-pad"
                placeholder="5"
                placeholderTextColor={colors.muted}
              />
            </View>

            <StringArrayEditor
              label="Repeat options"
              items={repeatOptions}
              onChange={setRepeatOptions}
            />

            <View style={styles.toggleRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.fieldLabel}>Require notes for "Retire"</Text>
                <Text style={styles.fieldHint}>
                  When retiring a meal, family members must add a note explaining why.
                </Text>
              </View>
              <Switch
                value={requireNotesForRetire}
                onValueChange={setRequireNotesForRetire}
                trackColor={{ true: colors.purple, false: colors.border }}
                thumbColor={colors.card}
              />
            </View>

            <Pressable
              style={[styles.saveBtn, ratingSaving && styles.saveBtnDisabled]}
              onPress={handleSaveRating}
              disabled={ratingSaving}
              accessibilityRole="button"
              accessibilityLabel="Save rating scale"
            >
              <Text style={styles.saveBtnText}>
                {ratingSaving ? "Saving…" : "Save Rating Scale"}
              </Text>
            </Pressable>
          </View>
        )}
      </View>

      {/* ------------------------------------------------------------------ */}
      {/* Section 3: Dietary categories                                       */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Dietary categories</Text>
          {dietarySaved && <Text style={styles.savedBadge}>Saved</Text>}
          {dietaryError && <Text style={styles.errorBadge}>{dietaryError}</Text>}
        </View>

        {dietaryLoading ? (
          <ActivityIndicator size="small" color={colors.purple} />
        ) : (
          <View style={styles.sectionBody}>
            <Text style={styles.fieldHint}>
              These labels appear in the dietary notes panel and are referenced by
              family members' per-member config. Changes here update the available
              options; individual member assignments are managed per-member.
            </Text>
            <StringArrayEditor
              label="Categories"
              items={categories}
              onChange={setCategories}
            />
            <Pressable
              style={[styles.saveBtn, dietarySaving && styles.saveBtnDisabled]}
              onPress={handleSaveDietary}
              disabled={dietarySaving}
              accessibilityRole="button"
              accessibilityLabel="Save dietary categories"
            >
              <Text style={styles.saveBtnText}>
                {dietarySaving ? "Saving…" : "Save Categories"}
              </Text>
            </Pressable>
          </View>
        )}
      </View>

      {/* ------------------------------------------------------------------ */}
      {/* Section 4: Analytics stub                                           */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Analytics</Text>
        </View>
        <Text style={styles.stubText}>
          Coming soon — most-repeated meals, kid acceptance trends, prep time vs rating.
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
  },
  toggleRow: { flexDirection: "row", alignItems: "center", gap: 12 },

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

// Chip selector styles
const chipStyles = StyleSheet.create({
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    borderRadius: radii.pill,
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.card,
  },
  chipActive: {
    backgroundColor: colors.purpleLight,
    borderColor: colors.purple,
  },
  chipText: { fontSize: 12, color: colors.muted, fontFamily: fonts.body },
  chipTextActive: { color: colors.purpleDeep, fontWeight: "600" },
});

// String array editor styles
const arrStyles = StyleSheet.create({
  container: { gap: 6 },
  label: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.text,
    fontFamily: fonts.body,
  },
  row: { flexDirection: "row", alignItems: "center", gap: 8 },
  input: {
    flex: 1,
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
});
