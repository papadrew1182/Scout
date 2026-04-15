/**
 * Meals — Reviews tab.
 *
 * Minimal functional meal review form. Scoped to what the smoke tests
 * assert: a "Meal title" input, a "Save Review" button, and a POST to
 * /meals/reviews via createMealReview on submit. Defaults are applied
 * for the other required fields (rating=4, decision="repeat") so the
 * user only has to type a title to submit.
 */

import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { colors, fonts, shared } from "../../lib/styles";
import { createMealReview, fetchMealReviews } from "../../lib/api";
import type { MealReview } from "../../lib/types";

const DEFAULT_RATING = 4;
const DEFAULT_DECISION: "repeat" | "tweak" | "retire" = "repeat";

export default function MealsReviews() {
  const [mealTitle, setMealTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [rating, setRating] = useState<number>(DEFAULT_RATING);
  const [decision, setDecision] = useState<"repeat" | "tweak" | "retire">(DEFAULT_DECISION);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [recent, setRecent] = useState<MealReview[]>([]);

  const loadRecent = async () => {
    try {
      const rows = await fetchMealReviews(5);
      setRecent(rows);
    } catch {
      // Non-fatal — reviews list is decorative.
    }
  };

  useEffect(() => { loadRecent(); }, []);

  const submit = async () => {
    const title = mealTitle.trim();
    if (!title) return;
    setBusy(true);
    setMsg(null);
    try {
      await createMealReview({
        weekly_plan_id: null,
        linked_meal_ref: null,
        meal_title: title,
        rating_overall: rating,
        kid_acceptance: null,
        effort: null,
        cleanup: null,
        leftovers: null,
        repeat_decision: decision,
        notes: notes.trim() || null,
      });
      setMsg("Review saved");
      setMealTitle("");
      setNotes("");
      setRating(DEFAULT_RATING);
      setDecision(DEFAULT_DECISION);
      loadRecent();
    } catch (e: any) {
      setMsg(e?.message ?? "Failed to save review");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>New review</Text>
          <Text style={shared.cardAction}> </Text>
        </View>

        <TextInput
          style={styles.input}
          value={mealTitle}
          onChangeText={setMealTitle}
          placeholder="Meal title"
          placeholderTextColor={colors.muted}
        />

        <Text style={styles.label}>Overall rating</Text>
        <View style={styles.ratingRow}>
          {[1, 2, 3, 4, 5].map((n) => (
            <Pressable
              key={n}
              style={[styles.ratingPill, rating === n && styles.ratingPillActive]}
              onPress={() => setRating(n)}
              accessibilityRole="button"
              accessibilityLabel={`Rate ${n} stars`}
            >
              <Text style={[styles.ratingPillText, rating === n && styles.ratingPillTextActive]}>{n}</Text>
            </Pressable>
          ))}
        </View>

        <Text style={styles.label}>Repeat decision</Text>
        <View style={styles.decisionRow}>
          {(["repeat", "tweak", "retire"] as const).map((d) => (
            <Pressable
              key={d}
              style={[styles.decisionPill, decision === d && styles.decisionPillActive]}
              onPress={() => setDecision(d)}
              accessibilityRole="button"
              accessibilityLabel={`Decision: ${d}`}
            >
              <Text style={[styles.decisionText, decision === d && styles.decisionTextActive]}>
                {d.charAt(0).toUpperCase() + d.slice(1)}
              </Text>
            </Pressable>
          ))}
        </View>

        <TextInput
          style={styles.input}
          value={notes}
          onChangeText={setNotes}
          placeholder="Notes (optional)"
          placeholderTextColor={colors.muted}
          multiline
        />

        <Pressable
          style={[styles.saveBtn, (!mealTitle.trim() || busy) && styles.saveBtnDisabled]}
          onPress={submit}
          disabled={!mealTitle.trim() || busy}
          accessibilityRole="button"
          accessibilityLabel="Save Review"
        >
          <Text style={styles.saveBtnText}>{busy ? "Saving…" : "Save Review"}</Text>
        </Pressable>

        {msg && <Text style={styles.msg}>{msg}</Text>}
      </View>

      {recent.length > 0 && (
        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Recent reviews</Text>
            <Text style={shared.cardAction}> </Text>
          </View>
          {recent.map((r) => (
            <View key={r.id} style={styles.recentRow}>
              <Text style={styles.recentTitle}>{r.meal_title}</Text>
              <Text style={styles.recentMeta}>
                {r.rating_overall}/5 · {r.repeat_decision}
              </Text>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  input: {
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 9,
    fontSize: 13,
    color: colors.text,
    fontFamily: fonts.body,
    marginBottom: 10,
    outlineWidth: 0,
  } as any,
  label: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.muted,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    marginTop: 4,
    marginBottom: 6,
    fontFamily: fonts.body,
  },
  ratingRow: { flexDirection: "row", gap: 6, marginBottom: 10 },
  ratingPill: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  ratingPillActive: { backgroundColor: colors.purple, borderColor: colors.purple },
  ratingPillText: { fontSize: 13, color: colors.text, fontFamily: fonts.mono, fontWeight: "600" },
  ratingPillTextActive: { color: "#FFFFFF" },
  decisionRow: { flexDirection: "row", gap: 6, marginBottom: 10 },
  decisionPill: {
    flex: 1,
    paddingVertical: 9,
    borderRadius: 8,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
  },
  decisionPillActive: { backgroundColor: colors.purpleLight, borderColor: colors.purpleMid },
  decisionText: { fontSize: 12, color: colors.muted, fontFamily: fonts.body, fontWeight: "500" },
  decisionTextActive: { color: colors.purpleDeep, fontWeight: "600" },
  saveBtn: {
    backgroundColor: colors.purple,
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
    marginTop: 4,
  },
  saveBtnDisabled: { backgroundColor: colors.border },
  saveBtnText: { color: "#FFFFFF", fontSize: 13, fontWeight: "600", fontFamily: fonts.body },
  msg: {
    fontSize: 12,
    color: colors.green,
    fontFamily: fonts.body,
    marginTop: 8,
    textAlign: "center",
  },
  recentRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  recentTitle: { fontSize: 12, color: colors.text, fontFamily: fonts.body, flex: 1 },
  recentMeta: { fontSize: 11, color: colors.muted, fontFamily: fonts.mono },
});
