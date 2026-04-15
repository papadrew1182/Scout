import { StyleSheet, Text, View } from "react-native";

import { useCalendarExports } from "../../../features/hooks";
import { formatTime } from "../../../features/lib/formatters";
import { colors } from "../../../lib/styles";

export default function CalendarRoute() {
  const { data, status, error } = useCalendarExports();
  if (status === "loading" || status === "idle") {
    return <Text style={styles.muted}>Loading calendar exports…</Text>;
  }
  if (status === "error") {
    return <Text style={styles.error}>{error ?? "Failed to load calendar exports"}</Text>;
  }
  if (!data) return null;
  return (
    <View>
      <Text style={styles.eyebrow}>Household calendar</Text>
      <Text style={styles.title}>Anchor blocks publishing to Hearth</Text>
      <Text style={styles.subtle}>
        Calendar is the publication spine. Hearth shows what's published here.
      </Text>

      {data.upcoming.map((e) => (
        <View key={e.export_id} style={styles.card}>
          <Text style={styles.cardTitle}>{e.title}</Text>
          <Text style={styles.subtle}>
            {formatTime(e.starts_at)} – {formatTime(e.ends_at)}
          </Text>
          <Text
            style={[
              styles.statusPill,
              e.publication_status === "published"
                ? styles.statusOk
                : e.publication_status === "failed"
                  ? styles.statusErr
                  : styles.statusPending,
            ]}
          >
            {e.publication_status.toUpperCase()}
          </Text>
        </View>
      ))}

      {data.upcoming.length === 0 && (
        <Text style={styles.muted}>No anchor blocks scheduled.</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  muted: { color: colors.textMuted, marginTop: 60, textAlign: "center" },
  error: { color: colors.negative, marginTop: 60, textAlign: "center" },
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
    marginBottom: 4,
  },
  subtle: { color: colors.textMuted, fontSize: 12, marginBottom: 2 },
  card: {
    backgroundColor: colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 14,
    marginTop: 12,
  },
  cardTitle: { color: colors.textPrimary, fontSize: 15, fontWeight: "700" },
  statusPill: {
    alignSelf: "flex-start",
    marginTop: 8,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 0.5,
    overflow: "hidden",
  },
  statusOk: { backgroundColor: colors.positiveBg, color: "#00866B" },
  statusPending: { backgroundColor: colors.warningBg, color: "#A2660C" },
  statusErr: { backgroundColor: colors.negativeBg, color: "#C0392B" },
});
