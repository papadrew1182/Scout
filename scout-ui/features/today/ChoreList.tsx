/**
 * ChoreList — inline list of TaskOccurrence rows for a block.
 *
 * Each row supports one-tap completion via useCompletionMutation, and
 * tapping the body opens the CompletionSheet (standards of done +
 * confirmation). Optimistic state comes from the AppContext mutator,
 * so the UI never waits for a network round-trip to feel responsive.
 */

import { Pressable, StyleSheet, Text, View } from "react-native";

import { TaskOccurrence } from "../lib/contracts";
import { useCompletionMutation, useUiCompletionSheet } from "../hooks";
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
        const inflight = completion.statusOf(o.occurrence_id);
        const optimisticDone = o.status === "complete" || inflight === "success";
        const optimisticPending = inflight === "pending";

        return (
          <View key={o.occurrence_id} style={styles.row}>
            {/* One-tap checkbox */}
            <Pressable
              onPress={() => completion.run(o.occurrence_id)}
              style={[
                styles.checkbox,
                optimisticDone && styles.checkboxDone,
                optimisticPending && styles.checkboxPending,
              ]}
              accessibilityRole="checkbox"
              accessibilityLabel={`Mark ${o.title} complete`}
              accessibilityState={{ checked: optimisticDone }}
              disabled={optimisticDone}
            >
              {optimisticDone && <Text style={styles.checkmark}>✓</Text>}
            </Pressable>

            {/* Body — tappable, opens the CompletionSheet for detail */}
            <Pressable
              style={styles.body}
              onPress={() => sheet.open(o.occurrence_id)}
              accessibilityRole="button"
              accessibilityLabel={`Open details for ${o.title}`}
            >
              <Text style={[styles.title, optimisticDone && styles.titleDone]} numberOfLines={2}>
                {o.title}
              </Text>
              <Text style={styles.meta} numberOfLines={1}>
                {o.owner.first_name}
                {o.assistants.length > 0
                  ? ` · with ${o.assistants.map((a) => a.first_name).join(", ")}`
                  : ""}
                {o.late ? " · LATE" : ""}
              </Text>
            </Pressable>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  list: { marginTop: 12, gap: 8 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  checkbox: {
    width: 26,
    height: 26,
    borderRadius: 13,
    borderWidth: 2,
    borderColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  checkboxDone: {
    backgroundColor: colors.positive,
    borderColor: colors.positive,
  },
  checkboxPending: {
    backgroundColor: colors.accentBg,
    borderColor: colors.accentLight,
  },
  checkmark: {
    color: colors.buttonPrimaryText,
    fontWeight: "800",
    fontSize: 13,
  },
  body: { flex: 1 },
  title: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: "600",
  },
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
  empty: {
    color: colors.textPlaceholder,
    fontSize: 12,
    fontStyle: "italic",
    marginTop: 8,
  },
});
