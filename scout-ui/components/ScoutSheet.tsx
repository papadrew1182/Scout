import { useEffect, useRef, useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { colors, fonts } from "../lib/styles";
import { SAMPLE_THREAD, QUICK_ACTIONS_BY_SURFACE, type ScoutSurface } from "../lib/mockScout";
import { fetchReady, sendChatMessageStream } from "../lib/api";

interface Turn { role: "user" | "assistant"; content: string; }

interface Props {
  visible: boolean;
  onClose: () => void;
  surface: ScoutSurface;
  initialPrompt?: string | null;
}

export function ScoutSheet({ visible, onClose, surface, initialPrompt }: Props) {
  const [thread, setThread] = useState<Turn[]>(() =>
    SAMPLE_THREAD.flatMap((t) => [
      { role: "user", content: t.user } as Turn,
      { role: "assistant", content: t.assistant } as Turn,
    ]),
  );
  const [value, setValue] = useState("");
  const [readyState, setReadyState] = useState<"checking" | "ok" | "disabled">("checking");
  const lastSentRef = useRef<string | null>(null);

  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    setReadyState("checking");
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
  }, [visible]);

  useEffect(() => {
    if (!visible || !initialPrompt || readyState !== "ok") return;
    // Send the prompt once — track with a ref to avoid double-fire
    if (lastSentRef.current === initialPrompt) return;
    lastSentRef.current = initialPrompt;
    send(initialPrompt);
  }, [visible, initialPrompt, readyState]);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setThread((prev) => [...prev, { role: "user", content: trimmed }]);
    setValue("");
    let accumulated = "";
    setThread((prev) => [...prev, { role: "assistant", content: "..." }]);
    await sendChatMessageStream(
      trimmed,
      { surface },
      {
        onEvent: (event) => {
          if (event.type === "text") {
            accumulated += event.text;
            setThread((prev) => {
              const copy = [...prev];
              copy[copy.length - 1] = { role: "assistant", content: accumulated };
              return copy;
            });
          } else if (event.type === "error") {
            setThread((prev) => {
              const copy = [...prev];
              copy[copy.length - 1] = { role: "assistant", content: `Error: ${event.message}` };
              return copy;
            });
          }
        },
        onError: (err) => {
          setThread((prev) => {
            const copy = [...prev];
            copy[copy.length - 1] = { role: "assistant", content: `Error: ${err.message}` };
            return copy;
          });
        },
      },
    );
  };

  const actions = QUICK_ACTIONS_BY_SURFACE[surface] ?? [];

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose} transparent={false}>
      <View style={styles.sheet}>
        <View style={styles.header}>
          <Text style={styles.title}>Scout</Text>
          <Pressable onPress={onClose} hitSlop={10} accessibilityRole="button" accessibilityLabel="Close Scout">
            <Text style={styles.close}>Close</Text>
          </Pressable>
        </View>

        {readyState === "checking" && (
          <View style={styles.disabledWrap}>
            <Text style={styles.disabledSub}>Checking Scout AI availability…</Text>
          </View>
        )}

        {readyState === "disabled" && (
          <View style={styles.disabledWrap}>
            <Text style={styles.disabledTitle}>Scout AI is unavailable right now</Text>
            <Text style={styles.disabledSub}>
              The backend reports ai_available=false. Try again later, or ask a parent to check the Anthropic API key.
            </Text>
          </View>
        )}

        {readyState === "ok" && (
          <>
            <ScrollView style={{ flex: 1 }} contentContainerStyle={styles.threadContent}>
              {thread.map((t, i) => (
                <View key={i} style={[styles.bubble, t.role === "user" ? styles.userBubble : styles.assistantBubble]}>
                  <Text style={t.role === "user" ? styles.userText : styles.assistantText}>{t.content}</Text>
                </View>
              ))}
            </ScrollView>

            <View style={styles.actionsRow}>
              {actions.map((a) => (
                <Pressable key={a} style={styles.actionChip} onPress={() => send(a)}>
                  <Text style={styles.actionChipText}>{a}</Text>
                </Pressable>
              ))}
            </View>

            <View style={styles.inputRow}>
              <TextInput
                value={value}
                onChangeText={setValue}
                placeholder="Ask Scout..."
                placeholderTextColor={colors.muted}
                style={styles.input}
                onSubmitEditing={() => send(value)}
                returnKeyType="send"
              />
              <Pressable style={styles.send} onPress={() => send(value)} accessibilityRole="button" accessibilityLabel="Send to Scout">
                <Text style={styles.sendText}>Send</Text>
              </Pressable>
            </View>
          </>
        )}
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  sheet: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: 16,
    backgroundColor: colors.sidebar,
  },
  title: { color: "#FFFFFF", fontSize: 16, fontWeight: "600", fontFamily: fonts.body },
  close: { color: colors.purple, fontSize: 14, fontWeight: "600", fontFamily: fonts.body },

  threadContent: { padding: 16, gap: 8 },
  bubble: { borderRadius: 12, padding: 12, maxWidth: "85%" },
  userBubble: { backgroundColor: colors.purple, alignSelf: "flex-end" },
  assistantBubble: { backgroundColor: colors.card, alignSelf: "flex-start", borderWidth: 1, borderColor: colors.border },
  userText: { color: "#FFFFFF", fontSize: 14, fontFamily: fonts.body },
  assistantText: { color: colors.text, fontSize: 14, fontFamily: fonts.body },

  actionsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    paddingHorizontal: 16,
    paddingBottom: 8,
  },
  actionChip: {
    backgroundColor: colors.purpleLight,
    borderWidth: 1,
    borderColor: colors.purpleMid,
    borderRadius: 14,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  actionChipText: { color: colors.purpleDeep, fontSize: 12, fontFamily: fonts.body },

  inputRow: {
    flexDirection: "row",
    gap: 8,
    padding: 16,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.card,
  },
  input: {
    flex: 1,
    backgroundColor: colors.bg,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 14,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    fontFamily: fonts.body,
    outlineWidth: 0,
  } as any,
  send: {
    backgroundColor: colors.purple,
    borderRadius: 12,
    paddingHorizontal: 18,
    justifyContent: "center",
  },
  sendText: { color: "#FFFFFF", fontSize: 14, fontWeight: "600", fontFamily: fonts.body },

  disabledWrap: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
    gap: 10,
  },
  disabledTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: colors.text,
    fontFamily: fonts.body,
    textAlign: "center",
  },
  disabledSub: {
    fontSize: 13,
    color: colors.muted,
    fontFamily: fonts.body,
    textAlign: "center",
    lineHeight: 18,
  },
});
