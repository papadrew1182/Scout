import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";

import { colors, fonts, shared } from "../../lib/styles";
import { TOWNES_CHORES, getMember, LEADERBOARD, ALLOWANCE } from "../../lib/seedData";

const TINT_BG: Record<string, string> = {
  purple: colors.avPurpleBg, teal: colors.avTealBg, amber: colors.avAmberBg, coral: colors.avCoralBg,
};
const TINT_TEXT: Record<string, string> = {
  purple: colors.avPurpleText, teal: colors.avTealText, amber: colors.avAmberText, coral: colors.avCoralText,
};

export default function Child() {
  const params = useLocalSearchParams<{ memberId: string }>();
  // Always show Townes for the demo regardless of route param.
  const member = getMember(params.memberId ?? "townes") ?? getMember("townes")!;
  const allowance = ALLOWANCE.find((a) => a.memberId === member.id) ?? ALLOWANCE[1];
  const leader = LEADERBOARD.find((l) => l.memberId === member.id) ?? LEADERBOARD[0];
  const pct = leader.points >= 1000 ? 100 : Math.round((leader.points / 1000) * 100);
  const remaining = Math.max(0, 1000 - leader.points);

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <View style={styles.hero}>
        <View style={[styles.bigAv, { backgroundColor: TINT_BG[member.tint] }]}>
          <Text style={[styles.bigAvText, { color: TINT_TEXT[member.tint] }]}>{member.initials}</Text>
        </View>
        <Text style={styles.heroTitle}>Hey {member.firstName}!</Text>
        <Text style={styles.heroSub}>Wednesday · You finished all your chores today!</Text>
        <View style={styles.heroPill}>
          <Text style={styles.heroPillText}>{leader.points} pts total · Rank #{leader.rank} this week 🏆</Text>
        </View>
      </View>

      <View style={styles.grid2}>
        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>My chores today</Text>
            <View style={styles.tagGreen}><Text style={styles.tagGreenText}>All done!</Text></View>
          </View>
          {TOWNES_CHORES.map((c) => (
            <View key={c.name} style={styles.choreRow}>
              <View style={[styles.check, c.done && styles.checkDone]}>
                {c.done && <Text style={styles.checkMark}>✓</Text>}
              </View>
              <Text style={styles.choreName}>{c.name}</Text>
              <View style={styles.tagGreen}><Text style={styles.tagGreenText}>+{c.pts} pts</Text></View>
            </View>
          ))}
          <View style={styles.streakBox}>
            <Text style={styles.streakText}>7-day streak bonus unlocked! +20 extra pts</Text>
          </View>
        </View>

        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>My points</Text>
            <Text style={shared.cardAction}>Rewards store</Text>
          </View>
          <View style={styles.pointsHero}>
            <Text style={styles.pointsBig}>{leader.points}</Text>
            <Text style={styles.pointsLabel}>Total points</Text>
          </View>
          <View style={styles.ptsBar}><View style={[styles.ptsFill, { width: `${pct}%` }]} /></View>
          <View style={styles.ptsRange}>
            <Text style={styles.ptsRangeText}>0</Text>
            <Text style={styles.ptsRangeText}>{remaining} more to unlock next reward</Text>
            <Text style={styles.ptsRangeText}>1000</Text>
          </View>
          <Text style={shared.sectionHead}>Recent earnings</Text>
          <View style={styles.earnRow}>
            <Text style={styles.earnLabel}>7-day streak bonus</Text>
            <View style={styles.tagGreen}><Text style={styles.tagGreenText}>+20</Text></View>
          </View>
          <View style={styles.earnRow}>
            <Text style={styles.earnLabel}>All chores today</Text>
            <View style={styles.tagGreen}><Text style={styles.tagGreenText}>+40</Text></View>
          </View>
          <View style={styles.earnRow}>
            <Text style={styles.earnLabel}>Reading — 30 min</Text>
            <View style={styles.tagPurple}><Text style={styles.tagPurpleText}>+15</Text></View>
          </View>
        </View>
      </View>

      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Allowance this week</Text>
          <Text style={shared.cardAction}> </Text>
        </View>
        <View style={styles.allowanceRow}>
          <View style={styles.fullBar}>
            <View style={[styles.fullBarFill, { width: `${(allowance.earned / allowance.max) * 100}%` }]} />
          </View>
          <Text style={styles.allowanceAmount}>${allowance.earned.toFixed(2)} / ${allowance.max.toFixed(2)}</Text>
          <View style={styles.tagGreen}><Text style={styles.tagGreenText}>Full payout!</Text></View>
        </View>
        <Text style={styles.allowanceSub}>Paid to your Greenlight card on Sunday. Keep it up!</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  hero: { alignItems: "center", paddingVertical: 16, gap: 8 },
  bigAv: { width: 72, height: 72, borderRadius: 36, alignItems: "center", justifyContent: "center" },
  bigAvText: { fontSize: 28, fontWeight: "600", fontFamily: fonts.body },
  heroTitle: { fontSize: 22, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  heroSub: { fontSize: 13, color: colors.muted, fontFamily: fonts.body },
  heroPill: { backgroundColor: colors.greenBg, borderRadius: 14, paddingHorizontal: 16, paddingVertical: 6, marginTop: 4 },
  heroPillText: { fontSize: 12, fontWeight: "600", color: colors.greenText, fontFamily: fonts.body },

  grid2: { flexDirection: "row", gap: 12 },

  choreRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 7,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  check: { width: 18, height: 18, borderRadius: 4, borderWidth: 1.5, borderColor: colors.border, alignItems: "center", justifyContent: "center" },
  checkDone: { backgroundColor: colors.green, borderColor: colors.green },
  checkMark: { color: "#FFFFFF", fontSize: 11, fontWeight: "700" },
  choreName: { flex: 1, fontSize: 13, color: colors.text, fontFamily: fonts.body },

  tagGreen: { backgroundColor: colors.greenBg, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  tagGreenText: { fontSize: 10, fontWeight: "700", color: colors.greenText, fontFamily: fonts.body },
  tagPurple: { backgroundColor: colors.purpleLight, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  tagPurpleText: { fontSize: 10, fontWeight: "700", color: colors.purpleDeep, fontFamily: fonts.body },

  streakBox: { marginTop: 10, backgroundColor: colors.greenBg, borderRadius: 8, padding: 10, alignItems: "center" },
  streakText: { fontSize: 12, color: colors.greenText, fontWeight: "600", fontFamily: fonts.body },

  pointsHero: { alignItems: "center", paddingVertical: 8 },
  pointsBig: { fontSize: 40, fontWeight: "600", color: colors.purple, fontFamily: fonts.mono },
  pointsLabel: { fontSize: 12, color: colors.muted, fontFamily: fonts.body },
  ptsBar: { height: 8, backgroundColor: colors.border, borderRadius: 4, overflow: "hidden", marginVertical: 8 },
  ptsFill: { height: "100%", backgroundColor: colors.purple, borderRadius: 4 },
  ptsRange: { flexDirection: "row", justifyContent: "space-between", marginBottom: 10 },
  ptsRangeText: { fontSize: 10, color: colors.muted, fontFamily: fonts.body },

  earnRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 5,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  earnLabel: { flex: 1, fontSize: 12, color: colors.text, fontFamily: fonts.body },

  allowanceRow: { flexDirection: "row", alignItems: "center", gap: 14, paddingVertical: 4 },
  fullBar: { flex: 1, height: 12, backgroundColor: colors.border, borderRadius: 6, overflow: "hidden" },
  fullBarFill: { height: "100%", backgroundColor: colors.green, borderRadius: 6 },
  allowanceAmount: { fontSize: 16, fontWeight: "600", color: colors.green, fontFamily: fonts.mono },
  allowanceSub: { fontSize: 11, color: colors.muted, marginTop: 6, fontFamily: fonts.body },
});
