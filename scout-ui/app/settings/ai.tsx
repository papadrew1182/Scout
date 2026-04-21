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
  View,
} from "react-native";
import { useRouter } from "expo-router";

import {
  archiveOlderConversations,
  getConversationStats,
  type ConversationStats,
} from "../../lib/ai-conversations";
import { colors, fonts, shared } from "../../lib/styles";

const ARCHIVE_PRESETS = [
  { label: "7 days", days: 7 },
  { label: "30 days", days: 30 },
  { label: "90 days", days: 90 },
];

export default function AISettings() {
  const router = useRouter();
  const [stats, setStats] = useState<ConversationStats | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [archiving, setArchiving] = useState<number | null>(null);
  const [archiveResult, setArchiveResult] = useState<
    { days: number; archived: number } | null
  >(null);

  const load = async () => {
    try {
      const s = await getConversationStats();
      setStats(s);
      setLoadError(null);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load stats";
      setLoadError(msg);
    }
  };

  useEffect(() => {
    load();
  }, []);

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
    </ScrollView>
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
    backgroundColor: colors.cardAlt ?? "#f3f4f6",
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
    color: colors.green ?? "#16a34a",
    fontSize: 13,
    marginTop: 10,
    fontFamily: fonts.body,
  },
  errorText: {
    color: colors.red ?? "#dc2626",
    fontSize: 13,
    marginTop: 8,
    fontFamily: fonts.body,
  },
});
