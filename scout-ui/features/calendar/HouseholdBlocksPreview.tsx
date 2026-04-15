/**
 * HouseholdBlocksPreview — list-of-anchor-blocks renderer.
 *
 * Pure layout component. Receives a CalendarExport[] (already filtered
 * / sorted by CalendarPreview) and renders one row per export with:
 *   - label
 *   - start-end time range
 *   - source_type pill ("Routine block", "Power 60", etc.)
 *   - target pill ("Google Calendar")
 *   - "On Hearth" chip when hearth_visible === true
 *
 * No data fetching, no mutations. The Hearth chip is display-only by
 * design — Hearth is the calendar display lane, not an interactive
 * surface.
 */

import { StyleSheet, Text, View } from "react-native";

import { CalendarExport } from "../lib/contracts";
import { formatTime } from "../lib/formatters";
import { colors } from "../../lib/styles";

interface Props {
  items: CalendarExport[];
}

export function HouseholdBlocksPreview({ items }: Props) {
  if (items.length === 0) {
    return (
      <Text style={styles.empty}>No anchor blocks scheduled to publish.</Text>
    );
  }
  return (
    <View>
      {items.map((item) => (
        <ExportRow key={item.calendar_export_id} item={item} />
      ))}
    </View>
  );
}

function ExportRow({ item }: { item: CalendarExport }) {
  return (
    <View style={styles.row}>
      <View style={styles.timeCol}>
        <Text style={styles.timeMain}>{formatTime(item.starts_at)}</Text>
        <Text style={styles.timeSub}>{formatTime(item.ends_at)}</Text>
      </View>

      <View style={styles.bodyCol}>
        <Text style={styles.label}>{item.label}</Text>
        <View style={styles.pillRow}>
          <Pill kind="source">{labelForSourceType(item.source_type)}</Pill>
          <Pill kind="target">{labelForTarget(item.target)}</Pill>
          {item.hearth_visible && <Pill kind="hearth">On Hearth</Pill>}
        </View>
      </View>
    </View>
  );
}

function Pill({
  kind,
  children,
}: {
  kind: "source" | "target" | "hearth";
  children: React.ReactNode;
}) {
  return (
    <View
      style={[
        styles.pill,
        kind === "source" && styles.pillSource,
        kind === "target" && styles.pillTarget,
        kind === "hearth" && styles.pillHearth,
      ]}
    >
      <Text
        style={[
          styles.pillText,
          kind === "source" && styles.pillTextSource,
          kind === "target" && styles.pillTextTarget,
          kind === "hearth" && styles.pillTextHearth,
        ]}
      >
        {children}
      </Text>
    </View>
  );
}

function labelForSourceType(t: string): string {
  switch (t) {
    case "routine_block":
      return "Routine block";
    case "weekly_event":
      return "Weekly event";
    case "ownership_chore":
      return "Ownership chore";
    case "rotating_chore":
      return "Rotating chore";
    default:
      return t.replace(/_/g, " ");
  }
}

function labelForTarget(t: string): string {
  switch (t) {
    case "google_calendar":
      return "Google Calendar";
    default:
      return t.replace(/_/g, " ");
  }
}

const styles = StyleSheet.create({
  empty: {
    color: colors.textPlaceholder,
    fontSize: 13,
    fontStyle: "italic",
    marginTop: 18,
    textAlign: "center",
  },
  row: {
    flexDirection: "row",
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  timeCol: {
    width: 64,
    alignItems: "flex-start",
    paddingTop: 2,
  },
  timeMain: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: "800",
    fontVariant: ["tabular-nums"] as any,
  },
  timeSub: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "600",
    marginTop: 1,
    fontVariant: ["tabular-nums"] as any,
  },
  bodyCol: { flex: 1, paddingLeft: 4 },
  label: { color: colors.textPrimary, fontSize: 15, fontWeight: "700" },
  pillRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 6,
  },
  pill: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
  },
  pillSource: { backgroundColor: colors.surfaceMuted },
  pillTarget: { backgroundColor: colors.accentBg },
  pillHearth: { backgroundColor: colors.positiveBg },
  pillText: {
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 0.5,
  },
  pillTextSource: { color: colors.textSecondary },
  pillTextTarget: { color: colors.accent },
  pillTextHearth: { color: "#00866B" },
});
