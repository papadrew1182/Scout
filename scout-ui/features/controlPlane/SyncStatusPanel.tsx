/**
 * SyncStatusPanel — sync orchestration counts.
 *
 * Reads the `connectors` and `sync_jobs` buckets from
 * /api/control-plane/summary. The contract ships counts only — no
 * per-job rows — so this panel surfaces the aggregated numbers and
 * relies on ConnectorHealthPanel for per-connector freshness.
 */

import { StyleSheet, Text, View } from "react-native";

import {
  ControlPlaneConnectorsBucket,
  ControlPlaneSyncJobsBucket,
} from "../lib/contracts";
import { colors } from "../../lib/styles";

interface Props {
  connectors: ControlPlaneConnectorsBucket | null;
  syncJobs: ControlPlaneSyncJobsBucket | null;
  unavailable: boolean;
}

export function SyncStatusPanel({ connectors, syncJobs, unavailable }: Props) {
  if (unavailable) {
    return (
      <View style={[styles.panel, styles.unavailable]}>
        <Text style={styles.unavailableText}>
          Summary feed unavailable — counts will appear once
          /api/control-plane/summary ships.
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.panel}>
      <View style={styles.row}>
        <Stat
          label="Healthy"
          value={connectors?.healthy_count ?? 0}
          tone="ok"
        />
        <Stat
          label="Stale"
          value={connectors?.stale_count ?? 0}
          tone={connectors && connectors.stale_count > 0 ? "warn" : "neutral"}
        />
        <Stat
          label="Errors"
          value={connectors?.error_count ?? 0}
          tone={connectors && connectors.error_count > 0 ? "err" : "neutral"}
        />
      </View>
      <View style={styles.divider} />
      <View style={styles.row}>
        <Stat
          label="Sync running"
          value={syncJobs?.running_count ?? 0}
          tone={syncJobs && syncJobs.running_count > 0 ? "info" : "neutral"}
        />
        <Stat
          label="Sync failed"
          value={syncJobs?.failed_count ?? 0}
          tone={syncJobs && syncJobs.failed_count > 0 ? "err" : "neutral"}
        />
      </View>
    </View>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "ok" | "warn" | "err" | "info" | "neutral";
}) {
  return (
    <View style={styles.statCell}>
      <Text
        style={[
          styles.statValue,
          tone === "ok" && { color: colors.positive },
          tone === "warn" && { color: colors.warning },
          tone === "err" && { color: colors.negative },
          tone === "info" && { color: colors.info },
        ]}
      >
        {value}
      </Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  panel: {
    backgroundColor: colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingVertical: 14,
    paddingHorizontal: 12,
  },
  unavailable: { backgroundColor: colors.surfaceMuted },
  unavailableText: {
    color: colors.textMuted,
    fontSize: 12,
    textAlign: "center",
    paddingVertical: 6,
  },
  row: { flexDirection: "row" },
  statCell: { flex: 1, alignItems: "center" },
  statValue: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: "800",
    fontVariant: ["tabular-nums"] as any,
  },
  statLabel: {
    color: colors.textMuted,
    fontSize: 10,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.8,
    marginTop: 2,
  },
  divider: {
    height: 1,
    backgroundColor: colors.divider,
    marginVertical: 12,
  },
});
