/**
 * TodayHome — Session 3 default landing surface.
 *
 * Answers the questions the operating surface MUST answer:
 *   - what is active now
 *   - what is due next
 *   - who still has work left
 *   - what can be completed in one tap
 *   - what is blocked or late
 *   - whether each child is still on track for a Daily Win
 *
 * Layout (mobile-first):
 *   1. Header: family name, today's date
 *   2. Daily Win strip: per-child status pill + on-track indicator
 *   3. Filter chips: Household | Sadie | Townes | River
 *   4. <HouseholdBoard /> — vertical list of <BlockCard />
 *   5. CompletionSheet renders inline at the bottom when open
 */

import { Pressable, StyleSheet, Text, View } from "react-native";

import { useFamilyContext, useHouseholdToday, useUiCompletionSheet, useUiFocusMember } from "../hooks";
import { colors } from "../../lib/styles";
import { HouseholdBoard } from "./HouseholdBoard";
import { CompletionSheet } from "./CompletionSheet";

export function TodayHome() {
  const today = useHouseholdToday();
  const family = useFamilyContext();
  const { focused_member_id, setFocus } = useUiFocusMember();
  const { occurrence_id: sheetOccId, close: closeSheet } = useUiCompletionSheet();

  if (today.status === "idle" || today.status === "loading") {
    return <LoadingState />;
  }
  if (today.status === "error" || !today.data) {
    return <ErrorState message={today.error ?? "Couldn't load today"} onRetry={today.refresh} />;
  }

  const data = today.data;
  const kids = (family.data?.members ?? []).filter((m) => m.role === "child" && m.is_active);
  const dateLabel = formatDateHeader(data.date);

  // Daily-win lookup
  const winByMember = new Map(data.daily_win_preview.map((d) => [d.member_id, d]));

  // Filter blocks/occurrences if a child is focused
  const filtered = focused_member_id
    ? {
        ...data,
        blocks: data.blocks
          .map((b) => ({
            ...b,
            occurrences: b.occurrences.filter((o) => o.owner.member_id === focused_member_id),
          }))
          .filter((b) => b.occurrences.length > 0),
        standalone_occurrences: data.standalone_occurrences.filter(
          (o) => o.owner.member_id === focused_member_id,
        ),
      }
    : data;

  return (
    <View>
      <Text style={styles.eyebrow}>{family.data?.family_name ?? "Household"}</Text>
      <Text style={styles.title}>Today</Text>
      <Text style={styles.subtitle}>{dateLabel}</Text>

      {/* Daily Win strip */}
      <View style={styles.winRow}>
        {kids.map((k) => {
          const win = winByMember.get(k.member_id);
          if (!win) return null;
          const onTrack = win.on_track && win.remaining_count > 0;
          const allDone = win.required_count > 0 && win.remaining_count === 0;
          return (
            <View
              key={k.member_id}
              style={[
                styles.winPill,
                allDone && styles.winPillDone,
                !allDone && !onTrack && styles.winPillRisk,
              ]}
            >
              <Text
                style={[
                  styles.winName,
                  allDone && styles.winNameDone,
                  !allDone && !onTrack && styles.winNameRisk,
                ]}
              >
                {k.first_name}
              </Text>
              <Text style={styles.winCount}>
                {win.completed_count} / {win.required_count}
              </Text>
            </View>
          );
        })}
      </View>

      {/* Filter chips: household + per child */}
      <View style={styles.chipRow}>
        <FilterChip
          label="Household"
          active={focused_member_id === null}
          onPress={() => setFocus(null)}
        />
        {kids.map((k) => (
          <FilterChip
            key={k.member_id}
            label={k.first_name}
            active={focused_member_id === k.member_id}
            onPress={() => setFocus(k.member_id)}
          />
        ))}
      </View>

      <HouseholdBoard data={filtered} />

      <CompletionSheet
        occurrenceId={sheetOccId}
        onClose={closeSheet}
        source={data}
      />
    </View>
  );
}

function FilterChip({
  label,
  active,
  onPress,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      style={[styles.chip, active && styles.chipActive]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`Filter ${label}`}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

function LoadingState() {
  return (
    <View style={styles.center}>
      <Text style={styles.muted}>Loading today…</Text>
    </View>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <View style={styles.center}>
      <Text style={styles.error}>{message}</Text>
      <Pressable style={styles.retry} onPress={onRetry} accessibilityRole="button">
        <Text style={styles.retryText}>Try again</Text>
      </Pressable>
    </View>
  );
}

function formatDateHeader(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

const styles = StyleSheet.create({
  eyebrow: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1.6,
    textTransform: "uppercase",
  },
  title: {
    color: colors.textPrimary,
    fontSize: 30,
    fontWeight: "800",
    marginTop: 4,
    letterSpacing: -0.6,
  },
  subtitle: {
    color: colors.textMuted,
    fontSize: 13,
    marginTop: 4,
    marginBottom: 16,
  },

  winRow: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 14,
  },
  winPill: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  winPillDone: {
    backgroundColor: colors.positiveBg,
    borderColor: colors.positive,
  },
  winPillRisk: {
    backgroundColor: colors.warningBg,
    borderColor: colors.warning,
  },
  winName: {
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: "700",
  },
  winNameDone: { color: "#00866B" },
  winNameRisk: { color: "#A2660C" },
  winCount: {
    color: colors.textMuted,
    fontSize: 11,
    marginTop: 2,
    fontWeight: "600",
  },

  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: 18,
  },
  chip: {
    backgroundColor: colors.card,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  chipActive: {
    backgroundColor: colors.accent,
    borderColor: colors.accent,
  },
  chipText: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: "700",
  },
  chipTextActive: {
    color: colors.buttonPrimaryText,
  },

  center: { alignItems: "center", paddingTop: 80 },
  muted: { color: colors.textMuted },
  error: { color: colors.negative, fontSize: 14, marginBottom: 12 },
  retry: {
    backgroundColor: colors.accent,
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  retryText: { color: colors.buttonPrimaryText, fontWeight: "700" },
});
