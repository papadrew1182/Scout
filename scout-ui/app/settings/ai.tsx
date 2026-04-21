/**
 * Sprint 04 Phase 1 - /settings/ai
 *
 * Per-user AI settings. Phase 1 ships the Conversation history section
 * (counts + archive-older-than control). Phase 2 will add the
 * Personality section on the same page.
 */

import { useEffect, useState } from "react";
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
  archiveOlderConversations,
  getConversationStats,
  listMyConversations,
  patchConversation,
  type Conversation,
  type ConversationStats,
} from "../../lib/ai-conversations";
import {
  getMyPersonality,
  patchMyPersonality,
  type PersonalityConfig,
  type PersonalityResponse,
  type Tone,
  type VocabularyLevel,
  type Formality,
  type Humor,
  type Proactivity,
  type Verbosity,
} from "../../lib/ai-personality";
import { colors, fonts, shared } from "../../lib/styles";

const TONES: Tone[] = ["warm", "direct", "playful", "professional"];
const VOCABS: VocabularyLevel[] = ["simple", "standard", "advanced"];
const FORMALITIES: Formality[] = ["casual", "neutral", "formal"];
const HUMORS: Humor[] = ["none", "light", "dry"];
const PROACTIVITIES: Proactivity[] = ["quiet", "balanced", "forthcoming"];
const VERBOSITIES: Verbosity[] = ["short", "standard", "detailed"];

function formatRelative(iso: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diffMin = Math.round((now - then) / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  if (diffDay < 30) return `${diffDay}d ago`;
  const diffMo = Math.round(diffDay / 30);
  return `${diffMo}mo ago`;
}

const ARCHIVE_PRESETS = [
  { label: "7 days", days: 7 },
  { label: "30 days", days: 30 },
  { label: "90 days", days: 90 },
];

export default function AISettings() {
  const router = useRouter();
  const [stats, setStats] = useState<ConversationStats | null>(null);
  const [conversations, setConversations] = useState<Conversation[] | null>(null);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [rowBusy, setRowBusy] = useState<string | null>(null);
  const [personality, setPersonality] = useState<PersonalityResponse | null>(null);
  const [personalitySaving, setPersonalitySaving] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [archiving, setArchiving] = useState<number | null>(null);
  const [archiveResult, setArchiveResult] = useState<
    { days: number; archived: number } | null
  >(null);

  const load = async () => {
    try {
      const [s, convs] = await Promise.all([
        getConversationStats(),
        listMyConversations({ includeArchived, limit: 20, pinnedFirst: true }),
      ]);
      setStats(s);
      setConversations(convs);
      setLoadError(null);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load stats";
      setLoadError(msg);
    }
  };

  useEffect(() => {
    load();
  }, [includeArchived]);

  useEffect(() => {
    getMyPersonality()
      .then(setPersonality)
      .catch(() => setPersonality(null));
  }, []);

  const savePersonalityPartial = async (patch: Partial<PersonalityConfig>) => {
    setPersonalitySaving(true);
    try {
      const updated = await patchMyPersonality(patch);
      setPersonality(updated);
    } finally {
      setPersonalitySaving(false);
    }
  };

  const togglePin = async (c: Conversation) => {
    setRowBusy(c.id);
    try {
      await patchConversation(c.id, { is_pinned: !c.is_pinned });
      await load();
    } finally {
      setRowBusy(null);
    }
  };

  const toggleArchive = async (c: Conversation) => {
    setRowBusy(c.id);
    try {
      await patchConversation(c.id, {
        status: c.status === "archived" ? "active" : "archived",
      });
      await load();
    } finally {
      setRowBusy(null);
    }
  };

  const rename = async (c: Conversation) => {
    // Web-only prompt; on native builds the rename control is hidden.
    const next =
      typeof window !== "undefined" && typeof window.prompt === "function"
        ? window.prompt("New title", c.title ?? "")
        : null;
    if (next === null) return;
    const trimmed = next.trim();
    if (!trimmed || trimmed === c.title) return;
    setRowBusy(c.id);
    try {
      await patchConversation(c.id, { title: trimmed });
      await load();
    } finally {
      setRowBusy(null);
    }
  };

  const handleArchive = async (days: number) => {
    setArchiving(days);
    setArchiveResult(null);
    try {
      const r = await archiveOlderConversations(days);
      setArchiveResult({ days, archived: r.archived_count });
      await load();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Archive failed";
      setLoadError(msg);
    } finally {
      setArchiving(null);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Pressable
          onPress={() => router.back()}
          hitSlop={12}
          accessibilityRole="button"
          accessibilityLabel="Back to settings"
        >
          <Text style={styles.backLink}>&larr; Settings</Text>
        </Pressable>
        <Text style={styles.h1}>AI &amp; Conversations</Text>
      </View>

      <View style={shared.card}>
        <Text style={shared.cardTitle}>Conversation history</Text>
        <Text style={styles.sectionBlurb}>
          Your Scout chat threads are saved across panel opens so you can pick
          up where you left off. Archiving hides older threads from the
          default list. It does not delete data.
        </Text>

        {loadError && (
          <Text style={styles.errorText}>{loadError}</Text>
        )}

        {stats === null && !loadError && (
          <ActivityIndicator color={colors.muted} style={{ marginTop: 8 }} />
        )}

        {stats !== null && (
          <View style={styles.statsRow}>
            <StatCell label="Total" value={stats.total_count} />
            <StatCell label="Active" value={stats.active_count} />
            <StatCell label="Archived" value={stats.archived_count} />
          </View>
        )}

        <Text style={styles.subLabel}>Archive older conversations</Text>
        <Text style={styles.helperText}>
          Archives older conversations for this member. Does not delete data.
        </Text>
        <View style={styles.presetRow}>
          {ARCHIVE_PRESETS.map((p) => (
            <Pressable
              key={p.days}
              style={[
                styles.presetBtn,
                archiving === p.days && styles.presetBtnBusy,
              ]}
              onPress={() => handleArchive(p.days)}
              disabled={archiving !== null}
              accessibilityRole="button"
              accessibilityLabel={`Archive conversations older than ${p.label}`}
            >
              {archiving === p.days ? (
                <ActivityIndicator color={colors.text} size="small" />
              ) : (
                <Text style={styles.presetBtnText}>
                  Older than {p.label}
                </Text>
              )}
            </Pressable>
          ))}
        </View>

        {archiveResult && (
          <Text style={styles.successText}>
            Archived {archiveResult.archived}{" "}
            {archiveResult.archived === 1 ? "conversation" : "conversations"}{" "}
            older than {archiveResult.days} days.
          </Text>
        )}
      </View>

      <View style={shared.card}>
        <View style={styles.listHeader}>
          <Text style={shared.cardTitle}>Your conversations</Text>
          <Pressable
            onPress={() => setIncludeArchived((v) => !v)}
            accessibilityRole="button"
            accessibilityLabel={
              includeArchived ? "Hide archived" : "Show archived"
            }
            style={styles.toggleBtn}
          >
            <Text style={styles.toggleBtnText}>
              {includeArchived ? "Hide archived" : "Show archived"}
            </Text>
          </Pressable>
        </View>

        {conversations === null ? (
          <ActivityIndicator color={colors.muted} style={{ marginTop: 8 }} />
        ) : conversations.length === 0 ? (
          <Text style={styles.emptyText}>
            No conversations yet. Open Scout and send a message to start one.
          </Text>
        ) : (
          conversations.map((c) => (
            <View key={c.id} style={styles.row}>
              <View style={styles.rowMain}>
                <Text style={styles.rowTitle} numberOfLines={1}>
                  {c.is_pinned ? "⭐ " : ""}
                  {c.title ?? "New conversation"}
                </Text>
                <Text style={styles.rowMeta}>
                  {c.status === "archived" ? "Archived · " : ""}
                  {formatRelative(c.last_active_at)}
                </Text>
              </View>
              <View style={styles.rowActions}>
                <Pressable
                  onPress={() => rename(c)}
                  disabled={rowBusy === c.id}
                  style={styles.rowBtn}
                  accessibilityRole="button"
                  accessibilityLabel={`Rename ${c.title ?? "conversation"}`}
                >
                  <Text style={styles.rowBtnText}>Rename</Text>
                </Pressable>
                <Pressable
                  onPress={() => togglePin(c)}
                  disabled={rowBusy === c.id}
                  style={styles.rowBtn}
                  accessibilityRole="button"
                  accessibilityLabel={c.is_pinned ? "Unpin" : "Pin"}
                >
                  <Text style={styles.rowBtnText}>
                    {c.is_pinned ? "Unpin" : "Pin"}
                  </Text>
                </Pressable>
                <Pressable
                  onPress={() => toggleArchive(c)}
                  disabled={rowBusy === c.id}
                  style={styles.rowBtn}
                  accessibilityRole="button"
                  accessibilityLabel={
                    c.status === "archived" ? "Unarchive" : "Archive"
                  }
                >
                  <Text style={styles.rowBtnText}>
                    {c.status === "archived" ? "Unarchive" : "Archive"}
                  </Text>
                </Pressable>
              </View>
            </View>
          ))
        )}
      </View>

      <View style={shared.card}>
        <Text style={shared.cardTitle}>Personality</Text>
        <Text style={styles.sectionBlurb}>
          Tune Scout's voice for your own conversations. Changes take effect
          on the next chat turn.
        </Text>

        {personality === null ? (
          <ActivityIndicator color={colors.muted} style={{ marginTop: 6 }} />
        ) : (
          <>
            <PersonalityChips
              label="Tone"
              values={TONES}
              current={personality.resolved.tone}
              onSelect={(v) => savePersonalityPartial({ tone: v })}
            />
            <PersonalityChips
              label="Vocabulary"
              values={VOCABS}
              current={personality.resolved.vocabulary_level}
              onSelect={(v) => savePersonalityPartial({ vocabulary_level: v })}
            />
            <PersonalityChips
              label="Formality"
              values={FORMALITIES}
              current={personality.resolved.formality}
              onSelect={(v) => savePersonalityPartial({ formality: v })}
            />
            <PersonalityChips
              label="Humor"
              values={HUMORS}
              current={personality.resolved.humor}
              onSelect={(v) => savePersonalityPartial({ humor: v })}
            />
            <PersonalityChips
              label="Verbosity"
              values={VERBOSITIES}
              current={personality.resolved.verbosity}
              onSelect={(v) => savePersonalityPartial({ verbosity: v })}
            />
            <PersonalityChips
              label="Proactivity"
              values={PROACTIVITIES}
              current={personality.resolved.proactivity}
              onSelect={(v) => savePersonalityPartial({ proactivity: v })}
            />
            <Text style={styles.proactivityNote}>
              Proactivity takes effect when proactive nudges ship in Sprint 05.
            </Text>

            <PersonalityFreeText
              label="Notes to Scout"
              limit={500}
              initialValue={personality.resolved.notes_to_self}
              onSave={(v) => savePersonalityPartial({ notes_to_self: v })}
            />
            <PersonalityFreeText
              label="Role context"
              limit={200}
              initialValue={personality.resolved.role_hints}
              onSave={(v) => savePersonalityPartial({ role_hints: v })}
            />

            {personalitySaving && (
              <Text style={styles.savingText}>Saving…</Text>
            )}

            <Pressable
              onPress={() => setPreviewOpen((v) => !v)}
              style={styles.previewBtn}
              accessibilityRole="button"
              accessibilityLabel="Toggle preamble preview"
            >
              <Text style={styles.previewBtnText}>
                {previewOpen ? "Hide preview" : "Preview preamble"}
              </Text>
            </Pressable>

            {previewOpen && (
              <View style={styles.previewBox}>
                <Text style={styles.previewText}>{personality.preamble}</Text>
              </View>
            )}
          </>
        )}
      </View>
    </ScrollView>
  );
}

function PersonalityChips<T extends string>({
  label,
  values,
  current,
  onSelect,
}: {
  label: string;
  values: readonly T[];
  current: T;
  onSelect: (v: T) => void;
}) {
  return (
    <View style={styles.enumRow}>
      <Text style={styles.enumLabel}>{label}</Text>
      <View style={styles.enumChips}>
        {values.map((v) => (
          <Pressable
            key={v}
            onPress={() => onSelect(v)}
            style={[styles.chip, current === v && styles.chipActive]}
            accessibilityRole="button"
            accessibilityLabel={`Set ${label} to ${v}`}
          >
            <Text
              style={[
                styles.chipText,
                current === v && styles.chipTextActive,
              ]}
            >
              {v}
            </Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function PersonalityFreeText({
  label,
  limit,
  initialValue,
  onSave,
}: {
  label: string;
  limit: number;
  initialValue: string;
  onSave: (v: string) => void;
}) {
  const [value, setValue] = useState(initialValue);
  useEffect(() => {
    setValue(initialValue);
  }, [initialValue]);
  return (
    <View style={styles.freeText}>
      <View style={styles.freeTextHeader}>
        <Text style={styles.enumLabel}>{label}</Text>
        <Text style={styles.counter}>
          {value.length}/{limit}
        </Text>
      </View>
      <TextInput
        style={styles.textInput}
        multiline
        value={value}
        maxLength={limit}
        onChangeText={setValue}
        onBlur={() => {
          if (value !== initialValue) onSave(value);
        }}
        accessibilityLabel={label}
      />
    </View>
  );
}

function StatCell({ label, value }: { label: string; value: number }) {
  return (
    <View style={styles.statCell}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  header: { gap: 6 },
  backLink: {
    color: colors.muted,
    fontSize: 14,
    fontFamily: fonts.body,
  },
  h1: {
    fontSize: 22,
    fontWeight: "600",
    color: colors.text,
    fontFamily: fonts.body,
  },
  sectionBlurb: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
    marginTop: 6,
    marginBottom: 12,
    fontFamily: fonts.body,
  },
  statsRow: { flexDirection: "row", gap: 16, marginVertical: 8 },
  statCell: { flex: 1 },
  statValue: {
    fontSize: 22,
    fontWeight: "600",
    color: colors.text,
    fontFamily: fonts.body,
  },
  statLabel: {
    fontSize: 12,
    color: colors.muted,
    fontFamily: fonts.body,
    marginTop: 2,
  },
  subLabel: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.text,
    fontFamily: fonts.body,
    marginTop: 16,
  },
  helperText: {
    color: colors.muted,
    fontSize: 12,
    marginTop: 4,
    marginBottom: 10,
    fontFamily: fonts.body,
  },
  presetRow: { flexDirection: "row", gap: 8, flexWrap: "wrap" },
  presetBtn: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 8,
    backgroundColor: "#f3f4f6",
    minWidth: 120,
    alignItems: "center",
  },
  presetBtnBusy: { opacity: 0.6 },
  presetBtnText: {
    color: colors.text,
    fontSize: 14,
    fontFamily: fonts.body,
  },
  successText: {
    color: "#16a34a",
    fontSize: 13,
    marginTop: 10,
    fontFamily: fonts.body,
  },
  errorText: {
    color: "#dc2626",
    fontSize: 13,
    marginTop: 8,
    fontFamily: fonts.body,
  },
  listHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  toggleBtn: {
    paddingVertical: 4,
    paddingHorizontal: 8,
  },
  toggleBtnText: {
    color: colors.muted,
    fontSize: 12,
    fontFamily: fonts.body,
  },
  emptyText: {
    color: colors.muted,
    fontSize: 13,
    paddingVertical: 10,
    fontFamily: fonts.body,
  },
  row: {
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#e5e7eb",
    gap: 6,
  },
  rowMain: { gap: 2 },
  rowTitle: {
    color: colors.text,
    fontSize: 14,
    fontFamily: fonts.body,
  },
  rowMeta: {
    color: colors.muted,
    fontSize: 12,
    fontFamily: fonts.body,
  },
  rowActions: {
    flexDirection: "row",
    gap: 8,
    flexWrap: "wrap",
    marginTop: 4,
  },
  rowBtn: {
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: 6,
    backgroundColor: "#f3f4f6",
  },
  rowBtnText: {
    color: colors.text,
    fontSize: 12,
    fontFamily: fonts.body,
  },
  enumRow: { marginTop: 10 },
  enumLabel: {
    fontSize: 12,
    color: colors.muted,
    fontFamily: fonts.body,
    marginBottom: 4,
    textTransform: "uppercase",
    letterSpacing: 0.3,
  },
  enumChips: { flexDirection: "row", gap: 6, flexWrap: "wrap" },
  chip: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 14,
    backgroundColor: "#f3f4f6",
  },
  chipActive: { backgroundColor: "#1f2937" },
  chipText: { color: colors.text, fontSize: 12, fontFamily: fonts.body },
  chipTextActive: { color: "#ffffff" },
  proactivityNote: {
    color: colors.muted,
    fontSize: 11,
    fontFamily: fonts.body,
    marginTop: 2,
  },
  freeText: { marginTop: 14 },
  freeTextHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  counter: {
    fontSize: 11,
    color: colors.muted,
    fontFamily: fonts.body,
  },
  textInput: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 8,
    padding: 8,
    minHeight: 60,
    fontSize: 13,
    color: colors.text,
    fontFamily: fonts.body,
  },
  savingText: {
    color: colors.muted,
    fontSize: 12,
    fontFamily: fonts.body,
    marginTop: 8,
  },
  previewBtn: {
    marginTop: 14,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 8,
    backgroundColor: "#f3f4f6",
    alignSelf: "flex-start",
  },
  previewBtnText: {
    fontSize: 13,
    color: colors.text,
    fontFamily: fonts.body,
  },
  previewBox: {
    marginTop: 10,
    padding: 12,
    borderRadius: 8,
    backgroundColor: "#f9fafb",
    borderWidth: 1,
    borderColor: "#e5e7eb",
  },
  previewText: {
    fontFamily: "monospace",
    fontSize: 12,
    color: colors.text,
    lineHeight: 18,
  },
});
