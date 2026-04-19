/**
 * DailyWinCard — kid-readable Daily Win progress strip.
 *
 * Five dots, Mon..Fri. Filled = win earned, hollow = pending or missed.
 * /api/rewards/week/current ships `daily_wins` as a single integer count
 * (not a per-day array). We render the first N dots filled where N =
 * daily_wins. Day-by-day mapping lands when the backend exposes it.
 */

import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import { RewardsMember } from "../lib/contracts";
import { colors } from "../../lib/styles";

interface Props {
  member: RewardsMember;
}

export function DailyWinCard({ member }: Props) {
  const router = useRouter();
  const total = 5;
  const dots = Array.from({ length: total }, (_, i) => i < member.daily_wins);
  const allFive = member.daily_wins >= 5;

  return (
    <Pressable
      style={[styles.card, allFive && styles.cardHero]}
      onPress={() => router.push(`/members/${member.family_member_id}?tab=wins`)}
      accessible
      accessibilityRole="link"
      accessibilityLabel={`${member.name} ${member.daily_wins} of 5 daily wins`}
    >
      <Text style={[styles.name, allFive && styles.nameHero]}>{member.name}</Text>
      <View style={styles.dots}>
        {dots.map((filled, i) => (
          <View key={i} style={[styles.dot, filled && styles.dotFilled]} />
        ))}
      </View>
      <Text style={[styles.count, allFive && styles.countHero]}>
        {member.daily_wins} / {total}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexBasis: "30%",
    flexGrow: 1,
    minWidth: 100,
    backgroundColor: colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingHorizontal: 12,
    paddingVertical: 12,
    alignItems: "center",
  },
  cardHero: { backgroundColor: colors.positiveBg, borderColor: colors.positive },
  name: { color: colors.textPrimary, fontSize: 13, fontWeight: "700" },
  nameHero: { color: "#00866B" },
  dots: { flexDirection: "row", gap: 6, marginTop: 8, marginBottom: 6 },
  dot: {
    width: 9,
    height: 9,
    borderRadius: 5,
    backgroundColor: colors.surfaceMuted,
    borderWidth: 1,
    borderColor: colors.cardBorder,
  },
  dotFilled: { backgroundColor: colors.accent, borderColor: colors.accent },
  count: { color: colors.textMuted, fontSize: 11, fontWeight: "700" },
  countHero: { color: "#00866B" },
});
