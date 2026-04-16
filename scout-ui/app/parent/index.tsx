import { ScrollView, StyleSheet, Text, View, Pressable } from "react-native";
import { useEffect, useState } from "react";

import { colors, fonts, shared } from "../../lib/styles";
import { useIsDesktop } from "../../lib/breakpoint";
import { ACTION_INBOX, HOMEWORK, ALLOWANCE, LEADERBOARD, getMember } from "../../lib/seedData";
import { createWeeklyPayout, fetchMembers, PayoutError } from "../../lib/api";
import { calculatePayout } from "../../lib/constants";
import { weekStartStr } from "../../lib/format";
import type { FamilyMember } from "../../lib/types";

const TINT_BG: Record<string, string> = {
  purple: colors.avPurpleBg, teal: colors.avTealBg, amber: colors.avAmberBg, coral: colors.avCoralBg,
};
const TINT_TEXT: Record<string, string> = {
  purple: colors.avPurpleText, teal: colors.avTealText, amber: colors.avAmberText, coral: colors.avCoralText,
};

const INBOX_TONE: Record<string, { bg: string; fg: string; label: string }> = {
  purchase: { bg: colors.amberBg,    fg: colors.amberText,    label: "Purchase" },
  brief:    { bg: colors.purpleLight,fg: colors.purpleDeep,   label: "Brief" },
  chore:    { bg: colors.amberBg,    fg: colors.amberText,    label: "Chore" },
  win:      { bg: colors.greenBg,    fg: colors.greenText,    label: "Win" },
};

export default function Parent() {
  const isDesktop = useIsDesktop();
  const [children, setChildren] = useState<FamilyMember[]>([]);
  const [payoutRan, setPayoutRan] = useState(false);
  const [payoutMsg, setPayoutMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchMembers()
      .then((all) => {
        setChildren(all.filter((m) => m.role === "child" && m.is_active));
      })
      .catch(() => {
        // ignore — the card still renders with the button that will
        // just no-op if no children are loaded
      });
  }, []);

  const handleRunPayouts = async () => {
    if (busy || payoutRan) return;
    setBusy(true);
    setPayoutMsg(null);
    const wStart = weekStartStr();
    const results: string[] = [];
    let hasError = false;
    let allDuplicate = true;

    for (const child of children) {
      const { baseline } = calculatePayout(child.first_name, 0);
      if (baseline === 0) continue;
      try {
        await createWeeklyPayout(child.id, baseline, wStart);
        results.push(`${child.first_name}: payout created`);
        allDuplicate = false;
      } catch (e: any) {
        hasError = true;
        if (e instanceof PayoutError && e.status === 409) {
          results.push(`${child.first_name}: payout already exists for this week`);
        } else {
          results.push(`${child.first_name}: payout failed`);
          allDuplicate = false;
        }
      }
    }

    setPayoutRan(true);
    setBusy(false);
    setPayoutMsg(
      allDuplicate
        ? "Payout already run for this week"
        : results.join("\n") || "No eligible children"
    );
  };

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Parent Dashboard</Text>

      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Weekly payout</Text>
          <Text style={shared.cardAction}> </Text>
        </View>
        <Pressable
          style={[styles.payoutBtn, (busy || payoutRan) && styles.payoutBtnDisabled]}
          onPress={handleRunPayouts}
          disabled={busy || payoutRan}
          accessibilityRole="button"
          accessibilityLabel="Run Weekly Payout"
        >
          <Text style={styles.payoutBtnText}>
            {busy ? "Running…" : payoutRan ? "Payout already run for this week" : "Run Weekly Payout"}
          </Text>
        </Pressable>
        {payoutMsg && <Text style={styles.payoutMsg}>{payoutMsg}</Text>}
      </View>

      <View style={[styles.alert, styles.alertRed]}>
        <Text style={[styles.alertText, { color: colors.redText }]}>
          River (0/3 chores) and Tyler (2/4 chores) are behind. Allowance payout at risk for both.
        </Text>
      </View>
      <View style={[styles.alert, styles.alertAmber]}>
        <Text style={[styles.alertText, { color: colors.amberText }]}>
          1 pending purchase request needs approval · 12 items in action inbox
        </Text>
      </View>

      <View style={[styles.grid2, !isDesktop && styles.grid2Stack]}>
        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Action inbox</Text>
            <View style={styles.countBadge}><Text style={styles.countBadgeText}>12</Text></View>
          </View>
          {ACTION_INBOX.map((item) => {
            const tone = INBOX_TONE[item.kind];
            return (
              <View key={item.title} style={styles.inboxRow}>
                <View style={[styles.inboxTag, { backgroundColor: tone.bg }]}>
                  <Text style={[styles.inboxTagText, { color: tone.fg }]}>{tone.label}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.inboxTitle}>{item.title}</Text>
                  <Text style={styles.inboxSub}>{item.sub}</Text>
                </View>
              </View>
            );
          })}
        </View>

        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Kids homework this week</Text>
            <Text style={shared.cardAction}> </Text>
          </View>
          {HOMEWORK.map((h) => {
            const m = getMember(h.memberId)!;
            return (
              <View key={h.memberId} style={styles.kidRow}>
                <View style={[styles.av, { backgroundColor: TINT_BG[m.tint] }]}>
                  <Text style={[styles.avText, { color: TINT_TEXT[m.tint] }]}>{m.initials}</Text>
                </View>
                <Text style={styles.kidName}>{m.firstName}</Text>
                <Text style={styles.hwMeta}>{h.sessions} sessions · {h.topics}</Text>
                <Tag tone={h.status === "on_track" ? "green" : "amber"}>
                  {h.status === "on_track" ? "On track" : "Low"}
                </Tag>
              </View>
            );
          })}
        </View>
      </View>

      <View style={[styles.grid2, !isDesktop && styles.grid2Stack]}>
        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Allowance this week</Text>
            <Text style={shared.cardAction}>Manage</Text>
          </View>
          {ALLOWANCE.map((a) => {
            const m = getMember(a.memberId)!;
            const pct = a.max === 0 ? 0 : Math.round((a.earned / a.max) * 100);
            const color = pct === 100 ? colors.green : pct >= 50 ? colors.amber : colors.red;
            return (
              <View key={a.memberId} style={styles.kidRow}>
                <View style={[styles.av, { backgroundColor: TINT_BG[m.tint] }]}>
                  <Text style={[styles.avText, { color: TINT_TEXT[m.tint] }]}>{m.initials}</Text>
                </View>
                <Text style={styles.kidName}>{m.firstName}</Text>
                <View style={styles.bar}><View style={[styles.barFill, { width: `${pct}%` }]} /></View>
                <Text style={[styles.allowanceAmount, { color }]}>
                  ${a.earned} / ${a.max}
                </Text>
              </View>
            );
          })}
        </View>

        <View style={shared.card}>
          <View style={shared.cardTitleRow}>
            <Text style={shared.cardTitle}>Points leaderboard · This week</Text>
            <Text style={shared.cardAction}> </Text>
          </View>
          {LEADERBOARD.map((l) => {
            const m = getMember(l.memberId)!;
            const top = LEADERBOARD[0].points;
            const pct = Math.round((l.points / top) * 100);
            return (
              <View key={l.memberId} style={styles.kidRow}>
                <Text style={styles.rank}>{l.rank}</Text>
                <View style={[styles.av, { backgroundColor: TINT_BG[m.tint] }]}>
                  <Text style={[styles.avText, { color: TINT_TEXT[m.tint] }]}>{m.initials}</Text>
                </View>
                <Text style={styles.kidName}>{m.firstName}</Text>
                <View style={styles.bar}><View style={[styles.barFill, { width: `${pct}%` }]} /></View>
                <Text style={styles.pointsText}>{l.points} pts</Text>
              </View>
            );
          })}
        </View>
      </View>
    </ScrollView>
  );
}

function Tag({ tone, children }: { tone: "green" | "amber" | "red"; children: string }) {
  const palette = {
    green: { bg: colors.greenBg, fg: colors.greenText },
    amber: { bg: colors.amberBg, fg: colors.amberText },
    red:   { bg: colors.redBg,   fg: colors.redText },
  }[tone];
  return (
    <View style={[styles.tag, { backgroundColor: palette.bg }]}>
      <Text style={[styles.tagText, { color: palette.fg }]}>{children}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  h1: { fontSize: 22, fontWeight: "600", color: colors.text, fontFamily: fonts.body },

  alert: {
    borderRadius: 8,
    padding: 12,
    borderLeftWidth: 3,
    borderWidth: 1,
  },
  alertRed:   { backgroundColor: colors.redBg,   borderColor: "#FCA5A5", borderLeftColor: colors.red },
  alertAmber: { backgroundColor: colors.amberBg, borderColor: "#FCD34D", borderLeftColor: colors.amber },
  alertText:  { fontSize: 12, lineHeight: 16, fontFamily: fonts.body },

  grid2: { flexDirection: "row", gap: 12 },
  grid2Stack: { flexDirection: "column" },

  countBadge: { backgroundColor: colors.red, borderRadius: 10, paddingHorizontal: 8, paddingVertical: 2 },
  countBadgeText: { color: "#FFFFFF", fontSize: 10, fontWeight: "700", fontFamily: fonts.body },

  inboxRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  inboxTag: { borderRadius: 5, paddingHorizontal: 8, paddingVertical: 2, marginTop: 2 },
  inboxTagText: { fontSize: 9, fontWeight: "700", fontFamily: fonts.body },
  inboxTitle: { fontSize: 12, color: colors.text, fontWeight: "500", fontFamily: fonts.body },
  inboxSub: { fontSize: 11, color: colors.muted, marginTop: 2, fontFamily: fonts.body },

  kidRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  av: { width: 28, height: 28, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  avText: { fontSize: 11, fontWeight: "600", fontFamily: fonts.body },
  kidName: { fontSize: 12, color: colors.text, minWidth: 56, fontFamily: fonts.body },
  hwMeta: { flex: 1, fontSize: 11, color: colors.muted, fontFamily: fonts.body },
  bar: { flex: 1, height: 5, backgroundColor: colors.border, borderRadius: 3, overflow: "hidden" },
  barFill: { height: "100%", backgroundColor: colors.green, borderRadius: 3 },
  allowanceAmount: { fontSize: 12, fontFamily: fonts.mono, fontWeight: "500" },
  rank: { width: 18, textAlign: "center", fontSize: 11, color: colors.muted, fontFamily: fonts.body },
  pointsText: { fontSize: 11, color: colors.text, fontFamily: fonts.mono },

  tag: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  tagText: { fontSize: 10, fontWeight: "700", fontFamily: fonts.body },

  payoutBtn: {
    backgroundColor: colors.purple,
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
  },
  payoutBtnDisabled: { backgroundColor: colors.border },
  payoutBtnText: { color: "#FFFFFF", fontSize: 13, fontWeight: "600", fontFamily: fonts.body },
  payoutMsg: {
    fontSize: 12,
    color: colors.muted,
    fontFamily: fonts.body,
    marginTop: 8,
    lineHeight: 17,
  },
});
