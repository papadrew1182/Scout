/**
 * ConnectorHealthPanel — per-connector status rows.
 *
 * Reads /api/connectors and /api/connectors/health, joins them by
 * connector_key, and renders one row per known connector with:
 *   - traffic-light dot (healthy / stale / error)
 *   - human label
 *   - status from /api/connectors (linked / disconnected / decision_gated / etc.)
 *   - freshness state from /api/connectors/health
 *   - last successful sync (or last error message if present)
 *
 * No mutations. No reconnect button — Block 3 explicitly does not
 * invent backend mutations for retries / approvals / reconnects.
 */

import { StyleSheet, Text, View } from "react-native";

import {
  ConnectorHealthItem,
  ConnectorListItem,
} from "../lib/contracts";
import { useConnectors, useConnectorsHealth } from "../hooks";
import { formatTime } from "../lib/formatters";
import { colors } from "../../lib/styles";

interface JoinedRow {
  connector_key: string;
  label: string;
  status: string;
  health: ConnectorHealthItem | null;
}

export function ConnectorHealthPanel() {
  const connectors = useConnectors();
  const health = useConnectorsHealth();

  if (
    (connectors.status === "idle" || connectors.status === "loading") &&
    (health.status === "idle" || health.status === "loading")
  ) {
    return <PanelSkeleton />;
  }

  // We render even when one of the two slices errors — the joined view
  // can still show whatever is live.
  const rows = joinRows(connectors.data?.items ?? [], health.data?.items ?? []);

  if (rows.length === 0) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>
          No connectors are visible. Confirm /api/connectors is reachable.
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.panel}>
      {rows.map((r) => (
        <ConnectorRow key={r.connector_key} row={r} />
      ))}
    </View>
  );
}

function joinRows(
  list: ConnectorListItem[],
  healthItems: ConnectorHealthItem[],
): JoinedRow[] {
  const healthByKey = new Map(healthItems.map((h) => [h.connector_key, h]));
  return list.map((c) => ({
    connector_key: c.connector_key,
    label: c.label,
    status: c.status,
    health: healthByKey.get(c.connector_key) ?? null,
  }));
}

function ConnectorRow({ row }: { row: JoinedRow }) {
  const { health } = row;
  const tone = toneForRow(row);
  return (
    <View style={styles.row}>
      <View style={[styles.dot, tone === "ok" && styles.dotOk, tone === "warn" && styles.dotWarn, tone === "err" && styles.dotErr]} />
      <View style={styles.bodyCol}>
        <View style={styles.titleRow}>
          <Text style={styles.label}>{row.label}</Text>
          <Text style={[styles.statusPill, statusPillStyle(row.status)]}>
            {row.status.toUpperCase().replace(/_/g, " ")}
          </Text>
        </View>
        <Text style={styles.meta} numberOfLines={2}>
          {describeRow(row)}
        </Text>
      </View>
    </View>
  );
}

type Tone = "ok" | "warn" | "err";

function toneForRow(r: JoinedRow): Tone {
  if (!r.health) {
    return r.status === "connected" ? "ok" : "err";
  }
  if (r.health.healthy) {
    if (
      r.health.freshness_state === "stale" ||
      r.health.freshness_state === "very_stale"
    ) {
      return "warn";
    }
    return "ok";
  }
  return "err";
}

function describeRow(r: JoinedRow): string {
  const h = r.health;
  if (!h) {
    if (r.status === "decision_gated") {
      return "Decision-gated · not linked yet";
    }
    if (r.status === "disconnected") {
      return "Not linked";
    }
    return "Health unknown";
  }
  if (h.last_error_message && !h.healthy) {
    return h.last_error_message;
  }
  if (h.last_success_at) {
    return `Last sync ${formatTime(h.last_success_at)} · ${h.freshness_state}`;
  }
  return h.freshness_state ?? "never synced";
}

function statusPillStyle(s: string) {
  switch (s) {
    case "connected":
      return styles.statusPillOk;
    case "pending":
      return styles.statusPillPending;
    case "disconnected":
    case "error":
      return styles.statusPillErr;
    case "decision_gated":
      return styles.statusPillGated;
    default:
      return styles.statusPillNeutral;
  }
}

function PanelSkeleton() {
  return (
    <View style={styles.panel}>
      <View style={styles.skeletonRow} />
      <View style={styles.skeletonRow} />
      <View style={styles.skeletonRow} />
    </View>
  );
}

const styles = StyleSheet.create({
  panel: {
    backgroundColor: colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingHorizontal: 4,
  },
  row: {
    flexDirection: "row",
    paddingVertical: 12,
    paddingHorizontal: 12,
    alignItems: "center",
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: 12,
    backgroundColor: colors.surfaceMuted,
  },
  dotOk: { backgroundColor: colors.positive },
  dotWarn: { backgroundColor: colors.warning },
  dotErr: { backgroundColor: colors.negative },
  bodyCol: { flex: 1 },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  label: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: "700",
    flex: 1,
  },
  meta: {
    color: colors.textMuted,
    fontSize: 11,
    marginTop: 3,
    fontWeight: "600",
  },
  statusPill: {
    fontSize: 9,
    fontWeight: "800",
    letterSpacing: 0.5,
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 999,
    overflow: "hidden",
    marginLeft: 8,
  },
  statusPillOk: { backgroundColor: colors.positiveBg, color: "#00866B" },
  statusPillErr: { backgroundColor: colors.negativeBg, color: "#C0392B" },
  statusPillPending: { backgroundColor: colors.warningBg, color: "#A2660C" },
  statusPillGated: { backgroundColor: colors.surfaceMuted, color: colors.textMuted },
  statusPillNeutral: { backgroundColor: colors.surfaceMuted, color: colors.textSecondary },

  empty: { padding: 16 },
  emptyText: { color: colors.textMuted, fontSize: 12 },

  skeletonRow: {
    height: 44,
    backgroundColor: colors.surfaceMuted,
    marginVertical: 4,
    marginHorizontal: 12,
    borderRadius: 8,
  },
});
