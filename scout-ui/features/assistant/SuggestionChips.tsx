/**
 * SuggestionChips — five pre-canned questions the assist surface answers
 * locally against the existing AppContext slices. No AI / backend.
 *
 * Tap a chip → expands an inline AnswerCard underneath with the
 * computed answer. Tapping again collapses. Selection state is local
 * to this component because Block 3 doesn't add new global ui state.
 */

import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "../../lib/styles";

export type ChipId =
  | "due_next"
  | "who_late"
  | "daily_win_track"
  | "hearth_tonight"
  | "parent_attention";

export interface ChipDef {
  id: ChipId;
  label: string;
}

export const CHIPS: ChipDef[] = [
  { id: "due_next", label: "What is due next?" },
  { id: "who_late", label: "Who is late?" },
  { id: "daily_win_track", label: "Am I on track for a Daily Win?" },
  { id: "hearth_tonight", label: "What will Hearth show tonight?" },
  { id: "parent_attention", label: "What needs parent attention?" },
];

interface Props {
  selected: ChipId | null;
  onSelect: (id: ChipId | null) => void;
}

export function SuggestionChips({ selected, onSelect }: Props) {
  return (
    <View style={styles.row}>
      {CHIPS.map((c) => {
        const active = selected === c.id;
        return (
          <Pressable
            key={c.id}
            style={[styles.chip, active && styles.chipActive]}
            onPress={() => onSelect(active ? null : c.id)}
            accessibilityRole="button"
            accessibilityLabel={c.label}
            accessibilityState={{ selected: active }}
          >
            <Text style={[styles.chipText, active && styles.chipTextActive]}>
              {c.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

// Re-export the local hook helper for ScoutAssistEntry consumers.
export function useChipSelection() {
  const [selected, setSelected] = useState<ChipId | null>(null);
  return { selected, setSelected };
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginVertical: 12,
  },
  chip: {
    backgroundColor: colors.card,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingHorizontal: 14,
    paddingVertical: 9,
  },
  chipActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  chipText: { color: colors.textSecondary, fontSize: 12, fontWeight: "700" },
  chipTextActive: { color: colors.buttonPrimaryText },
});
