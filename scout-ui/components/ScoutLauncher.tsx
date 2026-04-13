/**
 * Scout AI launcher — persistent entry point in the nav shell.
 * Opens a slide-up panel with chat, quick actions, handoff cards,
 * a confirm/cancel affordance for confirmation-gated tools, and a
 * disabled-state fallback when the backend reports ai_available=false.
 */

import { useCallback, useEffect, useState } from "react";
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
import {
  sendChatMessage,
  fetchReady,
  type AIHandoff,
  type AIPendingConfirmation,
} from "../lib/api";
import { colors } from "../lib/styles";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  handoff?: AIHandoff;
  pendingConfirmation?: AIPendingConfirmation;
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

type ReadyState = "checking" | "ok" | "disabled" | "error";

export function ScoutPanel({ visible, onClose, surface = "personal", memberId }: Props) {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [readyState, setReadyState] = useState<ReadyState>("checking");
  const [readyReason, setReadyReason] = useState<string | null>(null);

  // Probe backend /ready whenever the panel becomes visible so we never mount
  // the chat UI on top of a known-broken AI path. Cheap and cached-by-open.
  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    setReadyState("checking");
    setReadyReason(null);
    fetchReady()
      .then((r) => {
        if (cancelled) return;
        if (r.ai_available) {
          setReadyState("ok");
        } else {
          setReadyState("disabled");
          setReadyReason(r.reason ?? null);
        }
      })
      .catch((e) => {
        if (cancelled) return;
        setReadyState("error");
        setReadyReason((e as Error)?.message ?? "unknown");
      });
    return () => {
      cancelled = true;
    };
  }, [visible]);

  const applyResult = useCallback((result: any) => {
    setConversationId(result.conversation_id);
    const assistantMsg: ChatMessage = {
      role: "assistant",
      content: result.response,
      handoff: result.handoff ?? undefined,
      pendingConfirmation: result.pending_confirmation ?? undefined,
    };
    setMessages((prev) => [...prev, assistantMsg]);
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || loading) return;
      const userMsg: ChatMessage = { role: "user", content: text.trim() };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setLoading(true);
      try {
        const result = await sendChatMessage(text.trim(), surface, conversationId);
        applyResult(result);
      } catch (e) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "Something went wrong. Please try again." },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [surface, conversationId, loading, applyResult],
  );

  const confirmPendingTool = useCallback(
    async (pending: AIPendingConfirmation) => {
      if (loading) return;
      setLoading(true);
      try {
        const result = await sendChatMessage("", {
          surface,
          conversationId,
          confirmTool: { tool_name: pending.tool_name, arguments: pending.arguments },
        });
        applyResult(result);
      } catch (e) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "Confirmation failed. Please try again." },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [surface, conversationId, loading, applyResult],
  );

  const cancelPendingTool = useCallback(() => {
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "Cancelled. Let me know if you want something else." },
    ]);
  }, []);

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

        {readyState === "checking" && (
          <View style={styles.stateArea}>
            <ActivityIndicator size="small" color={colors.accent} />
            <Text style={styles.stateText}>Checking Scout AI availability…</Text>
          </View>
        )}

        {(readyState === "disabled" || readyState === "error") && (
          <View style={styles.stateArea}>
            <Text style={styles.disabledTitle}>Scout AI is unavailable right now</Text>
            <Text style={styles.stateText}>
              {readyState === "disabled"
                ? "The backend reports ai_available=false. Try again later, or ask a parent to check the Anthropic API key."
                : "We couldn't reach the backend readiness endpoint."}
            </Text>
            {readyReason && (
              <Text style={styles.stateReason}>({readyReason})</Text>
            )}
          </View>
        )}

        {readyState === "ok" && (
          <>
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
                <View
                  key={i}
                  style={[
                    styles.msgBubble,
                    msg.role === "user" ? styles.userBubble : styles.assistantBubble,
                  ]}
                >
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

                  {msg.pendingConfirmation && (
                    <View style={styles.confirmCard}>
                      <Text style={styles.confirmTitle}>Confirm this action</Text>
                      <Text style={styles.confirmTool}>
                        Tool: {msg.pendingConfirmation.tool_name}
                      </Text>
                      <Text style={styles.confirmBody}>
                        {msg.pendingConfirmation.message}
                      </Text>
                      <View style={styles.confirmRow}>
                        <Pressable
                          style={styles.confirmYes}
                          onPress={() => confirmPendingTool(msg.pendingConfirmation!)}
                          disabled={loading}
                        >
                          <Text style={styles.confirmYesText}>Confirm</Text>
                        </Pressable>
                        <Pressable
                          style={styles.confirmNo}
                          onPress={cancelPendingTool}
                          disabled={loading}
                        >
                          <Text style={styles.confirmNoText}>Cancel</Text>
                        </Pressable>
                      </View>
                    </View>
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
          </>
        )}
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

  stateArea: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
    gap: 10,
  },
  stateText: {
    color: colors.textMuted,
    fontSize: 14,
    textAlign: "center",
  },
  stateReason: {
    color: colors.textMuted,
    fontSize: 12,
    fontStyle: "italic",
    textAlign: "center",
  },
  disabledTitle: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: "700",
    textAlign: "center",
  },

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

  confirmCard: {
    marginTop: 10,
    padding: 10,
    borderRadius: 10,
    backgroundColor: colors.surfaceMuted,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    gap: 6,
  },
  confirmTitle: {
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: "700",
  },
  confirmTool: {
    color: colors.textMuted,
    fontSize: 12,
    fontFamily: "monospace",
  },
  confirmBody: { color: colors.textPrimary, fontSize: 13, lineHeight: 18 },
  confirmRow: {
    flexDirection: "row",
    gap: 8,
    marginTop: 6,
  },
  confirmYes: {
    backgroundColor: colors.accent,
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 14,
  },
  confirmYesText: { color: colors.buttonPrimaryText, fontSize: 13, fontWeight: "700" },
  confirmNo: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 14,
  },
  confirmNoText: { color: colors.textPrimary, fontSize: 13, fontWeight: "600" },

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
