import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { colors, fonts, shared } from "../../lib/styles";
import { useIsDesktop } from "../../lib/breakpoint";
import { FAMILY, INTEGRATIONS, SCOUT_AI_TOGGLES } from "../../lib/seedData";
import { useAuth } from "../../lib/auth";
import { fetchMemberAccounts, updateMemberAccount } from "../../lib/api";
import { useHasPermission } from "../../lib/permissions";
import { useFamilyConfig } from "../../lib/config";

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

// Display labels for the Scout AI toggles. The on/off state comes from the
// config store; these labels are UI copy and stay hardcoded here.
const AI_TOGGLE_LABELS: Array<{ key: keyof ScoutAIToggles; label: string; sub: string }> = [
  { key: "allow_general_chat",   label: "Allow general chat",    sub: "Q&A, creative writing, coding help" },
  { key: "allow_homework_help",  label: "Homework help (kids)",  sub: "Socratic tutoring — guides, doesn't give answers" },
  { key: "proactive_suggestions", label: "Proactive suggestions", sub: "Scout surfaces ideas without being asked" },
  { key: "push_notifications",   label: "Push notifications",    sub: "Chore reminders, meal alerts, family updates" },
];

interface ScoutAIToggles {
  allow_general_chat: boolean;
  allow_homework_help: boolean;
  proactive_suggestions: boolean;
  push_notifications: boolean;
}

const DEFAULT_AI_TOGGLES: ScoutAIToggles = {
  allow_general_chat: true,
  allow_homework_help: true,
  proactive_suggestions: true,
  push_notifications: true,
};

export default function Settings() {
  const isDesktop = useIsDesktop();
  const { member } = useAuth();
  const canManageAccounts = useHasPermission("family.manage_accounts");
  const canManageAIToggles = useHasPermission("scout_ai.manage_toggles");
  const { value: aiToggles, setValue: setAiToggles, loading: aiLoading } =
    useFamilyConfig<ScoutAIToggles>("scout_ai.toggles", DEFAULT_AI_TOGGLES);
  const andrew = FAMILY[0];
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwBusy, setPwBusy] = useState(false);
  const [pwMsg, setPwMsg] = useState<{ text: string; isError: boolean } | null>(null);

  const handleUpdatePassword = async () => {
    if (!member) {
      setPwMsg({ text: "Not logged in", isError: true });
      return;
    }
    if (!currentPw || currentPw.length === 0) {
      setPwMsg({ text: "Current password required", isError: true });
      return;
    }
    if (newPw.length < 6) {
      setPwMsg({ text: "New password must be at least 6 characters", isError: true });
      return;
    }
    setPwBusy(true);
    try {
      const accounts = await fetchMemberAccounts(member.member_id);
      const primaryAccount = accounts.find((a) => a.is_primary);
      if (!primaryAccount) {
        setPwMsg({ text: "No primary account found", isError: true });
        return;
      }
      await updateMemberAccount(member.member_id, primaryAccount.id, {
        new_password: newPw,
      });
      setPwMsg({ text: "Password updated successfully", isError: false });
      setCurrentPw("");
      setNewPw("");
    } catch (e: any) {
      setPwMsg({ text: e?.message || "Update failed", isError: true });
    } finally {
      setPwBusy(false);
    }
  };

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Settings</Text>

      <View style={[styles.grid2, !isDesktop && styles.grid2Stack]}>
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
            <TextInput
              style={styles.input}
              placeholder="Current password"
              placeholderTextColor={colors.muted}
              secureTextEntry
              value={currentPw}
              onChangeText={setCurrentPw}
              editable={!pwBusy}
            />
            <TextInput
              style={styles.input}
              placeholder="New password (min 6 chars)"
              placeholderTextColor={colors.muted}
              secureTextEntry
              value={newPw}
              onChangeText={setNewPw}
              editable={!pwBusy}
            />
            <Pressable
              style={styles.btnPrimaryFull}
              onPress={handleUpdatePassword}
              disabled={pwBusy}
              accessibilityRole="button"
              accessibilityLabel="Update password"
            >
              <Text style={styles.btnPrimaryText}>{pwBusy ? "Updating…" : "Update password"}</Text>
            </Pressable>
            {pwMsg && (
              <Text style={pwMsg.isError ? styles.pwMsgError : styles.pwMsgSuccess}>
                {pwMsg.text}
              </Text>
            )}
            <Text style={styles.sessionsText}>
              18 active sessions · <Text style={{ color: colors.red }}>Sign out all others</Text>
            </Text>
          </View>

          <View style={shared.card}>
            <View style={shared.cardTitleRow}>
              <Text style={shared.cardTitle}>Family members</Text>
              <Text style={shared.cardAction}> </Text>
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

          {canManageAccounts && (
            <View style={shared.card}>
              <Text style={shared.cardTitle}>Accounts & Access</Text>
              <Text style={styles.accountsBlurb}>
                Manage sign-in methods and session access for family members. Only admins can see this section.
              </Text>
            </View>
          )}
        </View>

        <View style={styles.col}>
          {canManageAIToggles && (
            <View style={shared.card}>
              <Text style={shared.cardTitle}>Scout AI settings</Text>
              {aiLoading ? (
                <ActivityIndicator size="small" color={colors.purple} style={{ marginVertical: 12 }} />
              ) : (
                AI_TOGGLE_LABELS.map((t) => {
                  const on = Boolean(aiToggles[t.key]);
                  return (
                    <View key={t.key} style={styles.toggleRow}>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.toggleLabel}>{t.label}</Text>
                        <Text style={styles.toggleSub}>{t.sub}</Text>
                      </View>
                      <Pressable
                        style={[styles.toggle, on ? styles.toggleOn : styles.toggleOff]}
                        onPress={() => setAiToggles({ ...aiToggles, [t.key]: !on })}
                        accessibilityRole="switch"
                        accessibilityState={{ checked: on }}
                        accessibilityLabel={t.label}
                      >
                        <View style={[styles.toggleKnob, on ? styles.toggleKnobOn : styles.toggleKnobOff]} />
                      </Pressable>
                    </View>
                  );
                })
              )}
            </View>
          )}

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
  grid2Stack: { flexDirection: "column" },
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
  pwMsgSuccess: { fontSize: 12, color: colors.green, fontFamily: fonts.body, marginTop: 8 },
  pwMsgError: { fontSize: 12, color: colors.red, fontFamily: fonts.body, marginTop: 8 },
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
