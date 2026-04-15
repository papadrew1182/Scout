/**
 * HouseholdBoard — vertical list of routine + chore blocks.
 *
 * Receives a household-today payload (already filtered by TodayHome
 * if a child is focused) and renders:
 *   1. blocks[] as BlockCards
 *   2. standalone_chores[] as a single grouped section
 *   3. weekly_items[] as a single grouped section
 *
 * Block ordering: any block with a late assignment first, then any
 * still-open block, then fully-done blocks. Within each tier, sort by
 * due_at. The canonical block contract no longer carries a block-level
 * status enum — tier is derived from assignment statuses instead.
 */

import { StyleSheet, Text, View } from "react-native";

import { HouseholdBlock, HouseholdTodayResponse } from "../lib/contracts";
import { colors } from "../../lib/styles";
import { BlockCard } from "./BlockCard";
import { ChoreList } from "./ChoreList";

interface Props {
  data: HouseholdTodayResponse;
}

export function HouseholdBoard({ data }: Props) {
  const blocks = [...data.blocks].sort(blockSort);
  const standalone = data.standalone_chores;
  const weekly = data.weekly_items;

  return (
    <View>
      {blocks.map((b) => (
        <BlockCard key={b.block_key} block={b} />
      ))}

      {standalone.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Ownership chores</Text>
          <View style={styles.sectionCard}>
            <ChoreList occurrences={standalone} />
          </View>
        </View>
      )}

      {weekly.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Weekly</Text>
          <View style={styles.sectionCard}>
            <ChoreList occurrences={weekly} />
          </View>
        </View>
      )}
    </View>
  );
}

function blockTier(b: HouseholdBlock): number {
  if (b.assignments.length > 0 && b.assignments.every((a) => a.status === "complete")) {
    return 2; // done
  }
  if (b.assignments.some((a) => a.status === "late")) {
    return 0; // late first
  }
  return 1; // open in the middle
}

function blockSort(a: HouseholdBlock, b: HouseholdBlock): number {
  const tierDelta = blockTier(a) - blockTier(b);
  if (tierDelta !== 0) return tierDelta;
  const ad = a.due_at ? new Date(a.due_at).getTime() : Number.POSITIVE_INFINITY;
  const bd = b.due_at ? new Date(b.due_at).getTime() : Number.POSITIVE_INFINITY;
  return ad - bd;
}

const styles = StyleSheet.create({
  section: {
    marginTop: 6,
  },
  sectionTitle: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 1.4,
    marginTop: 18,
    marginBottom: 8,
    paddingHorizontal: 4,
  },
  sectionCard: {
    backgroundColor: colors.card,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 12,
    marginBottom: 14,
  },
});
