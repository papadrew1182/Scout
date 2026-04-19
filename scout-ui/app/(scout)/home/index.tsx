import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "../../../lib/styles";

const API_BASE_URL = process.env.EXPO_PUBLIC_SCOUT_API_URL || "http://localhost:8000";

interface Zone { id: string; name: string; zone_type: string }
interface Instance {
  id: string;
  template_id: string;
  owner_member_id: string;
  scheduled_for: string;
  completed_at: string | null;
  notes: string | null;
}

function useHomeData() {
  const [zones, setZones] = useState<Zone[]>([]);
  const [instances, setInstances] = useState<Instance[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = typeof localStorage !== "undefined" ? localStorage.getItem("scout_session_token") : null;
    const familyId = typeof localStorage !== "undefined" ? localStorage.getItem("scout_family_id") : null;
    if (!token || !familyId) { setLoading(false); return; }
    const headers = { Authorization: `Bearer ${token}` };
    Promise.all([
      fetch(`${API_BASE_URL}/families/${familyId}/home/zones`, { headers }).then(r => r.ok ? r.json() : []),
      fetch(`${API_BASE_URL}/families/${familyId}/home/instances`, { headers }).then(r => r.ok ? r.json() : []),
    ]).then(([z, i]) => { setZones(z); setInstances(i); }).finally(() => setLoading(false));
  }, []);

  return { zones, instances, loading };
}

export default function HomeRoute() {
  const { zones, instances, loading } = useHomeData();
  const upcoming = instances.filter(i => !i.completed_at);

  if (loading) {
    return (
      <View style={styles.container}>
        <Text style={styles.eyebrow}>HOME</Text>
        <Text style={styles.title}>Maintenance</Text>
        <View style={styles.skeleton} />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.eyebrow}>HOME</Text>
      <Text style={styles.title}>Maintenance</Text>

      {upcoming.length > 0 ? (
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Upcoming</Text>
          {upcoming.map(inst => (
            <View key={inst.id} style={styles.row}>
              <View style={styles.dot} />
              <Text style={styles.rowLabel}>Task {inst.template_id.slice(0, 8)}</Text>
              <Text style={styles.rowMeta}>
                {new Date(inst.scheduled_for).toLocaleDateString()}
              </Text>
            </View>
          ))}
        </View>
      ) : (
        <View style={styles.card}>
          <Text style={styles.emptyTitle}>No upcoming maintenance</Text>
          <Text style={styles.emptyBody}>
            Ask an admin to create maintenance templates and generate upcoming instances.
          </Text>
        </View>
      )}

      {zones.length > 0 && (
        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Zones</Text>
          {zones.map(z => (
            <View key={z.id} style={styles.row}>
              <Text style={styles.rowLabel}>{z.name}</Text>
              <Text style={styles.rowMeta}>{z.zone_type}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { paddingTop: 8 },
  eyebrow: { color: colors.accent, fontSize: 11, fontWeight: "800", letterSpacing: 1.6, textTransform: "uppercase" },
  title: { color: colors.textPrimary, fontSize: 30, fontWeight: "800", marginTop: 4, letterSpacing: -0.6 },
  card: { backgroundColor: colors.card, borderRadius: 14, borderWidth: 1, borderColor: colors.cardBorder, padding: 16, marginTop: 16 },
  sectionTitle: { color: colors.textSecondary, fontSize: 11, fontWeight: "800", textTransform: "uppercase", letterSpacing: 1.2, marginBottom: 10 },
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 8, borderTopWidth: 1, borderTopColor: colors.divider },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.accent, marginRight: 10 },
  rowLabel: { flex: 1, color: colors.textPrimary, fontSize: 13, fontWeight: "600" },
  rowMeta: { color: colors.textMuted, fontSize: 11, fontWeight: "600" },
  emptyTitle: { color: colors.textPrimary, fontSize: 14, fontWeight: "700", marginBottom: 6 },
  emptyBody: { color: colors.textMuted, fontSize: 13, lineHeight: 18 },
  skeleton: { height: 120, borderRadius: 14, backgroundColor: colors.surfaceMuted, marginTop: 16 },
});
