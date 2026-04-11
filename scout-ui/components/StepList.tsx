import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { fetchStepCompletions, updateStepCompletion } from "../lib/api";
import { colors } from "../lib/styles";
import type { StepCompletion } from "../lib/types";
import { API_BASE_URL, FAMILY_ID } from "../lib/config";

interface RoutineStep {
  id: string;
  name: string;
  sort_order: number;
}

interface Props {
  taskInstanceId: string;
  routineId: string;
  onStepChange?: () => void;
}

export function StepList({ taskInstanceId, routineId, onStepChange }: Props) {
  const [steps, setSteps] = useState<StepCompletion[]>([]);
  const [stepNames, setStepNames] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  const loadSteps = () => {
    let cancelled = false;

    Promise.all([
      fetchStepCompletions(taskInstanceId),
      fetch(`${API_BASE_URL}/families/${FAMILY_ID}/routines/${routineId}/steps`)
        .then((r) => r.json()) as Promise<RoutineStep[]>,
    ])
      .then(([completions, routineSteps]) => {
        if (cancelled) return;
        const nameMap: Record<string, string> = {};
        for (const rs of routineSteps) nameMap[rs.id] = rs.name;
        setStepNames(nameMap);
        setSteps(completions);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  };

  useEffect(loadSteps, [taskInstanceId, routineId]);

  const handleToggle = async (step: StepCompletion) => {
    const newValue = !step.is_completed;
    setSteps((prev) =>
      prev.map((s) =>
        s.id === step.id ? { ...s, is_completed: newValue } : s
      )
    );
    try {
      await updateStepCompletion(taskInstanceId, step.id, newValue);
      onStepChange?.();
    } catch {
      setSteps((prev) =>
        prev.map((s) =>
          s.id === step.id ? { ...s, is_completed: !newValue } : s
        )
      );
    }
  };

  if (loading) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="small" color={colors.accent} />
      </View>
    );
  }

  if (steps.length === 0) {
    return null;
  }

  const doneCount = steps.filter((s) => s.is_completed).length;
  const allDone = doneCount === steps.length;

  return (
    <View style={styles.container}>
      <Text style={[styles.progress, allDone && styles.progressDone]}>
        {allDone ? "All steps complete" : `${doneCount} of ${steps.length} steps`}
      </Text>
      {steps.map((step, i) => {
        const stepName = stepNames[step.routine_step_id] ?? `Step ${i + 1}`;
        return (
          <Pressable
            key={step.id}
            style={styles.stepRow}
            onPress={() => handleToggle(step)}
            hitSlop={4}
          >
            <View
              style={[
                styles.stepCheckbox,
                step.is_completed && styles.stepCheckboxDone,
              ]}
            >
              {step.is_completed && (
                <Text style={styles.stepCheckmark}>✓</Text>
              )}
            </View>
            <Text
              style={[
                styles.stepText,
                step.is_completed && styles.stepTextDone,
              ]}
            >
              {stepName}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: 6 },
  loading: { paddingVertical: 8 },
  progress: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "600",
    marginBottom: 4,
  },
  progressDone: { color: colors.positive },
  stepRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 5,
  },
  stepCheckbox: {
    width: 22,
    height: 22,
    borderRadius: 5,
    borderWidth: 1.5,
    borderColor: colors.cardBorder,
    justifyContent: "center",
    alignItems: "center",
    marginRight: 10,
  },
  stepCheckboxDone: {
    backgroundColor: colors.positive,
    borderColor: colors.positive,
  },
  stepCheckmark: { color: colors.buttonPrimaryText, fontSize: 11, fontWeight: "700" },
  stepText: { color: colors.textSecondary, fontSize: 14 },
  stepTextDone: { color: colors.textMuted, textDecorationLine: "line-through" },
});
