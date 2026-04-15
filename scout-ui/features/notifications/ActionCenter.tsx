/**
 * ActionCenter — read-only "things parents may want to act on" surface.
 *
 * No backend mutations and no persistent storage. The center reads
 * existing slices (control plane summary + household today + rewards)
 * and surfaces a short list of "open items". Tapping an item navigates
 * to the surface that owns it.
 *
 * Visible only when the actor is parent-tier; rendered as nothing for
 * kid-tier viewers.
 */

import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import {
  useControlPlaneSummary,
  useHouseholdToday,
  useIsParent,
} from "../hooks";
import { colors } from "../../lib/styles";

interface ActionItem {
  id: string;
  title: string;
  detail: string;
  href: string;
  tone: "warn" | "err" | "info";
}

export function ActionCenter() {
  const isParent = useIsParent();
  const summary = useControlPlaneSummary();
  const today = useHouseholdToday();
  const router = useRouter();

  if (!isParent) return null;

  const items = collectItems(summary.data, today.data?.summary);

  return (
    <View style={styles.card}>
      <Text style={styles.label}>Action center</Text>
      <Text style={styles.helper}>
        Things waiting on a parent. Read-only — no actions land here yet.
      </Text>
      {items.length === 0 ? (
        <Text style={styles.empty}>Nothing waiting. Quiet day.</Text>
      ) : (
        items.map((it) => (
          <Pressable
            key={it.id}
            style={styles.item}
            onPress={() => router.push(it.href as any)}
            accessibilityRole="button"
            accessibilityLabel={`${it.title} — open`}
          >
            <View
              style={[
                styles.itemDot,
                it.tone === "warn" && styles.itemDotWarn,
                it.tone === "err" && styles.itemDotErr,
                it.tone === "info" && styles.itemDotInfo,
              ]}
            />
            <View style={styles.itemBody}>
              <Text style={styles.itemTitle}>{it.title}</Text>
              <Text style={styles.itemDetail}>{it.detail}</Text>
            </View>
            <Text style={styles.itemArrow}>›</Text>
          </Pressable>
        ))
      )}
    </View>
  );
}

function collectItems(
  summary: ReturnType<typeof useControlPlaneSummary>["data"],
  todaySummary: { due_count: number; completed_count: number; late_count: number } | undefined,
): ActionItem[] {
  const items: ActionItem[] = [];

  if (summary?.rewards.pending_approval_count) {
    items.push({
      id: "rewards-pending",
      title: `${summary.rewards.pending_approval_count} reward approval${summary.rewards.pending_approval_count === 1 ? "" : "s"}`,
      detail: "Open Rewards to review the projection",
      href: "/rewards",
      tone: "warn",
    });
  }

  if (summary?.connectors.error_count) {
    items.push({
      id: "connector-errors",
      title: `${summary.connectors.error_count} connector${summary.connectors.error_count === 1 ? "" : "s"} in error`,
      detail: "Check Control Plane for the failing connector",
      href: "/control-plane",
      tone: "err",
    });
  }

  if (summary?.calendar_exports.failed_count) {
    items.push({
      id: "calendar-failed",
      title: `${summary.calendar_exports.failed_count} calendar export${summary.calendar_exports.failed_count === 1 ? "" : "s"} failed`,
      detail: "Hearth may be out of date",
      href: "/calendar",
      tone: "err",
    });
  }

  if (todaySummary && todaySummary.late_count > 0) {
    items.push({
      id: "today-late",
      title: `${todaySummary.late_count} late item${todaySummary.late_count === 1 ? "" : "s"} on Today`,
      detail: "Quiet enforcement still applies — review on Today",
      href: "/today",
      tone: "warn",
    });
  }

  return items;
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 14,
    marginTop: 18,
  },
  label: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 1.4,
    marginBottom: 4,
  },
  helper: {
    color: colors.textMuted,
    fontSize: 12,
    fontStyle: "italic",
    marginBottom: 12,
  },
  empty: { color: colors.textPlaceholder, fontSize: 12, fontStyle: "italic" },
  item: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  itemDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 12,
    backgroundColor: colors.surfaceMuted,
  },
  itemDotWarn: { backgroundColor: colors.warning },
  itemDotErr: { backgroundColor: colors.negative },
  itemDotInfo: { backgroundColor: colors.info },
  itemBody: { flex: 1 },
  itemTitle: { color: colors.textPrimary, fontSize: 13, fontWeight: "700" },
  itemDetail: { color: colors.textMuted, fontSize: 11, marginTop: 2 },
  itemArrow: {
    color: colors.textMuted,
    fontSize: 18,
    marginLeft: 6,
    fontWeight: "600",
  },
});
