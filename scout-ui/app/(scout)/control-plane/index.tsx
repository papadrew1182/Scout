import { StyleSheet, Text, View } from "react-native";

import { useControlPlaneSummary } from "../../../features/hooks";
import { formatTime } from "../../../features/lib/formatters";
import { colors } from "../../../lib/styles";

export default function ControlPlaneRoute() {
  const { data, status, error } = useControlPlaneSummary();
  if (status === "loading" || status === "idle") {
    return <Text style={styles.muted}>Loading control plane…</Text>;
  }
  if (status === "error") {
    return <Text style={styles.error}>{error ?? "Failed to load control plane"}</Text>;
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
        <View key={c.id} style={styles.row}>
          <View style={[styles.rowDot, c.ok ? styles.dotOk : styles.dotErr]} />
          <Text style={styles.rowMain}>{c.id}</Text>
          <Text style={styles.rowSub}>
            {c.last_sync_status} · {c.last_sync_at ? formatTime(c.last_sync_at) : "never"}
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
      {data.sync_jobs.some((j) => j.error_message) && (
        <Text style={styles.error}>
          {data.sync_jobs.find((j) => j.error_message)?.error_message}
        </Text>
      )}

      <Text style={styles.section}>Publication</Text>
      {data.publications.map((p) => (
        <View key={p.surface} style={styles.row}>
          <View style={[styles.rowDot, p.failed_count > 0 ? styles.dotErr : styles.dotOk]} />
          <Text style={styles.rowMain}>{p.surface.replace(/_/g, " ")}</Text>
          <Text style={styles.rowSub}>
            pending {p.pending_count} · failed {p.failed_count}
          </Text>
        </View>
      ))}

      <Text style={styles.section}>Notifications</Text>
      <View style={styles.row}>
        <View style={[styles.rowDot, styles.dotInfo]} />
        <Text style={styles.rowMain}>Rules active</Text>
        <Text style={styles.rowSub}>{data.notifications.rules_active}</Text>
      </View>
      <View style={styles.row}>
        <View style={[styles.rowDot, styles.dotOk]} />
        <Text style={styles.rowMain}>Deliveries 24h</Text>
        <Text style={styles.rowSub}>{data.notifications.deliveries_24h}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  muted: { color: colors.textMuted, marginTop: 60, textAlign: "center" },
  error: { color: colors.negative, marginTop: 8 },
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
});
