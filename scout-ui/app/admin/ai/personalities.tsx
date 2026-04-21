/**
 * Sprint 04 Phase 2 - /admin/ai/personalities
 *
 * Adult-only surface for editing another family member's AI personality
 * config. Gated by `ai.edit_any_personality` (PARENT + PRIMARY_PARENT
 * per migration 048).
 *
 * Lists family members; tap a member to expand their config editor.
 * Preview text always comes from the backend's composed preamble —
 * no frontend prompt formatter.
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

import { fetchMembers, type FamilyMember } from "../../../lib/api";
import {
  getMemberPersonality,
  patchMemberPersonality,
  type PersonalityConfig,
  type PersonalityResponse,
  type Tone,
  type VocabularyLevel,
  type Formality,
  type Humor,
  type Proactivity,
  type Verbosity,
} from "../../../lib/ai-personality";
import { useHasPermission } from "../../../lib/permissions";
import { colors, fonts, shared } from "../../../lib/styles";

const TONES: Tone[] = ["warm", "direct", "playful", "professional"];
const VOCABS: VocabularyLevel[] = ["simple", "standard", "advanced"];
const FORMALITIES: Formality[] = ["casual", "neutral", "formal"];
const HUMORS: Humor[] = ["none", "light", "dry"];
const PROACTIVITIES: Proactivity[] = ["quiet", "balanced", "forthcoming"];
const VERBOSITIES: Verbosity[] = ["short", "standard", "detailed"];

export default function AdminPersonalities() {
  const router = useRouter();
  const canEdit = useHasPermission("ai.edit_any_personality");
  const [members, setMembers] = useState<FamilyMember[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<PersonalityResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  useEffect(() => {
    if (!canEdit) return;
    fetchMembers()
      .then(setMembers)
      .catch(() => setMembers([]));
  }, [canEdit]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    getMemberPersonality(selectedId)
      .then((d) => {
        setDetail(d);
        setSaveError(null);
      })
      .catch((e: unknown) => {
        setSaveError(e instanceof Error ? e.message : "Failed to load");
      })
      .finally(() => setDetailLoading(false));
  }, [selectedId]);

  const savePartial = async (patch: Partial<PersonalityConfig>) => {
    if (!selectedId) return;
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await patchMemberPersonality(selectedId, patch);
      setDetail(updated);
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (!canEdit) {
    return (
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.h1}>Not available</Text>
        <Text style={styles.blurb}>
          Editing other members' AI personality requires the
          <Text style={styles.code}> ai.edit_any_personality</Text> permission.
        </Text>
      </ScrollView>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <View style={styles.headerRow}>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <Text style={styles.backLink}>&larr; Admin</Text>
        </Pressable>
        <Text style={styles.h1}>AI personalities</Text>
      </View>

      <View style={shared.card}>
        <Text style={shared.cardTitle}>Family members</Text>
        {members === null ? (
          <ActivityIndicator color={colors.muted} style={{ marginTop: 6 }} />
        ) : (
          members.map((m) => (
            <Pressable
              key={m.id}
              style={[
                styles.memberRow,
                selectedId === m.id && styles.memberRowActive,
              ]}
              onPress={() =>
                setSelectedId((cur) => (cur === m.id ? null : m.id))
              }
              accessibilityRole="button"
              accessibilityLabel={`Edit ${m.first_name}'s personality`}
            >
              <Text style={styles.memberName}>
                {m.first_name} {m.last_name ?? ""}
              </Text>
              <Text style={styles.memberMeta}>{m.role}</Text>
            </Pressable>
          ))
        )}
      </View>

      {selectedId && (
        <View style={shared.card}>
          <Text style={shared.cardTitle}>Personality config</Text>
          {detailLoading || !detail ? (
            <ActivityIndicator color={colors.muted} style={{ marginTop: 6 }} />
          ) : (
            <>
              <EnumRow
                label="Tone"
                values={TONES}
                current={detail.resolved.tone}
                onSelect={(v) => savePartial({ tone: v })}
              />
              <EnumRow
                label="Vocabulary"
                values={VOCABS}
                current={detail.resolved.vocabulary_level}
                onSelect={(v) => savePartial({ vocabulary_level: v })}
              />
              <EnumRow
                label="Formality"
                values={FORMALITIES}
                current={detail.resolved.formality}
                onSelect={(v) => savePartial({ formality: v })}
              />
              <EnumRow
                label="Humor"
                values={HUMORS}
                current={detail.resolved.humor}
                onSelect={(v) => savePartial({ humor: v })}
              />
              <EnumRow
                label="Verbosity"
                values={VERBOSITIES}
                current={detail.resolved.verbosity}
                onSelect={(v) => savePartial({ verbosity: v })}
              />
              <EnumRow
                label="Proactivity"
                values={PROACTIVITIES}
                current={detail.resolved.proactivity}
                onSelect={(v) => savePartial({ proactivity: v })}
              />
              <Text style={styles.proactivityNote}>
                Proactivity takes effect when proactive nudges ship in Sprint 05.
              </Text>

              <FreeTextRow
                label="Notes to Scout"
                limit={500}
                initialValue={detail.resolved.notes_to_self}
                onSave={(v) => savePartial({ notes_to_self: v })}
              />
              <FreeTextRow
                label="Role context"
                limit={200}
                initialValue={detail.resolved.role_hints}
                onSave={(v) => savePartial({ role_hints: v })}
              />

              {saving && (
                <Text style={styles.savingText}>Saving…</Text>
              )}
              {saveError && (
                <Text style={styles.errorText}>{saveError}</Text>
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
                  <Text style={styles.previewText}>{detail.preamble}</Text>
                </View>
              )}
            </>
          )}
        </View>
      )}
    </ScrollView>
  );
}

function EnumRow<T extends string>({
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
            style={[
              styles.chip,
              current === v && styles.chipActive,
            ]}
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

function FreeTextRow({
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

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  headerRow: { gap: 6 },
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
  blurb: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 20,
    fontFamily: fonts.body,
  },
  code: {
    fontFamily: "monospace",
    color: colors.text,
  },
  memberRow: {
    paddingVertical: 10,
    paddingHorizontal: 10,
    borderRadius: 8,
    flexDirection: "row",
    justifyContent: "space-between",
  },
  memberRowActive: {
    backgroundColor: "#eef2ff",
  },
  memberName: {
    color: colors.text,
    fontSize: 14,
    fontFamily: fonts.body,
  },
  memberMeta: {
    color: colors.muted,
    fontSize: 12,
    fontFamily: fonts.body,
  },
  enumRow: { marginTop: 10 },
  enumLabel: {
    fontSize: 13,
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
  errorText: {
    color: "#dc2626",
    fontSize: 13,
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
