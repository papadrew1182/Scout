import { useEffect, useRef, useState } from "react";
import { Image, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { colors, fonts } from "../lib/styles";
import { SAMPLE_THREAD, QUICK_ACTIONS_BY_SURFACE, type ScoutSurface } from "../lib/mockScout";
import { fetchReady, fetchResumableConversation, sendChatMessageStream, uploadAttachment } from "../lib/api";
import { fetchConversationMessagesPaginated } from "../lib/ai-conversations";

interface Turn {
  role: "user" | "assistant";
  content: string;
  attachmentUri?: string; // local preview URI for images the user sent
}

interface PendingAttachment {
  uri: string;   // object URL for local preview
  blob: Blob;
  name: string;
}

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
  const [attachment, setAttachment] = useState<PendingAttachment | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  // Sprint 04 Phase 1: track conversation id so turns continue the thread
  // across panel opens. Null on a fresh session; set from resume hydration
  // or from the orchestrator's "done" event on the first turn.
  const [conversationId, setConversationId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
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

  // Sprint 04 Phase 1: resume the most recent in-flight conversation
  // when the sheet opens. Uses the existing /resumable endpoint (30-min
  // freshness + pending-confirmation / moderation safety gates). If
  // none is eligible, the sheet stays in its existing blank / sample
  // state.
  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    fetchResumableConversation("personal")
      .then(async (resume) => {
        if (cancelled || !resume.conversation_id) return;
        setConversationId(resume.conversation_id);
        try {
          const page = await fetchConversationMessagesPaginated(
            resume.conversation_id,
            { limit: 50 },
          );
          if (cancelled) return;
          const hydrated: Turn[] = page.messages
            .filter((m) => m.role === "user" || m.role === "assistant")
            .map((m) => ({
              role: m.role as "user" | "assistant",
              content: m.content ?? "",
            }));
          if (hydrated.length > 0) {
            setThread(hydrated);
          }
        } catch {
          // Resume hydration failed — stay on current thread state
        }
      })
      .catch(() => {
        // No resumable conversation; blank-state UX
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

  const handleFileSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const uri = URL.createObjectURL(file);
    setAttachment({ uri, blob: file, name: file.name });
    setUploadError(null);
    // Reset so the same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed && !attachment) return;
    setUploadError(null);

    // Snapshot and clear attachment before async work
    const pendingAttachment = attachment;
    setAttachment(null);

    let attachPath: string | undefined;
    let localUri: string | undefined;

    if (pendingAttachment) {
      localUri = pendingAttachment.uri;
      try {
        const result = await uploadAttachment(pendingAttachment.blob, pendingAttachment.name);
        attachPath = result.path;
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Upload failed";
        setUploadError(msg);
        setAttachment(pendingAttachment); // restore so user can retry
        return;
      }
    }

    setThread((prev) => [...prev, { role: "user", content: trimmed, attachmentUri: localUri }]);
    setValue("");
    let accumulated = "";
    setThread((prev) => [...prev, { role: "assistant", content: "..." }]);
    await sendChatMessageStream(
      trimmed || "What do you see in this image?",
      { surface, attachmentPath: attachPath, conversationId: conversationId ?? undefined },
      {
        onEvent: (event) => {
          if (event.type === "text") {
            accumulated += event.text;
            setThread((prev) => {
              const copy = [...prev];
              copy[copy.length - 1] = { role: "assistant", content: accumulated };
              return copy;
            });
          } else if (event.type === "done") {
            // Capture the backend's conversation id so subsequent turns
            // continue the same thread.
            if (event.conversation_id && !conversationId) {
              setConversationId(event.conversation_id);
            }
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
            {/* Hidden file input for attachment picking (web) */}
            {/* @ts-ignore — HTMLInputElement ref on web */}
            <input
              type="file"
              accept="image/*,application/pdf"
              style={{ display: "none" }}
              ref={fileInputRef as any}
              onChange={handleFileSelected as any}
            />

            <ScrollView style={{ flex: 1 }} contentContainerStyle={styles.threadContent}>
              {thread.map((t, i) => (
                <View key={i} style={[styles.bubble, t.role === "user" ? styles.userBubble : styles.assistantBubble]}>
                  {t.attachmentUri ? (
                    <Image
                      source={{ uri: t.attachmentUri }}
                      style={styles.attachmentThumb}
                      accessibilityLabel="Attached image"
                    />
                  ) : null}
                  {t.content ? (
                    <Text style={t.role === "user" ? styles.userText : styles.assistantText}>{t.content}</Text>
                  ) : null}
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

            {/* Attachment preview strip */}
            {attachment ? (
              <View style={styles.attachPreviewRow}>
                <Image source={{ uri: attachment.uri }} style={styles.attachPreviewThumb} accessibilityLabel="Pending attachment" />
                <Text style={styles.attachPreviewName} numberOfLines={1}>{attachment.name}</Text>
                <Pressable onPress={() => setAttachment(null)} style={styles.attachRemoveBtn} accessibilityLabel="Remove attachment">
                  <Text style={styles.attachRemoveText}>×</Text>
                </Pressable>
              </View>
            ) : null}

            {uploadError ? (
              <View style={styles.uploadErrorRow}>
                <Text style={styles.uploadErrorText}>{uploadError}</Text>
              </View>
            ) : null}

            <View style={styles.inputRow}>
              <Pressable
                style={styles.clipBtn}
                onPress={() => (fileInputRef.current as any)?.click()}
                accessibilityRole="button"
                accessibilityLabel="Attach image"
              >
                <Text style={styles.clipIcon}>📎</Text>
              </Pressable>
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
    alignItems: "center",
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
    height: 40,
  },
  sendText: { color: "#FFFFFF", fontSize: 14, fontWeight: "600", fontFamily: fonts.body },

  // Attachment UI
  clipBtn: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  clipIcon: { fontSize: 16 },
  attachPreviewRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 16,
    paddingBottom: 6,
    backgroundColor: colors.card,
  },
  attachPreviewThumb: {
    width: 48,
    height: 48,
    borderRadius: 8,
    backgroundColor: colors.border,
  },
  attachPreviewName: {
    flex: 1,
    fontSize: 12,
    color: colors.muted,
    fontFamily: fonts.body,
  },
  attachRemoveBtn: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  attachRemoveText: { fontSize: 14, color: colors.text, lineHeight: 20 },
  uploadErrorRow: {
    paddingHorizontal: 16,
    paddingBottom: 4,
    backgroundColor: colors.card,
  },
  uploadErrorText: { fontSize: 11, color: "#e53e3e", fontFamily: fonts.body },
  attachmentThumb: {
    width: "100%",
    height: 160,
    borderRadius: 8,
    marginBottom: 6,
    backgroundColor: colors.border,
  } as any,

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
