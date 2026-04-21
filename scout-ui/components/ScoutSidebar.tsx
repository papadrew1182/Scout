import { useEffect, useRef, useState } from "react";
import { Image, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { colors, fonts } from "../lib/styles";
import {
  QUICK_ACTIONS_BY_SURFACE,
  type ScoutSurface,
} from "../lib/mockScout";
import { fetchReady, fetchResumableConversation, sendChatMessageStream, uploadAttachment } from "../lib/api";
import { fetchConversationMessagesPaginated } from "../lib/ai-conversations";

interface Turn {
  role: "user" | "assistant";
  content: string;
  attachmentUri?: string;
}

interface PendingAttachment {
  uri: string;
  blob: Blob;
  name: string;
}

interface Props {
  surface: ScoutSurface;
}

export function ScoutSidebar({ surface }: Props) {
  // Starts blank; hydrates from /resumable on mount when eligible.
  const [thread, setThread] = useState<Turn[]>([]);
  const [value, setValue] = useState("");
  const [readyState, setReadyState] = useState<"checking" | "ok" | "disabled">("checking");
  const [attachment, setAttachment] = useState<PendingAttachment | null>(null);
  // Sprint 04 Phase 1: track conversation id for cross-turn continuity.
  const [conversationId, setConversationId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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

  // Sprint 04 Phase 1: resume most recent in-flight conversation on
  // mount. Silently no-ops if none is eligible.
  useEffect(() => {
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
          /* hydration failed — keep blank / sample state */
        }
      })
      .catch(() => { /* no resumable thread */ });
    return () => { cancelled = true; };
  }, []);

  const handleFileSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setAttachment({ uri: URL.createObjectURL(file), blob: file, name: file.name });
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed && !attachment) return;

    const pendingAttachment = attachment;
    setAttachment(null);

    let attachPath: string | undefined;
    let localUri: string | undefined;

    if (pendingAttachment) {
      localUri = pendingAttachment.uri;
      try {
        const result = await uploadAttachment(pendingAttachment.blob, pendingAttachment.name);
        attachPath = result.path;
      } catch {
        setAttachment(pendingAttachment); // restore on failure
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
          {/* Hidden file input — web only. Native renders null because
              RN has no `input` component; file picking on iOS/Android
              will move to expo-image-picker / expo-document-picker in
              a separate feature. */}
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

          <ScrollView style={styles.thread} contentContainerStyle={{ gap: 4 }}>
            {thread.map((t, i) => (
              <View key={i} style={t.role === "user" ? styles.userBubble : styles.assistantBubble}>
                {t.attachmentUri ? (
                  <Image
                    source={{ uri: t.attachmentUri }}
                    style={styles.attachThumb}
                    accessibilityLabel="Attached image"
                  />
                ) : null}
                {t.content ? (
                  <Text style={t.role === "user" ? styles.userText : styles.assistantText}>{t.content}</Text>
                ) : null}
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

          {/* Compact attachment preview */}
          {attachment ? (
            <View style={styles.attachPreviewRow}>
              <Image source={{ uri: attachment.uri }} style={styles.attachPreviewThumb} accessibilityLabel="Pending attachment" />
              <Pressable onPress={() => setAttachment(null)} style={styles.attachRemove} accessibilityLabel="Remove attachment">
                <Text style={styles.attachRemoveText}>×</Text>
              </Pressable>
            </View>
          ) : null}

          <View style={styles.miniInput}>
            <Pressable
              onPress={() => (fileInputRef.current as any)?.click()}
              style={styles.clipBtn}
              accessibilityLabel="Attach image"
            >
              <Text style={styles.clipIcon}>📎</Text>
            </Pressable>
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

  // Attachment UI (compact sidebar variant)
  clipBtn: {
    width: 18,
    height: 18,
    alignItems: "center",
    justifyContent: "center",
  },
  clipIcon: { fontSize: 11 },
  attachThumb: {
    width: "100%",
    height: 60,
    borderRadius: 4,
    marginBottom: 3,
    backgroundColor: colors.border,
  } as any,
  attachPreviewRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    marginTop: 6,
  },
  attachPreviewThumb: {
    width: 36,
    height: 36,
    borderRadius: 4,
    backgroundColor: colors.border,
  },
  attachRemove: {
    width: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  attachRemoveText: { fontSize: 11, color: colors.text, lineHeight: 16 },

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
