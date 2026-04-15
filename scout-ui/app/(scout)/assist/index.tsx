import { StyleSheet, Text, View } from "react-native";

import { colors } from "../../../lib/styles";

const SUGGESTIONS = [
  "What is on track today?",
  "Who still has work left?",
  "Show me the late items",
  "Pick a Daily Win nudge",
  "Mark Sadie's evening complete",
];

export default function AssistRoute() {
  return (
    <View>
      <Text style={styles.eyebrow}>Scout assist</Text>
      <Text style={styles.title}>Ask, suggest, intervene</Text>
      <Text style={styles.subtle}>
        Suggestion chips below. The deeper assist surface lands later in this lane.
      </Text>

      <View style={styles.chips}>
        {SUGGESTIONS.map((s) => (
          <View key={s} style={styles.chip}>
            <Text style={styles.chipText}>{s}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  eyebrow: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1.6,
    textTransform: "uppercase",
  },
  title: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: "700",
    marginTop: 4,
    marginBottom: 4,
  },
  subtle: { color: colors.textMuted, fontSize: 13, marginBottom: 16 },
  chips: { gap: 10, marginTop: 4 },
  chip: {
    backgroundColor: colors.card,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  chipText: { color: colors.textPrimary, fontSize: 13, fontWeight: "600" },
});
