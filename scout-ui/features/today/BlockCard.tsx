/**
 * BlockCard — one routine block (Morning / After School / Evening / etc.)
 *
 * Aligned to the canonical HouseholdBlock shape from canonical.py:
 *   { block_key, label, due_at, exported_to_calendar, assignments[] }
 *
 * Each assignment is one kid's slice of the block (member_name + status
 * + steps). Steps are completable; if a backend response ships an
 * assignment with empty steps[] (the current canonical projection), the
 * assignment itself is the completable target via its routine_instance_id.
 */

import { Pressable, StyleSheet, Text, View } from "react-native";

import {
  BlockAssignment,
  BlockStep,
  HouseholdBlock,
  OccurrenceStatus,
} from "../lib/contracts";
import {
  useCompletionMutation,
  useUiCompletionSheet,
} from "../hooks";
import { formatRelativeDue, formatTime } from "../lib/formatters";
import { colors } from "../../lib/styles";

interface Props {
  block: HouseholdBlock;
}

export function BlockCard({ block }: Props) {
  const dueLabel = block.due_at ? `Due ${formatTime(block.due_at)}` : "No deadline";
  const dueRelative =
    block.due_at && !allComplete(block.assignments)
      ? ` · ${formatRelativeDue(block.due_at)}`
      : "";

  return (
    <View style={[styles.card, cardAccent(block)]}>
      <View style={styles.headerRow}>
        <View style={styles.titleCol}>
          <Text style={styles.title}>{block.label}</Text>
          <Text style={styles.due}>
            {dueLabel}
            {dueRelative}
          </Text>
        </View>
        {block.exported_to_calendar && (
          <View style={styles.publishChip}>
            <Text style={styles.publishChipText}>On calendar</Text>
          </View>
        )}
      </View>

      {block.assignments.map((a) => (
        <AssignmentRow key={a.routine_instance_id} assignment={a} />
      ))}
    </View>
  );
}

function AssignmentRow({ assignment }: { assignment: BlockAssignment }) {
  return (
    <View style={styles.assignment}>
      <View style={styles.assignmentHeader}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>
            {(assignment.member_name ?? "?")[0]}
          </Text>
        </View>
        <Text style={styles.assignmentName} numberOfLines={1}>
          {assignment.member_name ?? "Unassigned"}
        </Text>
        <StatusPill status={assignment.status} />
      </View>

      {assignment.steps.length === 0 ? (
        <CompletableRow
          targetId={assignment.routine_instance_id}
          label={assignment.member_name ?? "This block"}
          status={assignment.status}
          summary
        />
      ) : (
        assignment.steps.map((step) => (
          <CompletableRow
            key={step.task_occurrence_id}
            targetId={step.task_occurrence_id}
            label={step.label}
            status={step.status}
          />
        ))
      )}
    </View>
  );
}

function CompletableRow({
  targetId,
  label,
  status,
  summary,
}: {
  targetId: string;
  label: string;
  status: OccurrenceStatus;
  summary?: boolean;
}) {
  const completion = useCompletionMutation();
  const sheet = useUiCompletionSheet();
  const inflight = completion.statusOf(targetId);
  const optimisticDone = status === "complete" || inflight === "success";
  const optimisticPending = inflight === "pending";
  const isLate = status === "late";

  return (
    <View style={styles.stepRow}>
      <Pressable
        onPress={() => completion.run(targetId)}
        style={[
          styles.checkbox,
          optimisticDone && styles.checkboxDone,
          optimisticPending && styles.checkboxPending,
          isLate && !optimisticDone && styles.checkboxLate,
        ]}
        accessibilityRole="checkbox"
        accessibilityLabel={`Mark ${label} complete`}
        accessibilityState={{ checked: optimisticDone }}
        disabled={optimisticDone}
      >
        {optimisticDone && <Text style={styles.checkmark}>✓</Text>}
      </Pressable>
      <Pressable
        style={styles.stepBody}
        onPress={() => sheet.open(targetId)}
        accessibilityRole="button"
        accessibilityLabel={`Open details for ${label}`}
      >
        <Text
          style={[
            styles.stepText,
            summary && styles.stepTextSummary,
            optimisticDone && styles.stepTextDone,
          ]}
          numberOfLines={2}
        >
          {label}
          {isLate && !optimisticDone ? " · LATE" : ""}
        </Text>
        {inflight === "error" && (
          <Text style={styles.stepError} numberOfLines={1}>
            {completion.errorOf(targetId) ?? "Couldn't save."}
          </Text>
        )}
      </Pressable>
    </View>
  );
}

function StatusPill({ status }: { status: OccurrenceStatus }) {
  return (
    <View style={[styles.pill, pillStyle(status)]}>
      <Text style={[styles.pillText, pillTextStyle(status)]}>
        {labelForStatus(status)}
      </Text>
    </View>
  );
}

function labelForStatus(s: OccurrenceStatus): string {
  switch (s) {
    case "complete":
      return "Done";
    case "late":
      return "Late";
    case "excused":
      return "Excused";
    case "open":
    default:
      return "Open";
  }
}

function pillStyle(s: OccurrenceStatus) {
  switch (s) {
    case "late":
      return { backgroundColor: colors.negativeBg };
    case "complete":
      return { backgroundColor: colors.positiveBg };
    case "excused":
      return { backgroundColor: colors.surfaceMuted };
    default:
      return { backgroundColor: colors.surfaceMuted };
  }
}

function pillTextStyle(s: OccurrenceStatus) {
  switch (s) {
    case "late":
      return { color: "#C0392B" };
    case "complete":
      return { color: "#00866B" };
    default:
      return { color: colors.textSecondary };
  }
}

function allComplete(assignments: BlockAssignment[]): boolean {
  if (assignments.length === 0) return false;
  return assignments.every((a) => a.status === "complete");
}

function cardAccent(block: HouseholdBlock) {
  if (allComplete(block.assignments)) {
    return { borderLeftColor: colors.positive, opacity: 0.85 };
  }
  if (block.assignments.some((a) => a.status === "late")) {
    return { borderLeftColor: colors.negative };
  }
  return { borderLeftColor: colors.cardBorder };
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderLeftWidth: 4,
    borderLeftColor: colors.cardBorder,
    padding: 16,
    marginBottom: 14,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 6,
  },
  titleCol: { flexShrink: 1, paddingRight: 10 },
  title: {
    color: colors.textPrimary,
    fontSize: 17,
    fontWeight: "700",
    letterSpacing: -0.2,
  },
  due: {
    color: colors.textMuted,
    fontSize: 12,
    marginTop: 3,
    fontWeight: "600",
  },
  publishChip: {
    backgroundColor: colors.accentBg,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
  },
  publishChipText: {
    color: colors.accent,
    fontSize: 9,
    fontWeight: "800",
    letterSpacing: 0.5,
    textTransform: "uppercase",
  },

  assignment: {
    marginTop: 12,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  assignmentHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 6,
  },
  avatar: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.accentBg,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 8,
    borderWidth: 1.5,
    borderColor: colors.card,
  },
  avatarText: { color: colors.accent, fontSize: 10, fontWeight: "800" },
  assignmentName: {
    flex: 1,
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: "700",
  },

  pill: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },
  pillText: {
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 0.6,
    textTransform: "uppercase",
  },

  stepRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 6,
    paddingLeft: 30,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 10,
  },
  checkboxDone: { backgroundColor: colors.positive, borderColor: colors.positive },
  checkboxPending: {
    backgroundColor: colors.accentBg,
    borderColor: colors.accentLight,
  },
  checkboxLate: { borderColor: colors.negative },
  checkmark: {
    color: colors.buttonPrimaryText,
    fontWeight: "800",
    fontSize: 11,
  },
  stepBody: { flex: 1 },
  stepText: { color: colors.textPrimary, fontSize: 13, fontWeight: "600" },
  stepTextSummary: { fontStyle: "italic", color: colors.textSecondary },
  stepTextDone: {
    color: colors.textMuted,
    textDecorationLine: "line-through",
  },
  stepError: {
    color: colors.negative,
    fontSize: 11,
    marginTop: 2,
    fontWeight: "600",
  },
});
