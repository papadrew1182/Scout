import { useRef, useState } from "react";
import { Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { colors, fonts } from "../lib/styles";

interface Props {
  placeholder?: string;
  chips: string[];
  onSubmit: (text: string, attachment?: { blob: Blob; name: string }) => void;
  onChipPress: (chip: string) => void;
}

export function ScoutBar({ placeholder = "Ask Scout anything about your family...", chips, onSubmit, onChipPress }: Props) {
  const [value, setValue] = useState("");
  const [pendingAttachment, setPendingAttachment] = useState<{ blob: Blob; name: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleFileSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPendingAttachment({ blob: file, name: file.name });
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed && !pendingAttachment) return;
    onSubmit(trimmed, pendingAttachment ?? undefined);
    setValue("");
    setPendingAttachment(null);
  };

  return (
    <View style={styles.bar}>
      {/* Hidden file input — web only. Native renders null because RN
          has no `input` component registered; file picking on iOS/
          Android will move to expo-image-picker / expo-document-picker
          in a separate feature. */}
      {Platform.OS === "web" && (
        // @ts-ignore — lowercase `input` is HTML-only; guard above keeps it web-only
        <input
          type="file"
          accept="image/*,application/pdf"
          style={{ display: "none" }}
          ref={fileInputRef as any}
          onChange={handleFileSelected as any}
        />
      )}
      <View style={styles.inputRow}>
        <View style={styles.dot} />
        {pendingAttachment ? (
          <View style={styles.attachBadge}>
            <Text style={styles.attachBadgeText} numberOfLines={1}>{pendingAttachment.name}</Text>
            <Pressable onPress={() => setPendingAttachment(null)} accessibilityLabel="Remove attachment">
              <Text style={styles.attachBadgeRemove}>×</Text>
            </Pressable>
          </View>
        ) : null}
        <TextInput
          value={value}
          onChangeText={setValue}
          placeholder={placeholder}
          placeholderTextColor={colors.muted}
          style={styles.input}
          onSubmitEditing={submit}
          returnKeyType="send"
        />
        <Pressable
          style={styles.clipBtn}
          onPress={() => (fileInputRef.current as any)?.click()}
          accessibilityLabel="Attach image"
        >
          <Text style={styles.clipIcon}>📎</Text>
        </Pressable>
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
    outlineWidth: 0,
  } as any, // whole-object cast — RN types reject `outlineWidth` at excess-property check
  sendBtn: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: colors.purple,
    alignItems: "center",
    justifyContent: "center",
  },
  sendArrow: { color: "#FFFFFF", fontSize: 12, fontWeight: "700" },
  clipBtn: {
    width: 26,
    height: 26,
    alignItems: "center",
    justifyContent: "center",
  },
  clipIcon: { fontSize: 14 },
  attachBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: colors.purpleLight,
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 2,
    maxWidth: 120,
  },
  attachBadgeText: {
    flex: 1,
    fontSize: 10,
    color: colors.purpleDeep,
    fontFamily: fonts.body,
  },
  attachBadgeRemove: { fontSize: 12, color: colors.purpleDeep, fontWeight: "700" },

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
