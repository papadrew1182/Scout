/**
 * CompletionSheet — starter completion confirmation surface.
 *
 * This is the *first pass* of the completion experience. It opens
 * inline at the bottom of TodayHome when the user taps a chore body
 * (not the one-tap checkbox). Surfaces:
 *   - the task title + owner + assistants
 *   - the standards-of-done checklist
 *   - a Confirm button that calls completeOccurrence()
 *   - a Cancel/Close button
 *
 * Future blocks layer in: photo evidence, parent override, late notes,
 * "excused" path, push back to a different owner. For now the
 * structure is in place and wired to the same useCompletionMutation
 * the inline checkbox uses, so reward preview refresh already works.
 */

import { Pressable, StyleSheet, Text, View } from "react-native";

import { HouseholdTodayResponse, TaskOccurrence } from "../lib/contracts";
import { useCompletionMutation } from "../hooks";
import { colors } from "../../lib/styles";

interface Props {
  occurrenceId: string | null;
  onClose: () => void;
  source: HouseholdTodayResponse;
}

export function CompletionSheet({ occurrenceId, onClose, source }: Props) {
  const completion = useCompletionMutation();
  if (!occurrenceId) return null;

  const occ = findOccurrence(source, occurrenceId);
  if (!occ) {
    return (
      <View style={styles.sheet}>
        <Text style={styles.title}>Task not found</Text>
        <Pressable style={styles.cancel} onPress={onClose}>
          <Text style={styles.cancelText}>Close</Text>
        </Pressable>
      </View>
    );
  }

  const inflight = completion.statusOf(occ.occurrence_id);
  const done = occ.status === "complete" || inflight === "success";

  return (
    <View style={styles.sheet}>
      <Text style={styles.eyebrow}>{occ.owner.first_name}</Text>
      <Text style={styles.title}>{occ.title}</Text>
      {occ.assistants.length > 0 && (
        <Text style={styles.subtle}>
          With {occ.assistants.map((a) => a.first_name).join(", ")}
        </Text>
      )}

      {occ.standards.length > 0 ? (
        <View style={styles.standards}>
          <Text style={styles.standardsLabel}>Done when</Text>
          {occ.standards.map((s, i) => (
            <View key={i} style={styles.standardRow}>
              <Text style={styles.standardBullet}>•</Text>
              <Text style={styles.standardText}>{s.label}</Text>
            </View>
          ))}
        </View>
      ) : occ.description ? (
        <Text style={styles.description}>{occ.description}</Text>
      ) : null}

      {occ.late && <Text style={styles.late}>Past deadline.</Text>}

      <View style={styles.actions}>
        <Pressable style={styles.cancel} onPress={onClose} accessibilityRole="button">
          <Text style={styles.cancelText}>Close</Text>
        </Pressable>
        <Pressable
          style={[styles.confirm, done && styles.confirmDone]}
          accessibilityRole="button"
          accessibilityLabel="Confirm complete"
          disabled={done || inflight === "pending"}
          onPress={() => {
            completion.run(occ.occurrence_id).then(() => onClose());
          }}
        >
          <Text style={styles.confirmText}>
            {done ? "Done" : inflight === "pending" ? "Saving…" : "Mark complete"}
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

function findOccurrence(
  source: HouseholdTodayResponse,
  id: string,
): TaskOccurrence | null {
  for (const b of source.blocks) {
    const hit = b.occurrences.find((o) => o.occurrence_id === id);
    if (hit) return hit;
  }
  return source.standalone_occurrences.find((o) => o.occurrence_id === id) ?? null;
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
    marginTop: 4,
  },
  subtle: { color: colors.textMuted, fontSize: 12, marginTop: 4, fontWeight: "600" },
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
    marginBottom: 4,
  },
  standardBullet: {
    color: colors.accent,
    fontSize: 14,
    fontWeight: "800",
    marginRight: 8,
  },
  standardText: { color: colors.textPrimary, fontSize: 13, flex: 1, lineHeight: 18 },
  description: {
    color: colors.textSecondary,
    fontSize: 13,
    marginTop: 12,
    lineHeight: 18,
  },
  late: { color: colors.negative, fontSize: 12, fontWeight: "700", marginTop: 10 },
  actions: {
    flexDirection: "row",
    gap: 10,
    marginTop: 18,
  },
  cancel: {
    flex: 1,
    backgroundColor: colors.surfaceMuted,
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
  },
  cancelText: { color: colors.textSecondary, fontWeight: "700", fontSize: 13 },
  confirm: {
    flex: 1,
    backgroundColor: colors.accent,
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
  },
  confirmDone: { backgroundColor: colors.positive },
  confirmText: { color: colors.buttonPrimaryText, fontWeight: "800", fontSize: 13 },
});
