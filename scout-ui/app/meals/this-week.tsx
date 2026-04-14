import { useState } from "react";
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
  approveWeeklyPlan,
  archiveWeeklyPlan,
  generateWeeklyMealPlan,
  regenerateWeeklyPlanDay,
} from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useCurrentWeeklyPlan, WEEKDAYS, formatWeekStart } from "../../lib/meal_plan_hooks";
import { shared, colors } from "../../lib/styles";
import type { WeeklyMealPlanGenerateResponse } from "../../lib/types";

function nextMondayISO(): string {
  const d = new Date();
  const day = d.getDay();
  const daysUntilMonday = day === 1 ? 0 : (8 - day) % 7;
  d.setDate(d.getDate() + daysUntilMonday);
  return d.toISOString().split("T")[0];
}

export default function ThisWeekPage() {
  const { plan, loading, notFound, error, reload } = useCurrentWeeklyPlan();
  const { member } = useAuth();
  const [generating, setGenerating] = useState(false);
  const [questions, setQuestions] = useState<{ key: string; question: string; hint?: string | null }[] | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isAdult = member?.role === "adult";
  const status = plan?.status;

  const runGenerate = async (answersPayload?: Record<string, string>) => {
    setGenerating(true);
    setMsg(null);
    try {
      const res: WeeklyMealPlanGenerateResponse = await generateWeeklyMealPlan(
        nextMondayISO(),
        answersPayload ? { answers: answersPayload } : undefined,
      );
      if (res.status === "needs_clarification" && res.questions && res.questions.length > 0) {
        setQuestions(res.questions);
        setAnswers({});
        setMsg("Scout needs a few details before planning.");
      } else if (res.status === "ready") {
        setQuestions(null);
        setAnswers({});
        setMsg("Draft plan saved. Review and approve below.");
        reload();
      }
    } catch (e: any) {
      setMsg(e.message ?? "Failed to generate plan");
    } finally {
      setGenerating(false);
    }
  };

  const handleApprove = async () => {
    if (!plan) return;
    setBusy(true);
    setMsg(null);
    try {
      await approveWeeklyPlan(plan.id);
      setMsg("Plan approved. Groceries synced.");
      reload();
    } catch (e: any) {
      setMsg(e.message ?? "Failed to approve plan");
    } finally {
      setBusy(false);
    }
  };

  const handleArchive = async () => {
    if (!plan) return;
    setBusy(true);
    setMsg(null);
    try {
      await archiveWeeklyPlan(plan.id);
      setMsg("Plan archived.");
      reload();
    } catch (e: any) {
      setMsg(e.message ?? "Failed to archive plan");
    } finally {
      setBusy(false);
    }
  };

  const handleRegenerateDay = async (day: string) => {
    if (!plan) return;
    setBusy(true);
    setMsg(null);
    try {
      await regenerateWeeklyPlanDay(plan.id, day);
      setMsg(`Regenerated ${day}.`);
      reload();
    } catch (e: any) {
      setMsg(e.message ?? "Failed to regenerate");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <View style={shared.pageCenter}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={shared.pageCenter}>
        <Text style={shared.errorLarge}>{error}</Text>
        <Pressable style={[shared.button, { marginTop: 16 }]} onPress={reload}>
          <Text style={shared.buttonText}>Retry</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={shared.pageContent}>
      <View style={shared.headerBlock}>
        <Text style={shared.headerEyebrow}>Meals</Text>
        <Text style={shared.headerTitle}>This Week</Text>
        {plan && (
          <Text style={shared.headerSubtitle}>
            Week of {formatWeekStart(plan.week_start_date)} · {status}
          </Text>
        )}
      </View>

      {msg && (
        <View style={shared.msgBox}>
          <Text style={shared.msgText}>{msg}</Text>
        </View>
      )}

      {/* Clarifying questions from AI */}
      {questions && isAdult && (
        <View style={s.questionsCard}>
          <Text style={s.questionsTitle}>Scout needs a bit more info</Text>
          {questions.map((q) => (
            <View key={q.key} style={{ marginBottom: 12 }}>
              <Text style={s.questionText}>{q.question}</Text>
              {q.hint && <Text style={s.questionHint}>{q.hint}</Text>}
              <TextInput
                style={s.input}
                value={answers[q.key] || ""}
                onChangeText={(v) => setAnswers((prev) => ({ ...prev, [q.key]: v }))}
                placeholder="Your answer"
                placeholderTextColor={colors.textPlaceholder}
              />
            </View>
          ))}
          <Pressable
            style={shared.button}
            onPress={() => runGenerate(answers)}
            disabled={generating}
          >
            <Text style={shared.buttonText}>{generating ? "Planning..." : "Continue"}</Text>
          </Pressable>
        </View>
      )}

      {/* No plan yet */}
      {notFound && !questions && (
        <View style={shared.card}>
          <Text style={shared.cardTitle}>No weekly plan yet</Text>
          <Text style={shared.cardSubtle}>
            Ask Scout to draft one. You can tweak or regenerate before approving.
          </Text>
          {isAdult && (
            <Pressable
              style={shared.button}
              onPress={() => runGenerate()}
              disabled={generating}
            >
              <Text style={shared.buttonText}>
                {generating ? "Planning..." : "Generate Weekly Plan"}
              </Text>
            </Pressable>
          )}
          {!isAdult && (
            <Text style={shared.emptyText}>An adult needs to generate the plan.</Text>
          )}
        </View>
      )}

      {/* Plan rendered from saved backend object */}
      {plan && (
        <>
          {plan.plan_summary && (
            <View style={shared.card}>
              <Text style={shared.cardTitle}>Summary</Text>
              <Text style={s.bodyText}>{plan.plan_summary}</Text>
            </View>
          )}

          <Text style={shared.sectionTitle}>Dinners</Text>
          {WEEKDAYS.map((day) => {
            const meal = plan.week_plan?.dinners?.[day];
            if (!meal) return null;
            return (
              <View key={day} style={shared.card}>
                <View style={shared.cardRow}>
                  <Text style={s.dayLabel}>{day}</Text>
                  {isAdult && status !== "archived" && (
                    <Pressable
                      style={shared.buttonSmall}
                      onPress={() => handleRegenerateDay(day)}
                      disabled={busy}
                    >
                      <Text style={shared.buttonSmallText}>Swap</Text>
                    </Pressable>
                  )}
                </View>
                <Text style={s.mealTitle}>{meal.title}</Text>
                {meal.description && <Text style={s.bodyText}>{meal.description}</Text>}
              </View>
            );
          })}

          {plan.week_plan?.breakfast?.plan && (
            <>
              <Text style={shared.sectionTitle}>Breakfast</Text>
              <View style={shared.card}>
                <Text style={s.bodyText}>{plan.week_plan.breakfast.plan}</Text>
              </View>
            </>
          )}

          {plan.week_plan?.lunch?.plan && (
            <>
              <Text style={shared.sectionTitle}>Lunch</Text>
              <View style={shared.card}>
                <Text style={s.bodyText}>{plan.week_plan.lunch.plan}</Text>
              </View>
            </>
          )}

          {plan.week_plan?.snacks && plan.week_plan.snacks.length > 0 && (
            <>
              <Text style={shared.sectionTitle}>Snacks</Text>
              <View style={shared.card}>
                {plan.week_plan.snacks.map((snack, i) => (
                  <Text key={i} style={s.bulletText}>
                    · {snack}
                  </Text>
                ))}
              </View>
            </>
          )}

          {isAdult && status === "draft" && (
            <>
              <Pressable
                style={shared.button}
                onPress={handleApprove}
                disabled={busy}
                accessibilityLabel="Approve Plan"
                accessibilityRole="button"
              >
                <Text style={shared.buttonText}>Approve Plan</Text>
              </Pressable>
              <Pressable
                style={[shared.button, s.archiveBtn]}
                onPress={handleArchive}
                disabled={busy}
                accessibilityLabel="Archive Draft"
                accessibilityRole="button"
              >
                <Text style={shared.buttonText}>Archive Draft</Text>
              </Pressable>
            </>
          )}

          {isAdult && status === "approved" && (
            <Pressable
              style={shared.button}
              onPress={() => runGenerate()}
              disabled={generating}
            >
              <Text style={shared.buttonText}>
                {generating ? "Planning..." : "Generate Next Draft"}
              </Text>
            </Pressable>
          )}
        </>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  dayLabel: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 1,
  },
  mealTitle: {
    color: colors.textPrimary,
    fontSize: 17,
    fontWeight: "600",
    marginTop: 6,
  },
  bodyText: {
    color: colors.textSecondary,
    fontSize: 14,
    lineHeight: 20,
    marginTop: 4,
  },
  bulletText: {
    color: colors.textSecondary,
    fontSize: 14,
    lineHeight: 22,
  },
  questionsCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    borderLeftWidth: 3,
    borderLeftColor: colors.accent,
    padding: 16,
    marginBottom: 12,
  },
  questionsTitle: {
    color: colors.textPrimary,
    fontSize: 15,
    fontWeight: "700",
    marginBottom: 12,
  },
  questionText: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: "600",
  },
  questionHint: {
    color: colors.textMuted,
    fontSize: 12,
    marginTop: 2,
  },
  input: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: colors.textPrimary,
    fontSize: 14,
    marginTop: 6,
  },
  archiveBtn: {
    backgroundColor: colors.surfaceMuted,
  },
});
