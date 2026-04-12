import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { useCurrentWeeklyPlan, formatWeekStart } from "../../lib/meal_plan_hooks";
import { shared, colors } from "../../lib/styles";

export default function PrepPlanPage() {
  const { plan, loading, notFound, error, reload } = useCurrentWeeklyPlan();

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

  if (notFound || !plan) {
    return (
      <ScrollView style={shared.pageContainer} contentContainerStyle={shared.pageContent}>
        <View style={shared.headerBlock}>
          <Text style={shared.headerEyebrow}>Meals</Text>
          <Text style={shared.headerTitle}>Prep Plan</Text>
        </View>
        <View style={shared.card}>
          <Text style={shared.emptyText}>
            No plan yet. Generate one on This Week first.
          </Text>
        </View>
      </ScrollView>
    );
  }

  const tasks = plan.prep_plan?.tasks ?? [];
  const timeline = plan.prep_plan?.timeline ?? [];

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={shared.pageContent}>
      <View style={shared.headerBlock}>
        <Text style={shared.headerEyebrow}>Meals</Text>
        <Text style={shared.headerTitle}>Sunday Prep</Text>
        <Text style={shared.headerSubtitle}>
          Week of {formatWeekStart(plan.week_start_date)}
        </Text>
      </View>

      <Text style={shared.sectionTitle}>Tasks</Text>
      {tasks.length === 0 && (
        <View style={shared.card}>
          <Text style={shared.emptyText}>No prep tasks for this plan.</Text>
        </View>
      )}
      {tasks.map((task, i) => (
        <View key={i} style={shared.card}>
          <View style={shared.cardRow}>
            <Text style={shared.cardTitle}>{task.title}</Text>
            {task.duration_min != null && (
              <Text style={s.durationText}>{task.duration_min} min</Text>
            )}
          </View>
          {task.supports && task.supports.length > 0 && (
            <Text style={s.supportsText}>
              Supports: {task.supports.join(", ")}
            </Text>
          )}
        </View>
      ))}

      {timeline.length > 0 && (
        <>
          <Text style={shared.sectionTitle}>Timeline</Text>
          {timeline.map((block, i) => (
            <View key={i} style={shared.card}>
              <Text style={s.blockLabel}>{block.block}</Text>
              {block.items.map((it, j) => (
                <Text key={j} style={s.bulletText}>
                  · {it}
                </Text>
              ))}
            </View>
          ))}
        </>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  durationText: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: "600",
  },
  supportsText: {
    color: colors.textMuted,
    fontSize: 12,
    marginTop: 6,
  },
  blockLabel: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 1,
    marginBottom: 6,
  },
  bulletText: {
    color: colors.textSecondary,
    fontSize: 14,
    lineHeight: 22,
  },
});
