/**
 * CalendarPreview — calendar publication preview.
 *
 * Reads /api/calendar/exports/upcoming and renders a day-grouped list
 * of household anchor blocks that will (or have) published to Google
 * Calendar. The Hearth display lane consumes the same Google Calendar
 * stream, so each row's "On Hearth" chip is what the family TV/wall
 * display will show during that block.
 *
 * Cross-references:
 *   - useConnectorsHealth() for the google_calendar connector. If the
 *     Google Calendar connector is stale, lagging, or unhealthy, we
 *     surface a top banner explaining the publication state — exports
 *     listed below remain visible so the user can still see what
 *     SHOULD publish.
 *
 * Both /api/calendar/exports/upcoming and the connector health feed are
 * real and DB-backed (Session 2 block 3, commit 3a3bf31). In mock mode
 * the mock client serves the same shapes from seeded Roberts data.
 */

import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import { CalendarExport, ConnectorHealthItem } from "../lib/contracts";
import { useCalendarExports, useConnectorsHealth } from "../hooks";
import { classifySlice } from "../lib/availability";
import { colors } from "../../lib/styles";
import { HouseholdBlocksPreview } from "./HouseholdBlocksPreview";

export function CalendarPreview() {
  const router = useRouter();
  const exports = useCalendarExports();
  const health = useConnectorsHealth();

  const view = classifySlice(
    { status: exports.status, error: exports.error, data: exports.data },
    "calendar_exports",
    { isEmpty: (d: any) => !d || (d.items ?? []).length === 0 },
  );

  if (view.kind === "loading") {
    return <SkeletonState />;
  }

  if (view.kind === "error") {
    return (
      <ErrorState
        title={view.title}
        body={view.body}
        onRetry={exports.refresh}
      />
    );
  }

  const items = exports.data?.items ?? [];
  const grouped = groupByDay(items);
  const calendarHealth = findGoogleCalendarHealth(health.data?.items);
  const banner = bannerForHealth(calendarHealth);

  return (
    <View>
      <Text style={styles.eyebrow}>Calendar publication</Text>
      <Text style={styles.title}>Household anchor blocks</Text>
      <Text style={styles.subtle}>
        Scout publishes routine blocks to Google Calendar. The Hearth
        display reads the same calendar — anything chipped "On Hearth"
        below is what the wall display will show.
      </Text>

      {banner && (
        <Pressable
          style={[
            styles.banner,
            banner.tone === "warn" && styles.bannerWarn,
            banner.tone === "error" && styles.bannerErr,
          ]}
          onPress={() => router.push("/control-plane")}
          accessibilityRole="link"
          accessibilityLabel={`${banner.title}. Tap to open control plane.`}
        >
          <Text style={styles.bannerTitle}>{banner.title}</Text>
          <Text style={styles.bannerBody}>{banner.body}</Text>
          <Text style={styles.bannerLink}>Open Control Plane</Text>
        </Pressable>
      )}

      {grouped.length === 0 ? (
        <EmptyState
          title="No exports scheduled"
          body="When Scout has anchor blocks ready to publish, they'll appear here."
        />
      ) : (
        grouped.map((group) => (
          <View key={group.dayKey} style={styles.dayBlock}>
            <Text style={styles.dayLabel}>{group.dayLabel}</Text>
            <View style={styles.dayCard}>
              <HouseholdBlocksPreview items={group.items} />
            </View>
          </View>
        ))
      )}

      <Text style={styles.footnote}>
        Hearth is display only. Tap a chore on Today to interact with it —
        Hearth never accepts task input.
      </Text>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Grouping helpers
// ---------------------------------------------------------------------------

interface DayGroup {
  dayKey: string; // YYYY-MM-DD
  dayLabel: string;
  items: CalendarExport[];
}

function groupByDay(items: CalendarExport[]): DayGroup[] {
  const groups = new Map<string, DayGroup>();
  for (const item of items) {
    const d = new Date(item.starts_at);
    if (Number.isNaN(d.getTime())) continue;
    const key = `${d.getFullYear()}-${`${d.getMonth() + 1}`.padStart(
      2,
      "0",
    )}-${`${d.getDate()}`.padStart(2, "0")}`;
    let g = groups.get(key);
    if (!g) {
      g = { dayKey: key, dayLabel: formatDayLabel(d), items: [] };
      groups.set(key, g);
    }
    g.items.push(item);
  }
  // Sort each group's items by start time, then sort groups by date.
  const arr = Array.from(groups.values());
  arr.forEach((g) =>
    g.items.sort(
      (a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime(),
    ),
  );
  arr.sort((a, b) => a.dayKey.localeCompare(b.dayKey));
  return arr;
}

function formatDayLabel(d: Date): string {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const day = new Date(d);
  day.setHours(0, 0, 0, 0);
  const diffDays = Math.round((day.getTime() - today.getTime()) / 86_400_000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Tomorrow";
  if (diffDays >= 2 && diffDays < 7) {
    return d.toLocaleDateString(undefined, { weekday: "long" });
  }
  return d.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

// ---------------------------------------------------------------------------
// Google Calendar health → banner
// ---------------------------------------------------------------------------

function findGoogleCalendarHealth(
  items: ConnectorHealthItem[] | undefined,
): ConnectorHealthItem | null {
  if (!items) return null;
  return items.find((i) => i.connector_key === "google_calendar") ?? null;
}

interface Banner {
  tone: "warn" | "error";
  title: string;
  body: string;
}

function bannerForHealth(h: ConnectorHealthItem | null): Banner | null {
  if (!h) return null;
  if (!h.healthy) {
    return {
      tone: "error",
      title: "Google Calendar isn't connected",
      body:
        h.last_error_message ||
        "Anchor blocks below are queued in Scout but won't reach the family calendar (or Hearth) until the connector is reconnected from Control Plane.",
    };
  }
  if (h.freshness_state === "stale" || h.freshness_state === "lagging") {
    return {
      tone: "warn",
      title: "Google Calendar sync is stale",
      body:
        "Recent edits to anchor blocks may not yet be reflected on Hearth. Check Control Plane for sync status.",
    };
  }
  return null;
}

// ---------------------------------------------------------------------------
// State subcomponents
// ---------------------------------------------------------------------------

function SkeletonState() {
  return (
    <View>
      <Text style={styles.eyebrow}>Calendar publication</Text>
      <Text style={styles.title}>Household anchor blocks</Text>
      <View style={styles.skeletonCard} />
      <View style={styles.skeletonCard} />
      <View style={styles.skeletonCard} />
    </View>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <View style={styles.empty}>
      <Text style={styles.emptyTitle}>{title}</Text>
      <Text style={styles.emptyBody}>{body}</Text>
    </View>
  );
}

function ErrorState({
  title,
  body,
  onRetry,
}: {
  title: string;
  body: string;
  onRetry: () => void;
}) {
  return (
    <View>
      <Text style={styles.eyebrow}>Calendar publication</Text>
      <Text style={styles.title}>Household anchor blocks</Text>
      <View
        style={[styles.banner, styles.bannerErr]}
        accessible
        accessibilityLiveRegion="polite"
      >
        <Text style={styles.bannerTitle}>{title}</Text>
        <Text style={styles.bannerBody}>{body}</Text>
        <Pressable
          style={styles.retry}
          onPress={onRetry}
          accessibilityRole="button"
          accessibilityLabel="Retry loading calendar exports"
          hitSlop={10}
        >
          <Text style={styles.retryText}>Try again</Text>
        </Pressable>
      </View>
    </View>
  );
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
  subtle: {
    color: colors.textMuted,
    fontSize: 13,
    marginTop: 4,
    marginBottom: 16,
    lineHeight: 18,
  },

  banner: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 14,
    marginBottom: 16,
    borderLeftWidth: 3,
    borderLeftColor: colors.cardBorder,
  },
  bannerWarn: {
    backgroundColor: colors.warningBg,
    borderLeftColor: colors.warning,
  },
  bannerErr: {
    backgroundColor: colors.negativeBg,
    borderLeftColor: colors.negative,
  },
  bannerTitle: {
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: "800",
  },
  bannerBody: {
    color: colors.textSecondary,
    fontSize: 12,
    marginTop: 4,
    lineHeight: 16,
  },
  bannerLink: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "700",
    marginTop: 8,
  },

  dayBlock: { marginBottom: 14 },
  dayLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 1.4,
    marginBottom: 8,
    paddingHorizontal: 4,
  },
  dayCard: {
    backgroundColor: colors.card,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 12,
  },

  footnote: {
    color: colors.textPlaceholder,
    fontSize: 11,
    marginTop: 24,
    textAlign: "center",
    paddingHorizontal: 16,
    lineHeight: 16,
    fontStyle: "italic",
  },

  skeletonCard: {
    height: 100,
    borderRadius: 14,
    backgroundColor: colors.surfaceMuted,
    marginBottom: 12,
  },

  empty: { marginTop: 30, alignItems: "center", paddingHorizontal: 12 },
  emptyTitle: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: "700",
    marginBottom: 6,
  },
  emptyBody: {
    color: colors.textMuted,
    fontSize: 13,
    textAlign: "center",
    lineHeight: 18,
  },

  retry: {
    backgroundColor: colors.accent,
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 10,
    alignSelf: "flex-start",
    marginTop: 10,
  },
  retryText: { color: colors.buttonPrimaryText, fontWeight: "700" },
});
