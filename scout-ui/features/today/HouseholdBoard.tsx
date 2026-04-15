/**
 * HouseholdBoard — vertical list of routine + chore blocks.
 *
 * Pure layout component. Receives a (possibly filtered) household-today
 * payload and renders one BlockCard per routine block, plus a tail
 * section for any standalone occurrences.
 */

import { StyleSheet, Text, View } from "react-native";

import { HouseholdTodayResponse } from "../lib/contracts";
import { colors } from "../../lib/styles";
import { BlockCard } from "./BlockCard";
import { ChoreList } from "./ChoreList";

interface Props {
  data: HouseholdTodayResponse;
}

export function HouseholdBoard({ data }: Props) {
  const blocks = [...data.blocks].sort(blockSort);
  const standalone = data.standalone_occurrences;

  if (blocks.length === 0 && standalone.length === 0) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyTitle}>No work for today</Text>
        <Text style={styles.emptyBody}>
          Either everything is done or no chores were generated. Check the
          control plane if this seems wrong.
        </Text>
      </View>
    );
  }

  return (
    <View>
      {blocks.map((b) => (
        <BlockCard key={b.block_id} block={b} />
      ))}

      {standalone.length > 0 && (
        <>
          <Text style={styles.section}>Other tasks</Text>
          <ChoreList occurrences={standalone} />
        </>
      )}
    </View>
  );
}

/** Sort blocks: active/late/due_soon first, then upcoming, done last. */
function blockSort(a: HouseholdTodayResponse["blocks"][number], b: HouseholdTodayResponse["blocks"][number]) {
  const rank = (s: string) =>
    ({
      late: 0,
      due_soon: 1,
      active: 2,
      blocked: 3,
      upcoming: 4,
      done: 5,
    })[s] ?? 99;
  const r = rank(a.status) - rank(b.status);
  if (r !== 0) return r;
  return new Date(a.due_at).getTime() - new Date(b.due_at).getTime();
}

const styles = StyleSheet.create({
  section: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 1.4,
    marginTop: 24,
    marginBottom: 8,
  },
  empty: {
    marginTop: 30,
    alignItems: "center",
    paddingHorizontal: 12,
  },
  emptyTitle: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: "700",
    marginBottom: 6,
  },
  emptyBody: {
    color: colors.textMuted,
    fontSize: 13,
    textAlign: "center",
    lineHeight: 18,
  },
});
