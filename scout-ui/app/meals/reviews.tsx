import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  createMealReview,
  fetchMealReviewSummary,
  fetchMealReviews,
} from "../../lib/api";
import { useCurrentWeeklyPlan, WEEKDAYS } from "../../lib/meal_plan_hooks";
import { shared, colors } from "../../lib/styles";
import type { MealReview, MealReviewSummary } from "../../lib/types";

const RATING_OPTIONS = [1, 2, 3, 4, 5];
const LEFTOVER_OPTIONS: { key: "none" | "some" | "plenty"; label: string }[] = [
  { key: "none", label: "None" },
  { key: "some", label: "Some" },
  { key: "plenty", label: "Plenty" },
];
const REPEAT_OPTIONS: { key: "repeat" | "tweak" | "retire"; label: string }[] = [
  { key: "repeat", label: "Repeat" },
  { key: "tweak", label: "Tweak" },
  { key: "retire", label: "Retire" },
];

export default function ReviewsPage() {
  const { plan } = useCurrentWeeklyPlan();
  const [reviews, setReviews] = useState<MealReview[]>([]);
  const [summary, setSummary] = useState<MealReviewSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  // Quick review form state
  const [mealTitle, setMealTitle] = useState("");
  const [mealRef, setMealRef] = useState<string | null>(null);
  const [rating, setRating] = useState<number>(4);
  const [kidAcceptance, setKidAcceptance] = useState<number | null>(null);
  const [effort, setEffort] = useState<number | null>(null);
  const [leftovers, setLeftovers] = useState<"none" | "some" | "plenty" | null>(null);
  const [repeatDecision, setRepeatDecision] = useState<"repeat" | "tweak" | "retire">("repeat");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [r, s] = await Promise.all([fetchMealReviews(30), fetchMealReviewSummary()]);
      setReviews(r);
      setSummary(s);
    } catch (e: any) {
      setError(e.message ?? "Failed to load reviews");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const reset = () => {
    setMealTitle("");
    setMealRef(null);
    setRating(4);
    setKidAcceptance(null);
    setEffort(null);
    setLeftovers(null);
    setRepeatDecision("repeat");
    setNotes("");
  };

  const submit = async () => {
    if (!mealTitle.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      await createMealReview({
        weekly_plan_id: plan?.id ?? null,
        linked_meal_ref: mealRef,
        meal_title: mealTitle.trim(),
        rating_overall: rating,
        kid_acceptance: kidAcceptance,
        effort: effort,
        leftovers: leftovers,
        repeat_decision: repeatDecision,
        notes: notes.trim() || null,
      });
      setMsg("Review saved.");
      reset();
      load();
    } catch (e: any) {
      setMsg(e.message ?? "Failed to save review");
    } finally {
      setBusy(false);
    }
  };

  const pickFromPlan = (day: string) => {
    const meal = plan?.week_plan?.dinners?.[day];
    if (meal) {
      setMealTitle(meal.title);
      setMealRef(`${day}:dinner`);
    }
  };

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={shared.pageContent}>
      <View style={shared.headerBlock}>
        <Text style={shared.headerEyebrow}>Meals</Text>
        <Text style={shared.headerTitle}>Reviews</Text>
      </View>

      {msg && (
        <View style={shared.msgBox}>
          <Text style={shared.msgText}>{msg}</Text>
        </View>
      )}

      {/* Summary context */}
      {summary && summary.total_reviews > 0 && (
        <View style={shared.card}>
          <Text style={shared.cardTitle}>What's working</Text>
          {summary.high_rated.length > 0 && (
            <Text style={s.summaryLine}>
              <Text style={s.summaryLabel}>Loved: </Text>
              {summary.high_rated.join(", ")}
            </Text>
          )}
          {summary.low_effort_favorites.length > 0 && (
            <Text style={s.summaryLine}>
              <Text style={s.summaryLabel}>Easy wins: </Text>
              {summary.low_effort_favorites.join(", ")}
            </Text>
          )}
          {summary.good_leftovers.length > 0 && (
            <Text style={s.summaryLine}>
              <Text style={s.summaryLabel}>Good leftovers: </Text>
              {summary.good_leftovers.join(", ")}
            </Text>
          )}
          {summary.retired.length > 0 && (
            <Text style={s.summaryLine}>
              <Text style={s.summaryLabel}>Retired: </Text>
              {summary.retired.join(", ")}
            </Text>
          )}
          {summary.low_kid_acceptance.length > 0 && (
            <Text style={s.summaryLine}>
              <Text style={s.summaryLabel}>Kid-rejected: </Text>
              {summary.low_kid_acceptance.join(", ")}
            </Text>
          )}
        </View>
      )}

      {/* Fast review form */}
      <Text style={shared.sectionTitle}>Add a Review</Text>
      <View style={shared.card}>
        {plan && (
          <View style={s.dayPicker}>
            {WEEKDAYS.map((day) => {
              const meal = plan.week_plan?.dinners?.[day];
              if (!meal) return null;
              const active = mealRef === `${day}:dinner`;
              return (
                <Pressable
                  key={day}
                  style={[s.dayChip, active && s.dayChipActive]}
                  onPress={() => pickFromPlan(day)}
                >
                  <Text style={[s.dayChipText, active && s.dayChipTextActive]}>
                    {day.slice(0, 3)}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        )}

        <TextInput
          style={s.input}
          value={mealTitle}
          onChangeText={setMealTitle}
          placeholder="Meal title"
          placeholderTextColor={colors.textPlaceholder}
        />

        <Text style={s.fieldLabel}>Overall</Text>
        <View style={s.ratingRow}>
          {RATING_OPTIONS.map((r) => (
            <Pressable
              key={r}
              style={[s.ratingDot, rating === r && s.ratingDotActive]}
              onPress={() => setRating(r)}
            >
              <Text style={[s.ratingText, rating === r && s.ratingTextActive]}>
                {r}
              </Text>
            </Pressable>
          ))}
        </View>

        <Text style={s.fieldLabel}>Kid acceptance (optional)</Text>
        <View style={s.ratingRow}>
          {RATING_OPTIONS.map((r) => (
            <Pressable
              key={r}
              style={[s.ratingDot, kidAcceptance === r && s.ratingDotActive]}
              onPress={() => setKidAcceptance(kidAcceptance === r ? null : r)}
            >
              <Text style={[s.ratingText, kidAcceptance === r && s.ratingTextActive]}>
                {r}
              </Text>
            </Pressable>
          ))}
        </View>

        <Text style={s.fieldLabel}>Effort (optional)</Text>
        <View style={s.ratingRow}>
          {RATING_OPTIONS.map((r) => (
            <Pressable
              key={r}
              style={[s.ratingDot, effort === r && s.ratingDotActive]}
              onPress={() => setEffort(effort === r ? null : r)}
            >
              <Text style={[s.ratingText, effort === r && s.ratingTextActive]}>
                {r}
              </Text>
            </Pressable>
          ))}
        </View>

        <Text style={s.fieldLabel}>Leftovers</Text>
        <View style={s.chipRow}>
          {LEFTOVER_OPTIONS.map((opt) => (
            <Pressable
              key={opt.key}
              style={[s.chip, leftovers === opt.key && s.chipActive]}
              onPress={() => setLeftovers(leftovers === opt.key ? null : opt.key)}
            >
              <Text style={[s.chipText, leftovers === opt.key && s.chipTextActive]}>
                {opt.label}
              </Text>
            </Pressable>
          ))}
        </View>

        <Text style={s.fieldLabel}>Decision</Text>
        <View style={s.chipRow}>
          {REPEAT_OPTIONS.map((opt) => (
            <Pressable
              key={opt.key}
              style={[s.chip, repeatDecision === opt.key && s.chipActive]}
              onPress={() => setRepeatDecision(opt.key)}
            >
              <Text
                style={[s.chipText, repeatDecision === opt.key && s.chipTextActive]}
              >
                {opt.label}
              </Text>
            </Pressable>
          ))}
        </View>

        <TextInput
          style={[s.input, { marginTop: 12, minHeight: 60 }]}
          value={notes}
          onChangeText={setNotes}
          placeholder="Notes (optional)"
          placeholderTextColor={colors.textPlaceholder}
          multiline
        />

        <Pressable
          style={[shared.button, !mealTitle.trim() && shared.buttonDisabled]}
          onPress={submit}
          disabled={busy || !mealTitle.trim()}
        >
          <Text
            style={[shared.buttonText, !mealTitle.trim() && shared.buttonTextDisabled]}
          >
            {busy ? "Saving..." : "Save Review"}
          </Text>
        </Pressable>
      </View>

      {/* Prior reviews */}
      <Text style={shared.sectionTitle}>Recent Reviews</Text>
      {loading && <ActivityIndicator size="small" color={colors.accent} />}
      {error && <Text style={shared.errorText}>{error}</Text>}
      {!loading && reviews.length === 0 && (
        <View style={shared.card}>
          <Text style={shared.emptyText}>No reviews yet.</Text>
        </View>
      )}
      {reviews.map((r) => (
        <View key={r.id} style={shared.card}>
          <View style={shared.cardRow}>
            <Text style={shared.cardTitle}>{r.meal_title}</Text>
            <Text style={s.reviewRating}>{r.rating_overall}/5</Text>
          </View>
          <Text style={shared.cardSubtle}>
            {r.repeat_decision === "repeat"
              ? "Repeat"
              : r.repeat_decision === "tweak"
              ? "Tweak"
              : "Retire"}
            {r.effort != null && ` · effort ${r.effort}/5`}
            {r.kid_acceptance != null && ` · kids ${r.kid_acceptance}/5`}
            {r.leftovers && ` · ${r.leftovers}`}
          </Text>
          {r.notes && <Text style={s.notes}>{r.notes}</Text>}
        </View>
      ))}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  summaryLine: {
    color: colors.textSecondary,
    fontSize: 13,
    lineHeight: 20,
    marginTop: 4,
  },
  summaryLabel: {
    color: colors.textPrimary,
    fontWeight: "700",
  },
  dayPicker: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginBottom: 10,
  },
  dayChip: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 6,
    backgroundColor: colors.surfaceMuted,
  },
  dayChipActive: { backgroundColor: colors.accent },
  dayChipText: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
  },
  dayChipTextActive: { color: colors.buttonPrimaryText },
  input: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: colors.textPrimary,
    fontSize: 14,
  },
  fieldLabel: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.8,
    marginTop: 14,
    marginBottom: 6,
  },
  ratingRow: { flexDirection: "row", gap: 8 },
  ratingDot: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: colors.card,
  },
  ratingDotActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  ratingText: { color: colors.textSecondary, fontSize: 13, fontWeight: "700" },
  ratingTextActive: { color: colors.buttonPrimaryText },
  chipRow: { flexDirection: "row", gap: 6, flexWrap: "wrap" },
  chip: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 8,
    backgroundColor: colors.surfaceMuted,
  },
  chipActive: { backgroundColor: colors.accent },
  chipText: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: "700",
  },
  chipTextActive: { color: colors.buttonPrimaryText },
  reviewRating: {
    color: colors.accent,
    fontSize: 14,
    fontWeight: "700",
  },
  notes: {
    color: colors.textSecondary,
    fontSize: 13,
    lineHeight: 18,
    marginTop: 6,
  },
});
