import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { colors, fonts } from "../lib/styles";
import {
  mockScoutResponse,
  SAMPLE_THREAD,
  QUICK_ACTIONS_BY_SURFACE,
  type ScoutSurface,
} from "../lib/mockScout";
import { fetchReady } from "../lib/api";

interface Turn { role: "user" | "assistant"; content: string; }

interface Props {
  surface: ScoutSurface;
}

export function ScoutSidebar({ surface }: Props) {
  const [thread, setThread] = useState<Turn[]>(() =>
    SAMPLE_THREAD.flatMap((t) => [
      { role: "user", content: t.user } as Turn,
      { role: "assistant", content: t.assistant } as Turn,
    ]),
  );
  const [value, setValue] = useState("");
  const [readyState, setReadyState] = useState<"checking" | "ok" | "disabled">("checking");

  useEffect(() => {
    let cancelled = false;
    fetchReady()
      .then((r) => {
        if (cancelled) return;
        setReadyState(r.ai_available ? "ok" : "disabled");
      })
      .catch(() => {
        if (cancelled) return;
        setReadyState("disabled");
      });
    return () => { cancelled = true; };
  }, []);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setThread((prev) => [...prev, { role: "user", content: trimmed }]);
    setValue("");
    const reply = await mockScoutResponse(trimmed);
    setThread((prev) => [...prev, { role: "assistant", content: reply }]);
  };

  const actions = QUICK_ACTIONS_BY_SURFACE[surface] ?? [];

  return (
    <View style={styles.panel}>
      <View style={styles.titleRow}>
        <View style={styles.dot} />
        <Text style={styles.title}>Scout</Text>
      </View>

      {readyState === "disabled" ? (
        <View style={styles.disabledWrap}>
          <Text style={styles.disabledTitle}>Scout AI unavailable</Text>
          <Text style={styles.disabledSub}>Try again later.</Text>
        </View>
      ) : readyState === "checking" ? (
        <Text style={styles.disabledSub}>Checking availability…</Text>
      ) : (
        <>
          <ScrollView style={styles.thread} contentContainerStyle={{ gap: 4 }}>
            {thread.map((t, i) => (
              <View key={i} style={t.role === "user" ? styles.userBubble : styles.assistantBubble}>
                <Text style={t.role === "user" ? styles.userText : styles.assistantText}>{t.content}</Text>
              </View>
            ))}
          </ScrollView>

          <View style={{ marginTop: 8 }}>
            <Text style={styles.actionsHead}>Quick actions</Text>
            {actions.map((a) => (
              <Pressable key={a} style={styles.actionPill} onPress={() => send(a)} accessibilityRole="button" accessibilityLabel={`Run quick action: ${a}`}>
                <Text style={styles.actionText}>{a}</Text>
              </Pressable>
            ))}
          </View>

          <View style={styles.miniInput}>
            <TextInput
              value={value}
              onChangeText={setValue}
              placeholder="Ask Scout..."
              placeholderTextColor={colors.muted}
              style={styles.miniInputField}
              onSubmitEditing={() => send(value)}
              returnKeyType="send"
            />
            <Pressable style={styles.miniSend} onPress={() => send(value)} accessibilityRole="button" accessibilityLabel="Send to Scout">
              <Text style={styles.miniSendArrow}>↗</Text>
            </Pressable>
          </View>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  panel: {
    width: 200,
    backgroundColor: colors.card,
    borderLeftWidth: 1,
    borderLeftColor: colors.border,
    padding: 14,
    flexShrink: 0,
  },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 10 },
  dot: { width: 7, height: 7, borderRadius: 4, backgroundColor: colors.green },
  title: {
    fontSize: 10,
    fontWeight: "600",
    color: colors.muted,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    fontFamily: fonts.body,
  },

  thread: { flex: 1 },
  userBubble: {
    backgroundColor: colors.purpleLight,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 5,
  },
  userText: { fontSize: 10, color: colors.purpleDeep, lineHeight: 14, fontFamily: fonts.body },
  assistantBubble: {
    backgroundColor: colors.bg,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderWidth: 1,
    borderColor: colors.border,
  },
  assistantText: { fontSize: 10, color: colors.text, lineHeight: 14, fontFamily: fonts.body },

  actionsHead: {
    fontSize: 9,
    fontWeight: "600",
    color: colors.muted,
    textTransform: "uppercase",
    letterSpacing: 0.6,
    marginBottom: 4,
    fontFamily: fonts.body,
  },
  actionPill: {
    backgroundColor: colors.purpleLight,
    borderWidth: 1,
    borderColor: colors.purpleMid,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 4,
    marginBottom: 4,
  },
  actionText: { fontSize: 9, color: colors.purpleDeep, fontWeight: "500", fontFamily: fonts.body },

  miniInput: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: colors.bg,
    borderRadius: 12,
    paddingHorizontal: 8,
    paddingVertical: 5,
    borderWidth: 1,
    borderColor: colors.border,
    marginTop: 8,
  },
  miniInputField: {
    flex: 1,
    fontSize: 10,
    color: colors.text,
    fontFamily: fonts.body,
    outlineWidth: 0,
  } as any,
  miniSend: {
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: colors.purple,
    alignItems: "center",
    justifyContent: "center",
  },
  miniSendArrow: { color: "#FFFFFF", fontSize: 9, fontWeight: "700" },

  disabledWrap: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 12,
    gap: 6,
  },
  disabledTitle: {
    fontSize: 11,
    fontWeight: "700",
    color: colors.text,
    fontFamily: fonts.body,
    textAlign: "center",
  },
  disabledSub: {
    fontSize: 9,
    color: colors.muted,
    fontFamily: fonts.body,
    textAlign: "center",
    lineHeight: 13,
  },
});
