import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { StepList } from "./StepList";
import { colors } from "../lib/styles";
import type { TaskInstance } from "../lib/types";

interface Props {
  task: TaskInstance;
  name: string;
  isRoutine: boolean;
  routineId: string | null;
  description: string | null;
  onToggle: () => void;
  onStepChange?: () => void;
}

export function TaskCard({ task, name, isRoutine, routineId, description, onToggle, onStepChange }: Props) {
  const [expanded, setExpanded] = useState(false);
  const done = task.override_completed ?? task.is_completed;

  const dueTime = new Date(task.due_at).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });

  const hasDetails = isRoutine || !!description || !!task.override_note;

  const handleCheckbox = () => {
    if (isRoutine) return;
    onToggle();
  };

  const safeTestId = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

  return (
    <Pressable
      style={[styles.card, done && styles.cardDone]}
      onPress={hasDetails ? () => setExpanded(!expanded) : undefined}
      testID={`task-card-${safeTestId}`}
    >
      <View style={styles.row}>
        <Pressable
          style={[styles.checkbox, done && styles.checkboxDone]}
          onPress={handleCheckbox}
          hitSlop={8}
          testID={`task-checkbox-${safeTestId}`}
          accessibilityLabel={`Mark ${name} complete`}
        >
          {done && <Text style={styles.checkmark}>✓</Text>}
        </Pressable>

        <View style={styles.content}>
          <Text style={[styles.name, done && styles.nameDone]} numberOfLines={2}>
            {name}
          </Text>
          <Text style={[styles.dueTime, done && styles.dueTimeDone]}>
            by {dueTime}
          </Text>
        </View>

        {hasDetails && (
          <Text style={[styles.chevron, done && styles.chevronDone]}>
            {expanded ? "−" : "+"}
          </Text>
        )}
      </View>

      {task.override_completed !== null && !expanded && (
        <View style={styles.excusedBadgeRow}>
          <View style={styles.excusedDot} />
          <Text style={styles.excusedBadge}>Excused</Text>
        </View>
      )}

      {expanded && (
        <View style={styles.details}>
          {description ? (
            <Text style={styles.description}>{description}</Text>
          ) : null}

          {task.override_note ? (
            <View style={styles.excusedRow}>
              <View style={styles.excusedDot} />
              <View>
                <Text style={styles.excusedLabel}>Excused</Text>
                <Text style={styles.excusedNote}>{task.override_note}</Text>
              </View>
            </View>
          ) : null}

          {isRoutine && routineId && (
            <StepList
              taskInstanceId={task.id}
              routineId={routineId}
              onStepChange={onStepChange}
            />
          )}
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 16,
    marginBottom: 10,
    borderLeftWidth: 3,
    borderLeftColor: colors.accent,
  },
  cardDone: {
    borderLeftColor: colors.positive,
    opacity: 0.6,
    backgroundColor: colors.surfaceMuted,
  },
  row: { flexDirection: "row", alignItems: "center" },
  checkbox: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: colors.accent,
    justifyContent: "center",
    alignItems: "center",
    marginRight: 14,
  },
  checkboxDone: {
    backgroundColor: colors.positive,
    borderColor: colors.positive,
  },
  checkmark: { color: colors.buttonPrimaryText, fontSize: 14, fontWeight: "700" },
  content: { flex: 1 },
  name: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: "600",
    letterSpacing: -0.2,
  },
  nameDone: {
    color: colors.textMuted,
    textDecorationLine: "line-through",
  },
  dueTime: { color: colors.textMuted, fontSize: 12, marginTop: 3 },
  dueTimeDone: { color: colors.textPlaceholder },
  chevron: {
    color: colors.textMuted,
    fontSize: 20,
    fontWeight: "300",
    paddingLeft: 10,
  },
  chevronDone: { color: colors.textPlaceholder },

  excusedBadgeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: 8,
    marginLeft: 42,
  },
  excusedDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.warning,
  },
  excusedBadge: {
    color: colors.warning,
    fontSize: 11,
    fontWeight: "600",
  },

  details: {
    marginTop: 14,
    marginLeft: 42,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  description: {
    color: colors.textSecondary,
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 10,
  },
  excusedRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
    marginBottom: 10,
  },
  excusedLabel: {
    color: colors.warning,
    fontSize: 12,
    fontWeight: "600",
    marginBottom: 2,
  },
  excusedNote: { color: colors.textSecondary, fontSize: 13 },
});
