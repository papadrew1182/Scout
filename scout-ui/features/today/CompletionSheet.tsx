/**
 * CompletionSheet — Block 2 hardened completion experience.
 *
 * Surfaces:
 *   - eyebrow:  owner name
 *   - title:    occurrence label
 *   - status:   open / late / complete pill
 *   - due:      formatted due time + relative ("in 30 min" / "20 min late")
 *   - standards-of-done checklist when the template_key has documented
 *     standards (room reset, common-area closeout, dog walks, etc.)
 *   - free-form description fallback when no standards are available
 *   - optional notes input (sent to POST /api/household/completions)
 *   - parent-only "Mark complete on behalf of <child>" toggle, surfaced
 *     by capability rather than age. When the actor is not parent-tier,
 *     the toggle is hidden and the completion uses mode "manual".
 *
 * Loading / disabled / success / error states are explicit. The button
 * label flips through "Mark complete" → "Saving…" → "Complete!" → close.
 *
 * After success the AppContext refreshes householdToday + rewardsWeek
 * (when the server signals it) on its own; this sheet just closes.
 */

import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  HouseholdTodayResponse,
  TaskOccurrence,
  standardsForTemplate,
} from "../lib/contracts";
import {
  useCompletionMutation,
  useIsParent,
  useMe,
} from "../hooks";
import { formatRelativeDue, formatTime } from "../lib/formatters";
import { colors } from "../../lib/styles";

interface Props {
  occurrenceId: string | null;
  onClose: () => void;
  source: HouseholdTodayResponse;
}

export function CompletionSheet({ occurrenceId, onClose, source }: Props) {
  const completion = useCompletionMutation();
  const me = useMe();
  const isParent = useIsParent();

  const [notes, setNotes] = useState("");
  const [parentOverride, setParentOverride] = useState(false);

  // Reset local state whenever the sheet target changes.
  useEffect(() => {
    setNotes("");
    setParentOverride(false);
  }, [occurrenceId]);

  if (!occurrenceId) return null;

  const occ = findOccurrence(source, occurrenceId);
  if (!occ) {
    return (
      <View style={styles.sheet}>
        <Text style={styles.title}>Task not found</Text>
        <Text style={styles.subtle}>It may have been removed or already completed.</Text>
        <Pressable
          style={styles.cancelBtn}
          onPress={onClose}
          accessibilityRole="button"
          accessibilityLabel="Close"
        >
          <Text style={styles.cancelText}>Close</Text>
        </Pressable>
      </View>
    );
  }

  const inflight = completion.statusOf(occ.task_occurrence_id);
  const error = completion.errorOf(occ.task_occurrence_id);
  const done = occ.status === "complete" || inflight === "success";
  const saving = inflight === "pending";
  const standards = standardsForTemplate(occ.template_key);
  const isLate = occ.status === "late";

  const ownerName = occ.owner_name ?? "Unassigned";
  const isSelfMode =
    me.data?.user.family_member_id &&
    occ.owner_family_member_id === me.data.user.family_member_id;

  // Parent-override toggle is only relevant when the actor is parent-tier
  // AND they're not completing their own task.
  const showParentOverrideToggle = isParent && !isSelfMode && !done;

  const submit = async () => {
    await completion.run({
      task_occurrence_id: occ.task_occurrence_id,
      notes: notes.trim() || undefined,
      completion_mode: parentOverride ? "parent_override" : "manual",
    });
    // The mutation's success path shows a toast + flips local state; we
    // close the sheet so the user sees the toast over the board.
    onClose();
  };

  return (
    <View style={styles.sheet}>
      <View style={styles.headerRow}>
        <Text style={styles.eyebrow}>{ownerName}</Text>
        <StatusPill done={done} late={isLate && !done} />
      </View>
      <Text style={styles.title}>{occ.label}</Text>

      {occ.due_at && (
        <Text style={styles.due}>
          Due {formatTime(occ.due_at)}
          {!done ? ` · ${formatRelativeDue(occ.due_at)}` : ""}
        </Text>
      )}

      {standards.length > 0 ? (
        <View style={styles.standards}>
          <Text style={styles.standardsLabel}>Done when</Text>
          {standards.map((s, i) => (
            <View key={i} style={styles.standardRow}>
              <Text style={styles.standardBullet}>•</Text>
              <Text style={styles.standardText}>{s.label}</Text>
            </View>
          ))}
        </View>
      ) : (
        <Text style={styles.fallback}>
          No standards-of-done detail yet for this task. Confirm with the
          owner before marking complete.
        </Text>
      )}

      {!done && (
        <View style={styles.notesBlock}>
          <Text style={styles.notesLabel}>Notes (optional)</Text>
          <TextInput
            style={styles.notesInput}
            value={notes}
            onChangeText={setNotes}
            placeholder="Anything to record? e.g. 'Excused for piano lesson'"
            placeholderTextColor={colors.textPlaceholder}
            multiline
            numberOfLines={3}
            editable={!saving}
            accessibilityLabel="Optional completion notes"
          />
        </View>
      )}

      {showParentOverrideToggle && (
        <View style={styles.toggleRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.toggleLabel}>Mark complete on their behalf</Text>
            <Text style={styles.toggleHelp}>
              Records this as a parent override on {ownerName}.
            </Text>
          </View>
          <Switch
            value={parentOverride}
            onValueChange={setParentOverride}
            disabled={saving}
            accessibilityLabel="Parent override toggle"
          />
        </View>
      )}

      {error && <Text style={styles.errorText}>{error}</Text>}

      <View style={styles.actions}>
        <Pressable
          style={styles.cancelBtn}
          onPress={onClose}
          disabled={saving}
          accessibilityRole="button"
          accessibilityLabel="Close completion sheet"
        >
          <Text style={styles.cancelText}>Close</Text>
        </Pressable>
        <Pressable
          style={[
            styles.confirmBtn,
            done && styles.confirmDone,
            saving && styles.confirmSaving,
          ]}
          accessibilityRole="button"
          accessibilityLabel="Confirm complete"
          disabled={done || saving}
          onPress={submit}
        >
          {saving ? (
            <View style={styles.savingRow}>
              <ActivityIndicator size="small" color={colors.buttonPrimaryText} />
              <Text style={styles.confirmText}>Saving…</Text>
            </View>
          ) : (
            <Text style={styles.confirmText}>
              {done ? "Done" : "Mark complete"}
            </Text>
          )}
        </Pressable>
      </View>
    </View>
  );
}

function StatusPill({ done, late }: { done: boolean; late: boolean }) {
  if (done) {
    return (
      <View style={[styles.pill, styles.pillDone]}>
        <Text style={[styles.pillText, { color: "#00866B" }]}>Done</Text>
      </View>
    );
  }
  if (late) {
    return (
      <View style={[styles.pill, styles.pillLate]}>
        <Text style={[styles.pillText, { color: "#C0392B" }]}>Late</Text>
      </View>
    );
  }
  return (
    <View style={[styles.pill, styles.pillOpen]}>
      <Text style={[styles.pillText, { color: colors.textSecondary }]}>Open</Text>
    </View>
  );
}

/**
 * Resolve a completable target by id across the canonical
 * household-today shape. Standalone + weekly rows are full
 * TaskOccurrence objects, so they're returned as-is. Block-internal
 * targets need to be synthesized from the parent block + parent
 * assignment because steps only carry {task_occurrence_id, label,
 * status} and the assignment carries owner; due_at lives on the block.
 *
 * The lookup matches an id against EITHER `assignment.routine_instance_id`
 * (the canonical projection currently overloads this with the
 * task_occurrence_id) OR `step.task_occurrence_id` (when the backend
 * ships richer steps[]). Both code paths return the same shape so the
 * sheet renders uniformly.
 */
function findOccurrence(
  source: HouseholdTodayResponse,
  id: string,
): TaskOccurrence | null {
  const std = source.standalone_chores.find((o) => o.task_occurrence_id === id);
  if (std) return std;
  const wk = source.weekly_items.find((o) => o.task_occurrence_id === id);
  if (wk) return wk;

  for (const b of source.blocks) {
    for (const a of b.assignments) {
      // Empty-steps assignment: the assignment itself is the target.
      if (a.steps.length === 0 && a.routine_instance_id === id) {
        return synthesizeFromAssignment(b, a, a.routine_instance_id, a.status);
      }
      const step = a.steps.find((s) => s.task_occurrence_id === id);
      if (step) {
        return synthesizeFromAssignment(b, a, step.task_occurrence_id, step.status, step.label);
      }
    }
  }
  return null;
}

function synthesizeFromAssignment(
  block: HouseholdTodayResponse["blocks"][number],
  assignment: HouseholdTodayResponse["blocks"][number]["assignments"][number],
  task_occurrence_id: string,
  status: TaskOccurrence["status"],
  stepLabel?: string,
): TaskOccurrence {
  return {
    task_occurrence_id,
    template_key: null,
    label: stepLabel ?? `${block.label} · ${assignment.member_name ?? "Unassigned"}`,
    owner_family_member_id: assignment.family_member_id,
    owner_name: assignment.member_name,
    due_at: block.due_at,
    status,
    block_label: block.label,
    routine_key: block.block_key,
  };
}

const styles = StyleSheet.create({
  sheet: {
    backgroundColor: colors.card,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 18,
    marginTop: 18,
    marginBottom: 12,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  eyebrow: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1.4,
    textTransform: "uppercase",
  },
  title: {
    color: colors.textPrimary,
    fontSize: 18,
    fontWeight: "700",
    marginTop: 6,
  },
  subtle: { color: colors.textMuted, fontSize: 12, marginTop: 6, fontWeight: "600" },
  due: { color: colors.textMuted, fontSize: 12, marginTop: 4, fontWeight: "600" },

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
  pillDone: { backgroundColor: colors.positiveBg },
  pillLate: { backgroundColor: colors.negativeBg },
  pillOpen: { backgroundColor: colors.surfaceMuted },

  standards: { marginTop: 14 },
  standardsLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 1.2,
    marginBottom: 8,
  },
  standardRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: 6,
  },
  standardBullet: {
    color: colors.accent,
    fontSize: 14,
    fontWeight: "800",
    marginRight: 8,
  },
  standardText: { color: colors.textPrimary, fontSize: 13, flex: 1, lineHeight: 18 },
  fallback: {
    color: colors.textSecondary,
    fontSize: 12,
    fontStyle: "italic",
    marginTop: 12,
    lineHeight: 16,
  },

  notesBlock: { marginTop: 18 },
  notesLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 1.2,
    marginBottom: 8,
  },
  notesInput: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 10,
    padding: 12,
    color: colors.textPrimary,
    fontSize: 13,
    minHeight: 60,
    textAlignVertical: "top",
  },

  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 16,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 10,
    backgroundColor: colors.surfaceMuted,
  },
  toggleLabel: { color: colors.textPrimary, fontSize: 13, fontWeight: "700" },
  toggleHelp: { color: colors.textMuted, fontSize: 11, marginTop: 2 },

  errorText: { color: colors.negative, fontSize: 12, marginTop: 12 },

  actions: { flexDirection: "row", gap: 10, marginTop: 18 },
  cancelBtn: {
    flex: 1,
    backgroundColor: colors.surfaceMuted,
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
  },
  cancelText: { color: colors.textSecondary, fontWeight: "700", fontSize: 13 },
  confirmBtn: {
    flex: 1,
    backgroundColor: colors.accent,
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
  },
  confirmDone: { backgroundColor: colors.positive },
  confirmSaving: { backgroundColor: colors.accentLight },
  confirmText: {
    color: colors.buttonPrimaryText,
    fontWeight: "800",
    fontSize: 13,
    marginLeft: 6,
  },
  savingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
});
