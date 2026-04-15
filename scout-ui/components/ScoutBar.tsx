import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { colors, fonts } from "../lib/styles";

interface Props {
  placeholder?: string;
  chips: string[];
  onSubmit: (text: string) => void;
  onChipPress: (chip: string) => void;
}

export function ScoutBar({ placeholder = "Ask Scout anything about your family...", chips, onSubmit, onChipPress }: Props) {
  const [value, setValue] = useState("");

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
    setValue("");
  };

  return (
    <View style={styles.bar}>
      <View style={styles.inputRow}>
        <View style={styles.dot} />
        <TextInput
          value={value}
          onChangeText={setValue}
          placeholder={placeholder}
          placeholderTextColor={colors.muted}
          style={styles.input}
          onSubmitEditing={submit}
          returnKeyType="send"
        />
        <Pressable style={styles.sendBtn} onPress={submit} accessibilityLabel="Send to Scout">
          <Text style={styles.sendArrow}>↗</Text>
        </Pressable>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
        {chips.map((c) => (
          <Pressable key={c} style={styles.chip} onPress={() => onChipPress(c)}>
            <Text style={styles.chipText}>{c}</Text>
          </Pressable>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    backgroundColor: colors.card,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingHorizontal: 16,
    paddingVertical: 10,
    gap: 8,
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: colors.bg,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.green,
  },
  input: {
    flex: 1,
    fontSize: 13,
    color: colors.text,
    fontFamily: fonts.body,
    paddingVertical: 0,
  } as any, // suppress web outline
  sendBtn: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: colors.purple,
    alignItems: "center",
    justifyContent: "center",
  },
  sendArrow: { color: "#FFFFFF", fontSize: 12, fontWeight: "700" },

  chipRow: {
    flexDirection: "row",
    gap: 6,
    paddingRight: 16,
  },
  chip: {
    backgroundColor: colors.purpleLight,
    borderWidth: 1,
    borderColor: colors.purpleMid,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 4,
  },
  chipText: { fontSize: 11, color: colors.purpleDeep, fontFamily: fonts.body, fontWeight: "500" },
});
