import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";

import { colors, fonts, shared } from "../../lib/styles";
import { useIsDesktop } from "../../lib/breakpoint";
import { FAMILY } from "../../lib/seedData";
import { useAuth } from "../../lib/auth";
import { fetchMemberAccounts, updateMemberAccount } from "../../lib/api";
import { useHasPermission } from "../../lib/permissions";

const TINT_BG: Record<string, string> = {
  purple: colors.avPurpleBg, teal: colors.avTealBg, amber: colors.avAmberBg, coral: colors.avCoralBg,
};
const TINT_TEXT: Record<string, string> = {
  purple: colors.avPurpleText, teal: colors.avTealText, amber: colors.avAmberText, coral: colors.avCoralText,
};

export default function Settings() {
  const isDesktop = useIsDesktop();
  const router = useRouter();
  const { member } = useAuth();
  const canManageAccounts = useHasPermission("family.manage_accounts");

  // Check any admin permission for showing the admin link
  const hasAdminAllowance   = useHasPermission("allowance.manage_config");
  const hasAdminChores      = useHasPermission("chores.manage_config");
  const hasAdminGrocery     = useHasPermission("grocery.manage_config");
  const hasAdminMeals       = useHasPermission("meals.manage_config");
  const hasAdminScoutAI     = useHasPermission("scout_ai.manage_toggles");
  const hasAdminFamily      = useHasPermission("family.manage_members");
  const hasAdminPermissions = useHasPermission("admin.manage_permissions");
  const hasAdminConfig      = useHasPermission("admin.manage_config");

  const hasAnyAdmin =
    hasAdminAllowance ||
    hasAdminChores ||
    hasAdminGrocery ||
    hasAdminMeals ||
    hasAdminScoutAI ||
    hasAdminFamily ||
    hasAdminPermissions ||
    hasAdminConfig;

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
          {/* My account — per-user, always shown */}
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

          {/* Accounts & Access — per-user, admin-only */}
          {canManageAccounts && (
            <View style={shared.card}>
              <Text style={shared.cardTitle}>Accounts & Access</Text>
              <Text style={styles.accountsBlurb}>
                Manage sign-in methods and session access for family members. Only admins can see this section.
              </Text>
            </View>
          )}
        </View>

        {/* Admin link — shown only if user holds any admin permission */}
        {hasAnyAdmin && (
          <View style={styles.col}>
            <Pressable
              style={[shared.card, styles.adminLinkCard]}
              onPress={() => router.push("/admin" as any)}
              accessibilityRole="link"
              accessibilityLabel="Go to family and app config"
            >
              <Text style={styles.adminLinkTitle}>Family &amp; app config</Text>
              <Text style={styles.adminLinkDesc}>
                Manage allowance, chores, meals, grocery, Scout AI settings, family members, and integrations.
              </Text>
              <Text style={styles.adminLinkCta}>Open Admin &rarr;</Text>
            </Pressable>
          </View>
        )}
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

  accountsBlurb: {
    fontSize: 12,
    color: colors.muted,
    fontFamily: fonts.body,
    lineHeight: 17,
    marginTop: 4,
  },

  adminLinkCard: {
    paddingVertical: 16,
    paddingHorizontal: 16,
  },
  adminLinkTitle: {
    fontSize: 15,
    fontWeight: "600",
    color: colors.text,
    fontFamily: fonts.body,
  },
  adminLinkDesc: {
    fontSize: 12,
    color: colors.muted,
    fontFamily: fonts.body,
    lineHeight: 17,
    marginTop: 4,
    marginBottom: 10,
  },
  adminLinkCta: {
    fontSize: 13,
    color: colors.purple,
    fontWeight: "600",
    fontFamily: fonts.body,
  },
});
