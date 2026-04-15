/**
 * ChoreList — inline list of TaskOccurrence rows.
 *
 * Aligned to the canonical flat occurrence shape:
 *   {task_occurrence_id, template_key, label, owner_family_member_id,
 *    owner_name, due_at, status, block_label?, routine_key?}
 *
 * Each row supports one-tap completion via useCompletionMutation
 * (defaults completion_mode = "manual", no notes). Tapping the body
 * opens the CompletionSheet for the same occurrence so the user can
 * review the standards-of-done detail and add a note.
 *
 * Optimistic updates: when run() succeeds the AppContext flips the
 * occurrence to status "complete" in its local cache; we read that
 * status here. We also read the per-occurrence in-flight state from
 * useCompletionMutation.statusOf so the row can show a pending /
 * error state without waiting for the next refetch.
 */

import { Pressable, StyleSheet, Text, View } from "react-native";

import { TaskOccurrence } from "../lib/contracts";
import { useCompletionMutation, useUiCompletionSheet } from "../hooks";
import { formatTime } from "../lib/formatters";
import { colors } from "../../lib/styles";

interface Props {
  occurrences: TaskOccurrence[];
}

export function ChoreList({ occurrences }: Props) {
  const completion = useCompletionMutation();
  const sheet = useUiCompletionSheet();

  if (occurrences.length === 0) {
    return <Text style={styles.empty}>Nothing here.</Text>;
  }

  return (
    <View style={styles.list}>
      {occurrences.map((o) => {
        const inflight = completion.statusOf(o.task_occurrence_id);
        const optimisticDone = o.status === "complete" || inflight === "success";
        const optimisticPending = inflight === "pending";
        const isLate = o.status === "late";

        return (
          <View key={o.task_occurrence_id} style={styles.row}>
            {/* One-tap checkbox */}
            <Pressable
              onPress={() => completion.run(o.task_occurrence_id)}
              style={[
                styles.checkbox,
                optimisticDone && styles.checkboxDone,
                optimisticPending && styles.checkboxPending,
                isLate && !optimisticDone && styles.checkboxLate,
              ]}
              accessibilityRole="checkbox"
              accessibilityLabel={`Mark ${o.label} complete`}
              accessibilityState={{ checked: optimisticDone }}
              disabled={optimisticDone}
            >
              {optimisticDone && <Text style={styles.checkmark}>✓</Text>}
            </Pressable>

            {/* Body — tappable, opens the CompletionSheet */}
            <Pressable
              style={styles.body}
              onPress={() => sheet.open(o.task_occurrence_id)}
              accessibilityRole="button"
              accessibilityLabel={`Open details for ${o.label}`}
            >
              <Text
                style={[styles.title, optimisticDone && styles.titleDone]}
                numberOfLines={2}
              >
                {o.label}
              </Text>
              <Text style={styles.meta} numberOfLines={1}>
                {o.owner_name ?? "Unassigned"}
                {o.due_at ? ` · ${formatTime(o.due_at)}` : ""}
                {isLate && !optimisticDone ? " · LATE" : ""}
              </Text>
              {inflight === "error" && (
                <Text style={styles.errorMeta} numberOfLines={1}>
                  {completion.errorOf(o.task_occurrence_id) ?? "Couldn't save."}
                </Text>
              )}
            </Pressable>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  list: { gap: 4 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  checkbox: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  checkboxDone: { backgroundColor: colors.positive, borderColor: colors.positive },
  checkboxPending: {
    backgroundColor: colors.accentBg,
    borderColor: colors.accentLight,
  },
  checkboxLate: {
    borderColor: colors.negative,
  },
  checkmark: {
    color: colors.buttonPrimaryText,
    fontWeight: "800",
    fontSize: 13,
  },
  body: { flex: 1 },
  title: { color: colors.textPrimary, fontSize: 14, fontWeight: "600" },
  titleDone: {
    color: colors.textMuted,
    textDecorationLine: "line-through",
  },
  meta: {
    color: colors.textMuted,
    fontSize: 11,
    marginTop: 2,
    fontWeight: "600",
  },
  errorMeta: {
    color: colors.negative,
    fontSize: 11,
    marginTop: 2,
    fontWeight: "600",
  },
  empty: {
    color: colors.textPlaceholder,
    fontSize: 12,
    fontStyle: "italic",
    marginTop: 8,
  },
});
