import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { colors, fonts, shared } from "../../lib/styles";
import { FAMILY, INTEGRATIONS, SCOUT_AI_TOGGLES } from "../../lib/seedData";
import { useAuth } from "../../lib/auth";

const TINT_BG: Record<string, string> = {
  purple: colors.avPurpleBg, teal: colors.avTealBg, amber: colors.avAmberBg, coral: colors.avCoralBg,
};
const TINT_TEXT: Record<string, string> = {
  purple: colors.avPurpleText, teal: colors.avTealText, amber: colors.avAmberText, coral: colors.avCoralText,
};

const INTEGRATION_STATUS = {
  connected:     { dot: colors.green, label: "Connected",     bg: colors.greenBg, fg: colors.greenText },
  needs_reauth:  { dot: colors.amber, label: "Needs reauth",  bg: colors.amberBg, fg: colors.amberText },
  not_connected: { dot: colors.muted, label: "Not connected", bg: "#F3F4F6",      fg: "#6B7280" },
} as const;

const ROLE_TAG = {
  admin: { bg: colors.purpleLight, fg: colors.purpleDeep, label: "Admin" },
  full:  { bg: "#F3F4F6",          fg: "#374151",         label: "Full user" },
  child: { bg: colors.tealBg,      fg: colors.tealText,   label: "Child" },
} as const;

export default function Settings() {
  const [toggles, setToggles] = useState(SCOUT_AI_TOGGLES.map((t) => t.on));
  const { member } = useAuth();
  const isAdult = member?.role === "adult";
  const andrew = FAMILY[0];

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Settings</Text>

      <View style={styles.grid2}>
        <View style={styles.col}>
          <View style={shared.card}>
            <Text style={shared.cardTitle}>My account</Text>
            <View style={styles.accountRow}>
              <View style={[styles.bigAv, { backgroundColor: TINT_BG[andrew.tint] }]}>
                <Text style={[styles.bigAvText, { color: TINT_TEXT[andrew.tint] }]}>{andrew.initials}</Text>
              </View>
              <View>
                <Text style={styles.accountName}>Andrew Roberts</Text>
                <Text style={styles.accountEmail}>Admin · {andrew.email}</Text>
              </View>
            </View>
            <TextInput style={styles.input} placeholder="Current password" placeholderTextColor={colors.muted} secureTextEntry />
            <TextInput style={styles.input} placeholder="New password (min 6 chars)" placeholderTextColor={colors.muted} secureTextEntry />
            <Pressable style={styles.btnPrimaryFull} accessibilityRole="button" accessibilityLabel="Update password"><Text style={styles.btnPrimaryText}>Update password</Text></Pressable>
            <Text style={styles.sessionsText}>
              18 active sessions · <Text style={{ color: colors.red }}>Sign out all others</Text>
            </Text>
          </View>

          <View style={shared.card}>
            <View style={shared.cardTitleRow}>
              <Text style={shared.cardTitle}>Family members</Text>
              <Text style={shared.cardAction}>+ Add member</Text>
            </View>
            {FAMILY.map((m) => {
              const role = ROLE_TAG[m.role];
              return (
                <View key={m.id} style={styles.memberRow}>
                  <View style={[styles.av, { backgroundColor: TINT_BG[m.tint] }]}>
                    <Text style={[styles.avText, { color: TINT_TEXT[m.tint] }]}>{m.initials}</Text>
                  </View>
                  <Text style={styles.memberName}>
                    {m.firstName} {m.lastName}
                    {m.age !== undefined ? ` · ${m.age}` : ""}
                  </Text>
                  <View style={[styles.tag, { backgroundColor: role.bg }]}>
                    <Text style={[styles.tagText, { color: role.fg }]}>{role.label}</Text>
                  </View>
                </View>
              );
            })}
          </View>

          {isAdult && (
            <View style={shared.card}>
              <Text style={shared.cardTitle}>Accounts & Access</Text>
              <Text style={styles.accountsBlurb}>
                Manage sign-in methods and session access for family members. Only admins can see this section.
              </Text>
            </View>
          )}
        </View>

        <View style={styles.col}>
          <View style={shared.card}>
            <Text style={shared.cardTitle}>Scout AI settings</Text>
            {SCOUT_AI_TOGGLES.map((t, i) => (
              <View key={t.label} style={styles.toggleRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.toggleLabel}>{t.label}</Text>
                  <Text style={styles.toggleSub}>{t.sub}</Text>
                </View>
                <Pressable
                  style={[styles.toggle, toggles[i] ? styles.toggleOn : styles.toggleOff]}
                  onPress={() => setToggles((prev) => prev.map((v, j) => (j === i ? !v : v)))}
                  accessibilityRole="switch"
                  accessibilityState={{ checked: toggles[i] }}
                  accessibilityLabel={t.label}
                >
                  <View style={[styles.toggleKnob, toggles[i] ? styles.toggleKnobOn : styles.toggleKnobOff]} />
                </Pressable>
              </View>
            ))}
          </View>

          <View style={shared.card}>
            <Text style={shared.cardTitle}>Connected integrations</Text>
            {INTEGRATIONS.map((it) => {
              const s = INTEGRATION_STATUS[it.status];
              return (
                <View key={it.name} style={styles.integrationRow}>
                  <View style={[styles.statusDot, { backgroundColor: s.dot }]} />
                  <Text style={styles.integrationName}>{it.name}</Text>
                  <View style={[styles.tag, { backgroundColor: s.bg }]}>
                    <Text style={[styles.tagText, { color: s.fg }]}>{s.label}</Text>
                  </View>
                </View>
              );
            })}
          </View>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  h1: { fontSize: 22, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  grid2: { flexDirection: "row", gap: 12, alignItems: "flex-start" },
  col: { flex: 1, gap: 12 },

  accountRow: { flexDirection: "row", alignItems: "center", gap: 14, marginBottom: 14 },
  bigAv: { width: 48, height: 48, borderRadius: 24, alignItems: "center", justifyContent: "center" },
  bigAvText: { fontSize: 16, fontWeight: "600", fontFamily: fonts.body },
  accountName: { fontSize: 14, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  accountEmail: { fontSize: 11, color: colors.muted, fontFamily: fonts.body },

  input: {
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 9,
    fontSize: 12,
    color: colors.text,
    marginBottom: 8,
    fontFamily: fonts.body,
    outlineWidth: 0,
  } as any,
  btnPrimaryFull: {
    backgroundColor: colors.purple,
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: "center",
  },
  btnPrimaryText: { color: "#FFFFFF", fontSize: 12, fontWeight: "500", fontFamily: fonts.body },
  sessionsText: { fontSize: 11, color: colors.muted, marginTop: 12, fontFamily: fonts.body },

  memberRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  av: { width: 28, height: 28, borderRadius: 14, alignItems: "center", justifyContent: "center" },
  avText: { fontSize: 11, fontWeight: "600", fontFamily: fonts.body },
  memberName: { flex: 1, fontSize: 13, color: colors.text, fontFamily: fonts.body },

  tag: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  tagText: { fontSize: 10, fontWeight: "700", fontFamily: fonts.body },

  toggleRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  toggleLabel: { fontSize: 12, fontWeight: "500", color: colors.text, fontFamily: fonts.body },
  toggleSub: { fontSize: 11, color: colors.muted, marginTop: 2, fontFamily: fonts.body },
  toggle: { width: 36, height: 20, borderRadius: 10, padding: 2, justifyContent: "center" },
  toggleOn: { backgroundColor: colors.green },
  toggleOff: { backgroundColor: "#D1D5DB" },
  toggleKnob: { width: 16, height: 16, borderRadius: 8, backgroundColor: "#FFFFFF" },
  toggleKnobOn: { alignSelf: "flex-end" },
  toggleKnobOff: { alignSelf: "flex-start" },

  integrationRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  integrationName: { flex: 1, fontSize: 12, color: colors.text, fontFamily: fonts.body },

  accountsBlurb: {
    fontSize: 12,
    color: colors.muted,
    fontFamily: fonts.body,
    lineHeight: 17,
    marginTop: 4,
  },
});
