import React, { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { colors, fonts, shared } from "../../../lib/styles";
import { AffirmationAnalytics as AnalyticsData, fetchAffirmationAnalytics } from "../../../lib/affirmations";

export function AffirmationAnalytics() {
  const [data, setData] = useState<AnalyticsData | null>(null);

  useEffect(() => {
    fetchAffirmationAnalytics().then(setData).catch(() => {});
  }, []);

  if (!data) return <Text style={styles.loading}>Loading analytics...</Text>;

  return (
    <View style={{ gap: 14 }}>
      {/* Summary counts */}
      <View style={[shared.card, styles.summaryCard]}>
        <Stat label="Deliveries" value={data.total_deliveries} />
        <Stat label="Hearts" value={data.reactions.heart} />
        <Stat label="Nopes" value={data.reactions.thumbs_down} />
        <Stat label="Skips" value={data.reactions.skip} />
        <Stat label="Reshows" value={data.reactions.reshow} />
      </View>

      {/* Most liked */}
      <View style={shared.card}>
        <Text style={styles.sectionTitle}>Most Liked</Text>
        {data.most_liked.length === 0 && <Text style={styles.empty}>No hearts yet.</Text>}
        {data.most_liked.map((item) => (
          <View key={item.id} style={styles.listRow}>
            <Text style={styles.listText} numberOfLines={1}>{item.text}</Text>
            <Text style={styles.listCount}>{item.hearts} ♡</Text>
          </View>
        ))}
      </View>

      {/* Most rejected */}
      <View style={shared.card}>
        <Text style={styles.sectionTitle}>Most Rejected</Text>
        {data.most_rejected.length === 0 && <Text style={styles.empty}>No rejections yet.</Text>}
        {data.most_rejected.map((item) => (
          <View key={item.id} style={styles.listRow}>
            <Text style={styles.listText} numberOfLines={1}>{item.text}</Text>
            <Text style={styles.listCount}>{item.thumbs_down} 👎</Text>
          </View>
        ))}
      </View>

      {/* Stale */}
      <View style={shared.card}>
        <Text style={styles.sectionTitle}>Stale (30+ days unseen)</Text>
        {data.stale.length === 0 && <Text style={styles.empty}>All affirmations are in active rotation.</Text>}
        {data.stale.map((item) => (
          <View key={item.id} style={styles.listRow}>
            <Text style={styles.listText} numberOfLines={1}>{item.text}</Text>
            <Text style={styles.listMeta}>{item.last_delivered ? `Last: ${item.last_delivered.slice(0, 10)}` : "Never shown"}</Text>
          </View>
        ))}
      </View>

      {/* Per audience */}
      <View style={shared.card}>
        <Text style={styles.sectionTitle}>By Audience</Text>
        {Object.entries(data.per_audience).map(([aud, count]) => (
          <View key={aud} style={styles.listRow}>
            <Text style={styles.listText}>{aud}</Text>
            <Text style={styles.listCount}>{count}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  loading: { fontSize: 14, color: colors.muted, fontFamily: fonts.body, textAlign: "center", paddingVertical: 20 },
  summaryCard: { flexDirection: "row", justifyContent: "space-around", padding: 16 },
  stat: { alignItems: "center" },
  statValue: { fontSize: 22, fontWeight: "700", color: colors.text, fontFamily: fonts.body },
  statLabel: { fontSize: 12, color: colors.muted, fontFamily: fonts.body, marginTop: 2 },
  sectionTitle: { fontSize: 15, fontWeight: "600", color: colors.text, fontFamily: fonts.body, padding: 14, paddingBottom: 8 },
  listRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 8, paddingHorizontal: 14, borderTopWidth: 1, borderTopColor: colors.border },
  listText: { flex: 1, fontSize: 14, color: colors.text, fontFamily: fonts.body },
  listCount: { fontSize: 14, fontWeight: "600", color: colors.purple, fontFamily: fonts.body, marginLeft: 8 },
  listMeta: { fontSize: 12, color: colors.muted, fontFamily: fonts.body, marginLeft: 8 },
  empty: { fontSize: 13, color: colors.muted, fontFamily: fonts.body, padding: 14, paddingTop: 0 },
});
