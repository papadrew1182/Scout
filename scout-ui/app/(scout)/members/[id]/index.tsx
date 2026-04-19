// Phase 3 placeholder - child master card route.
// Full implementation (today's tasks, streak, scope contracts, allowance
// forecast) lands in Phase 3 of the operability sprint. This stub exists
// solely to satisfy tap-target wiring from Phase 1.

import { StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";

import { useFamilyContext, useMe } from "../../../../features/hooks";
import { colors } from "../../../../lib/styles";

export default function MemberDetailRoute() {
  const { id, tab } = useLocalSearchParams<{ id: string; tab?: string }>();
  const family = useFamilyContext();
  const me = useMe();

  const kids = family.data?.kids ?? [];
  const member = kids.find((k) => k.family_member_id === id);
  const memberName = member?.name ?? "Member";

  const isOwnCard =
    me.data?.user.family_member_id === id;
  const isParentTier =
    me.data?.user.role_tier_key === "PRIMARY_PARENT" ||
    me.data?.user.role_tier_key === "PARENT";
  const canView = isOwnCard || isParentTier;

  if (!canView) {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>Not available</Text>
        <Text style={styles.body}>
          You can only view your own master card.
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.eyebrow}>MEMBER</Text>
      <Text style={styles.title}>{memberName}</Text>
      {tab && <Text style={styles.tab}>Tab: {tab}</Text>}
      <View style={styles.placeholder}>
        <Text style={styles.placeholderTitle}>Coming in Phase 3</Text>
        <Text style={styles.body}>
          This screen will show today's tasks, ownership chores, current
          streak, Daily Win forecast, allowance forecast, and scope
          contracts for each active chore.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { paddingTop: 8 },
  eyebrow: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1.6,
    textTransform: "uppercase",
  },
  title: {
    color: colors.textPrimary,
    fontSize: 30,
    fontWeight: "800",
    marginTop: 4,
    letterSpacing: -0.6,
  },
  tab: {
    color: colors.textMuted,
    fontSize: 12,
    marginTop: 4,
    fontWeight: "600",
  },
  placeholder: {
    backgroundColor: colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 20,
    marginTop: 20,
    alignItems: "center",
  },
  placeholderTitle: {
    color: colors.textSecondary,
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 8,
  },
  body: {
    color: colors.textMuted,
    fontSize: 13,
    textAlign: "center",
    lineHeight: 18,
  },
});
