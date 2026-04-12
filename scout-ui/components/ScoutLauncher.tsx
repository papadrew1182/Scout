/**
 * Scout AI launcher — persistent entry point in the nav shell.
 * Opens a slide-up panel with chat, quick actions, and handoff cards.
 */

import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { useRouter } from "expo-router";
import { CURRENT_USER_ID } from "../lib/config";
import { sendChatMessage } from "../lib/api";
import { colors } from "../lib/styles";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  handoff?: { entity_type: string; route_hint: string; summary: string };
}

const QUICK_ACTIONS = [
  { label: "What does today look like?", message: "What does today look like?" },
  { label: "What's off track?", message: "What is off track this week?" },
  { label: "Add a task", message: "Help me add a task" },
  { label: "Add to grocery list", message: "Add something to the grocery list" },
  { label: "Plan meals for next week", message: "Help me plan meals for next week" },
  { label: "What do the kids still need to finish?", message: "What do the kids still need to finish today?" },
];

interface Props {
  visible: boolean;
  onClose: () => void;
  surface?: string;
  memberId?: string;
}

export function ScoutPanel({ visible, onClose, surface = "personal", memberId }: Props) {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const actorId = memberId ?? CURRENT_USER_ID;

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg: ChatMessage = { role: "user", content: text.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const result = await sendChatMessage(actorId, text.trim(), surface, conversationId);
      setConversationId(result.conversation_id);

      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: result.response,
        handoff: result.handoff ?? undefined,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Something went wrong. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  }, [actorId, surface, conversationId, loading]);

  if (!visible) return null;

  return (
    <View style={styles.overlay}>
      <View style={styles.panel}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Scout</Text>
          <Pressable onPress={onClose}>
            <Text style={styles.closeBtn}>Close</Text>
          </Pressable>
        </View>

        <ScrollView style={styles.messageArea} contentContainerStyle={styles.messageContent}>
          {messages.length === 0 && (
            <View style={styles.emptyState}>
              <Text style={styles.emptyTitle}>What can I help with?</Text>
              <View style={styles.quickActions}>
                {QUICK_ACTIONS.map((qa) => (
                  <Pressable
                    key={qa.label}
                    style={styles.quickAction}
                    onPress={() => sendMessage(qa.message)}
                  >
                    <Text style={styles.quickActionText}>{qa.label}</Text>
                  </Pressable>
                ))}
              </View>
            </View>
          )}

          {messages.map((msg, i) => (
            <View key={i} style={[styles.msgBubble, msg.role === "user" ? styles.userBubble : styles.assistantBubble]}>
              <Text style={[styles.msgText, msg.role === "user" && styles.userText]}>
                {msg.content}
              </Text>
              {msg.handoff && (
                <Pressable
                  style={styles.handoffBtn}
                  onPress={() => {
                    const hint = msg.handoff?.route_hint;
                    if (hint) {
                      onClose();
                      router.push(hint as any);
                    }
                  }}
                >
                  <Text style={styles.handoffText}>{msg.handoff.summary}</Text>
                </Pressable>
              )}
            </View>
          ))}

          {loading && (
            <View style={styles.loadingRow}>
              <ActivityIndicator size="small" color={colors.accent} />
              <Text style={styles.loadingText}>Thinking...</Text>
            </View>
          )}
        </ScrollView>

        <View style={styles.inputRow}>
          <TextInput
            style={styles.input}
            placeholder="Ask Scout anything..."
            placeholderTextColor={colors.textPlaceholder}
            value={input}
            onChangeText={setInput}
            onSubmitEditing={() => sendMessage(input)}
            returnKeyType="send"
          />
          <Pressable
            style={[styles.sendBtn, (!input.trim() || loading) && styles.sendBtnDisabled]}
            onPress={() => sendMessage(input)}
            disabled={!input.trim() || loading}
          >
            <Text style={styles.sendBtnText}>Send</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0,0,0,0.3)",
    justifyContent: "flex-end",
    zIndex: 100,
  },
  panel: {
    backgroundColor: colors.bg,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: "80%",
    minHeight: 400,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.cardBorder,
  },
  headerTitle: {
    color: colors.accent,
    fontSize: 18,
    fontWeight: "700",
  },
  closeBtn: { color: colors.textMuted, fontSize: 14, fontWeight: "600" },

  messageArea: { flex: 1 },
  messageContent: { padding: 16, paddingBottom: 8 },

  emptyState: { alignItems: "center", paddingTop: 20 },
  emptyTitle: {
    color: colors.textPrimary,
    fontSize: 18,
    fontWeight: "600",
    marginBottom: 16,
  },
  quickActions: { gap: 8, width: "100%" },
  quickAction: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 10,
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  quickActionText: { color: colors.textPrimary, fontSize: 14 },

  msgBubble: {
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
    maxWidth: "85%",
  },
  userBubble: {
    backgroundColor: colors.accent,
    alignSelf: "flex-end",
  },
  assistantBubble: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    alignSelf: "flex-start",
  },
  msgText: { color: colors.textPrimary, fontSize: 14, lineHeight: 20 },
  userText: { color: colors.buttonPrimaryText },

  handoffBtn: {
    backgroundColor: colors.accentBg,
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 12,
    marginTop: 8,
  },
  handoffText: { color: colors.accent, fontSize: 12, fontWeight: "600" },

  loadingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 8,
  },
  loadingText: { color: colors.textMuted, fontSize: 13 },

  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: colors.cardBorder,
    gap: 8,
  },
  input: {
    flex: 1,
    backgroundColor: colors.surfaceMuted,
    borderRadius: 10,
    padding: 12,
    color: colors.textPrimary,
    fontSize: 14,
  },
  sendBtn: {
    backgroundColor: colors.accent,
    borderRadius: 10,
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  sendBtnDisabled: { backgroundColor: colors.buttonDisabledBg },
  sendBtnText: { color: colors.buttonPrimaryText, fontSize: 14, fontWeight: "600" },
});
