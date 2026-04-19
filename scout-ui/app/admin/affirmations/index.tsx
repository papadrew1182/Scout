import React, { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { Redirect } from "expo-router";
import { shared, colors, fonts } from "../../../lib/styles";
import { useHasPermission } from "../../../lib/permissions";
import { AffirmationLibrary } from "../../../features/affirmations/admin/AffirmationLibrary";
import { AffirmationGovernance } from "../../../features/affirmations/admin/AffirmationGovernance";
import { AffirmationTargeting } from "../../../features/affirmations/admin/AffirmationTargeting";
import { AffirmationAnalytics } from "../../../features/affirmations/admin/AffirmationAnalytics";

const TABS = ["Library", "Governance", "Targeting", "Analytics"] as const;
type Tab = (typeof TABS)[number];

export default function AffirmationsAdmin() {
  const canManage = useHasPermission("affirmations.manage_config");
  const [tab, setTab] = useState<Tab>("Library");

  if (!canManage) return <Redirect href="/" />;

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Affirmations</Text>
      <Text style={styles.subtitle}>Manage the affirmation library, rules, targeting, and analytics.</Text>

      <View style={styles.tabRow}>
        {TABS.map((t) => (
          <Pressable
            key={t}
            style={[styles.tab, tab === t && styles.tabActive]}
            onPress={() => setTab(t)}
            accessibilityRole="tab"
            accessibilityState={{ selected: tab === t }}
          >
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>{t}</Text>
          </Pressable>
        ))}
      </View>

      {tab === "Library" && <AffirmationLibrary />}
      {tab === "Governance" && <AffirmationGovernance />}
      {tab === "Targeting" && <AffirmationTargeting />}
      {tab === "Analytics" && <AffirmationAnalytics />}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, paddingBottom: 48, gap: 14 },
  h1: { fontSize: 20, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  subtitle: { fontSize: 14, color: colors.muted, fontFamily: fonts.body, lineHeight: 20 },
  tabRow: { flexDirection: "row", gap: 0, borderBottomWidth: 1, borderBottomColor: colors.border },
  tab: { paddingVertical: 10, paddingHorizontal: 16 },
  tabActive: { borderBottomWidth: 2, borderBottomColor: colors.purple },
  tabText: { fontSize: 14, color: colors.muted, fontFamily: fonts.body },
  tabTextActive: { color: colors.purple, fontWeight: "600" },
});
