/**
 * Admin — Permissions management.
 *
 * Shows the per-member permissions matrix: which tier each member holds,
 * what effective permissions they have, and allows tier reassignment.
 * Reads from GET /admin/permissions/registry + /admin/permissions/members.
 * Writes via PATCH /admin/permissions/members/{id}.
 */

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Redirect } from "expo-router";

import { useAuth } from "../../../lib/auth";
import { useHasPermission } from "../../../lib/permissions";
import { colors, fonts, shared } from "../../../lib/styles";

const API_BASE = process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000";

interface PermissionEntry {
  permission_key: string;
  description: string;
}

interface MemberPermissions {
  member_id: string;
  first_name: string;
  role: string;
  tier_name: string | null;
  tier_id: string | null;
  effective_permissions: Record<string, boolean>;
}

interface TierOption {
  id: string;
  name: string;
}

export default function AdminPermissions() {
  const canManage = useHasPermission("admin.manage_permissions");
  const canView = useHasPermission("admin.view_permissions");
  const { token } = useAuth();

  const [registry, setRegistry] = useState<PermissionEntry[]>([]);
  const [members, setMembers] = useState<MemberPermissions[]>([]);
  const [tiers, setTiers] = useState<TierOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  if (!canView && !canManage) return <Redirect href="/admin" />;

  const headers = useCallback(
    () => ({
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    }),
    [token],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [regRes, memRes] = await Promise.all([
        fetch(`${API_BASE}/admin/permissions/registry`, { headers: headers() }),
        fetch(`${API_BASE}/admin/permissions/members`, { headers: headers() }),
      ]);
      if (!regRes.ok || !memRes.ok) throw new Error("Failed to load permissions data");
      const regData = await regRes.json();
      const memData = await memRes.json();

      setRegistry(Array.isArray(regData) ? regData : regData.permissions ?? []);
      const memberList = Array.isArray(memData) ? memData : memData.members ?? [];
      setMembers(memberList);

      const uniqueTiers = new Map<string, string>();
      for (const m of memberList) {
        if (m.tier_id && m.tier_name) uniqueTiers.set(m.tier_id, m.tier_name);
      }
      if (uniqueTiers.size === 0) {
        try {
          const tiersRes = await fetch(`${API_BASE}/admin/permissions/registry`, { headers: headers() });
          const tiersData = await tiersRes.json();
          if (tiersData.tiers) {
            for (const t of tiersData.tiers) uniqueTiers.set(t.id, t.name);
          }
        } catch { /* silent */ }
      }
      setTiers(Array.from(uniqueTiers, ([id, name]) => ({ id, name })));
    } catch (e: any) {
      setError(e?.message ?? "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [headers]);

  useEffect(() => { load(); }, [load]);

  const changeTier = async (memberId: string, tierId: string) => {
    setSaving(memberId);
    setMsg(null);
    try {
      const res = await fetch(`${API_BASE}/admin/permissions/members/${memberId}`, {
        method: "PATCH",
        headers: headers(),
        body: JSON.stringify({ role_tier_id: tierId }),
      });
      if (!res.ok) throw new Error(`Failed (${res.status})`);
      setMsg("Tier updated");
      await load();
    } catch (e: any) {
      setMsg(e?.message ?? "Update failed");
    } finally {
      setSaving(null);
    }
  };

  if (loading) {
    return (
      <View style={shared.pageCenter}>
        <ActivityIndicator size="large" color={colors.purple} />
      </View>
    );
  }

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Permissions</Text>
      <Text style={styles.intro}>
        Manage role tiers and view effective permissions per family member.
      </Text>

      {error && (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
          <Pressable onPress={load} accessibilityRole="button">
            <Text style={styles.retryText}>Retry</Text>
          </Pressable>
        </View>
      )}

      {msg && <Text style={styles.msg}>{msg}</Text>}

      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Family members</Text>
          <Text style={shared.cardAction}>{members.length} members</Text>
        </View>
        {members.map((m) => (
          <View key={m.member_id} style={styles.memberRow}>
            <View style={styles.memberInfo}>
              <Text style={styles.memberName}>{m.first_name}</Text>
              <Text style={styles.memberMeta}>{m.role} · {m.tier_name ?? "No tier"}</Text>
            </View>
            {canManage && tiers.length > 0 && (
              <View style={styles.tierPills}>
                {tiers.map((t) => {
                  const active = t.id === m.tier_id;
                  const isSaving = saving === m.member_id;
                  return (
                    <Pressable
                      key={t.id}
                      style={[styles.tierPill, active && styles.tierPillActive]}
                      onPress={() => !active && !isSaving && changeTier(m.member_id, t.id)}
                      disabled={active || isSaving}
                      accessibilityRole="button"
                      accessibilityLabel={`Assign ${m.first_name} to ${t.name}`}
                      accessibilityState={{ selected: active }}
                    >
                      <Text style={[styles.tierPillText, active && styles.tierPillTextActive]}>
                        {t.name.replace(/_/g, " ")}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            )}
          </View>
        ))}
      </View>

      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Permission registry</Text>
          <Text style={shared.cardAction}>{registry.length} keys</Text>
        </View>
        {registry.map((p) => (
          <View key={p.permission_key} style={styles.permRow}>
            <Text style={styles.permKey}>{p.permission_key}</Text>
            <Text style={styles.permDesc}>{p.description}</Text>
          </View>
        ))}
        {registry.length === 0 && (
          <Text style={styles.empty}>No permissions found in registry.</Text>
        )}
      </View>

      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Audit log</Text>
          <Text style={shared.cardAction}> </Text>
        </View>
        <Text style={styles.stub}>
          Coming soon — permission change history, tier assignment timeline.
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  h1: { fontSize: 22, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  intro: { fontSize: 13, color: colors.muted, fontFamily: fonts.body, marginBottom: 4 },

  errorBox: {
    backgroundColor: colors.redBg,
    borderRadius: 8,
    padding: 12,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  errorText: { fontSize: 12, color: colors.redText, fontFamily: fonts.body, flex: 1 },
  retryText: { fontSize: 12, color: colors.purple, fontWeight: "600", fontFamily: fonts.body },
  msg: { fontSize: 12, color: colors.green, fontFamily: fonts.body, textAlign: "center" },

  memberRow: {
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: 8,
  },
  memberInfo: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  memberName: { fontSize: 14, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  memberMeta: { fontSize: 11, color: colors.muted, fontFamily: fonts.body },

  tierPills: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  tierPill: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 6,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  tierPillActive: { backgroundColor: colors.purpleLight, borderColor: colors.purpleMid },
  tierPillText: { fontSize: 10, color: colors.muted, fontFamily: fonts.body, fontWeight: "500" },
  tierPillTextActive: { color: colors.purpleDeep, fontWeight: "600" },

  permRow: {
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  permKey: { fontSize: 11, color: colors.text, fontFamily: fonts.mono, fontWeight: "500" },
  permDesc: { fontSize: 11, color: colors.muted, fontFamily: fonts.body, marginTop: 2 },
  empty: { fontSize: 12, color: colors.muted, fontFamily: fonts.body, paddingVertical: 8 },

  stub: { fontSize: 12, color: colors.muted, fontFamily: fonts.body, fontStyle: "italic", paddingVertical: 8 },
});
