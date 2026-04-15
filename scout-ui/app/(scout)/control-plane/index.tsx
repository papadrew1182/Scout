import { StyleSheet, Text, View } from "react-native";

import { useControlPlaneSummary } from "../../../features/hooks";
import { formatTime } from "../../../features/lib/formatters";
import { colors } from "../../../lib/styles";

/**
 * Control-plane placeholder surface. The /api/control-plane/summary
 * endpoint is not yet shipped by the backend, so this route still reads
 * from the mock client. Field names match the canonical
 * ConnectorHealthItem (connector_key, healthy, last_success_at, etc).
 */
export default function ControlPlaneRoute() {
  const { data, status, error } = useControlPlaneSummary();
  if (status === "loading" || status === "idle") {
    return <Text style={styles.muted}>Loading control plane…</Text>;
  }
  if (status === "error") {
    return (
      <View>
        <Text style={styles.eyebrow}>Control plane</Text>
        <Text style={styles.title}>Not yet shipped</Text>
        <Text style={styles.muted}>
          {error ?? "Endpoint not implemented by the backend yet."}
        </Text>
      </View>
    );
  }
  if (!data) return null;

  return (
    <View>
      <Text style={styles.eyebrow}>Control plane</Text>
      <Text style={styles.title}>Connectors, sync, publication</Text>
      <View
        style={[
          styles.statusBar,
          data.household_status === "healthy" && styles.statusBarOk,
          data.household_status === "warning" && styles.statusBarWarn,
          data.household_status === "critical" && styles.statusBarErr,
        ]}
      >
        <Text style={styles.statusBarText}>
          Household status: {data.household_status.toUpperCase()}
        </Text>
      </View>

      <Text style={styles.section}>Connector health</Text>
      {data.connectors.map((c) => (
        <View key={c.connector_key} style={styles.row}>
          <View style={[styles.rowDot, c.healthy ? styles.dotOk : styles.dotErr]} />
          <Text style={styles.rowMain}>{c.connector_key}</Text>
          <Text style={styles.rowSub}>
            {c.freshness_state} ·{" "}
            {c.last_success_at ? formatTime(c.last_success_at) : "never"}
          </Text>
        </View>
      ))}

      <Text style={styles.section}>Sync jobs</Text>
      {data.sync_jobs.map((j) => (
        <View key={j.job_id} style={styles.row}>
          <View
            style={[
              styles.rowDot,
              j.status === "idle" && styles.dotOk,
              j.status === "running" && styles.dotInfo,
              j.status === "error" && styles.dotErr,
            ]}
          />
          <Text style={styles.rowMain}>{j.name}</Text>
          <Text style={styles.rowSub}>
            {j.status}
            {j.last_run_at ? ` · last ${formatTime(j.last_run_at)}` : ""}
          </Text>
        </View>
      ))}

      <Text style={styles.section}>Publication</Text>
      {data.publications.map((p) => (
        <View key={p.surface} style={styles.row}>
          <View
            style={[styles.rowDot, p.failed_count > 0 ? styles.dotErr : styles.dotOk]}
          />
          <Text style={styles.rowMain}>{p.surface.replace(/_/g, " ")}</Text>
          <Text style={styles.rowSub}>
            pending {p.pending_count} · failed {p.failed_count}
          </Text>
        </View>
      ))}

      <Text style={styles.note}>
        This surface still reads from the mock client. Once
        /api/control-plane/summary ships it will switch automatically.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  muted: { color: colors.textMuted, marginTop: 60, textAlign: "center" },
  eyebrow: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1.6,
    textTransform: "uppercase",
  },
  title: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: "700",
    marginTop: 4,
    marginBottom: 12,
  },
  statusBar: {
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 10,
    marginBottom: 4,
  },
  statusBarOk: { backgroundColor: colors.positiveBg },
  statusBarWarn: { backgroundColor: colors.warningBg },
  statusBarErr: { backgroundColor: colors.negativeBg },
  statusBarText: { color: colors.textPrimary, fontWeight: "700", fontSize: 12 },
  section: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 1.4,
    marginTop: 24,
    marginBottom: 8,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },
  rowDot: { width: 8, height: 8, borderRadius: 4, marginRight: 12 },
  dotOk: { backgroundColor: colors.positive },
  dotErr: { backgroundColor: colors.negative },
  dotInfo: { backgroundColor: colors.info },
  rowMain: { flex: 1, color: colors.textPrimary, fontSize: 13, fontWeight: "600" },
  rowSub: { color: colors.textMuted, fontSize: 12 },
  note: {
    color: colors.textPlaceholder,
    fontSize: 11,
    marginTop: 18,
    textAlign: "center",
  },
});
