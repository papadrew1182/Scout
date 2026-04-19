import React, { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, fonts, shared } from "../../../lib/styles";
import { fetchMembers, fetchMemberConfig, putMemberConfig } from "../../../lib/api";
import type { FamilyMember } from "../../../lib/types";

interface MemberRow {
  member: FamilyMember;
  enabled: boolean;
  hasPrefs: boolean;
}

export function AffirmationTargeting() {
  const [rows, setRows] = useState<MemberRow[]>([]);

  useEffect(() => {
    loadAll();
  }, []);

  const loadAll = async () => {
    try {
      const members = await fetchMembers();
      const result: MemberRow[] = [];
      for (const m of members) {
        try {
          const configs = await fetchMemberConfig(m.id);
          const affPref = configs.find((c) => c.key === "affirmations.preferences");
          const val = affPref?.value as Record<string, unknown> | undefined;
          result.push({
            member: m,
            enabled: val?.enabled !== false,
            hasPrefs: !!val && Object.keys(val).length > 1,
          });
        } catch {
          result.push({ member: m, enabled: true, hasPrefs: false });
        }
      }
      setRows(result);
    } catch {
      // empty state
    }
  };

  const toggle = async (memberId: string, currentEnabled: boolean) => {
    try {
      const configs = await fetchMemberConfig(memberId);
      const existing = configs.find((c) => c.key === "affirmations.preferences");
      const val = (existing?.value as Record<string, unknown>) ?? {};
      await putMemberConfig(memberId, "affirmations.preferences", { ...val, enabled: !currentEnabled });
      loadAll();
    } catch {
      // keep state
    }
  };

  return (
    <View style={[shared.card, { padding: 16 }]}>
      <View style={styles.headerRow}>
        <Text style={[styles.headerCell, { flex: 2 }]}>Member</Text>
        <Text style={styles.headerCell}>Role</Text>
        <Text style={styles.headerCell}>Enabled</Text>
        <Text style={styles.headerCell}>Prefs</Text>
      </View>
      {rows.map((r) => (
        <View key={r.member.id} style={styles.row}>
          <Text style={[styles.cell, { flex: 2 }]}>{r.member.first_name}</Text>
          <Text style={styles.cell}>{r.member.role}</Text>
          <Pressable
            onPress={() => toggle(r.member.id, r.enabled)}
            accessibilityRole="switch"
            accessibilityState={{ checked: r.enabled }}
            style={[styles.toggleBtn, r.enabled && styles.toggleBtnActive]}
          >
            <Text style={styles.toggleText}>{r.enabled ? "✓" : "✗"}</Text>
          </Pressable>
          <Text style={styles.cell}>{r.hasPrefs ? "set" : "—"}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  headerRow: { flexDirection: "row", paddingBottom: 8, borderBottomWidth: 1, borderBottomColor: colors.border },
  headerCell: { flex: 1, fontSize: 12, fontWeight: "600", color: colors.muted, fontFamily: fonts.body },
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border },
  cell: { flex: 1, fontSize: 14, color: colors.text, fontFamily: fonts.body },
  toggleBtn: { width: 28, height: 28, borderRadius: 14, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: colors.border },
  toggleBtnActive: { backgroundColor: colors.greenBg, borderColor: colors.green },
  toggleText: { fontSize: 13 },
});
