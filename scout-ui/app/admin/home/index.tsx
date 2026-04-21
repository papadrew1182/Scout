import { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { API_BASE_URL } from "../../../lib/config";
import { colors, fonts, shared } from "../../../lib/styles";
import { useHasPermission } from "../../../lib/permissions";

type Tab = "zones" | "assets" | "templates";

async function apiPost(path: string, body: Record<string, unknown>) {
  const token = typeof localStorage !== "undefined" ? localStorage.getItem("scout_session_token") : null;
  const familyId = typeof localStorage !== "undefined" ? localStorage.getItem("scout_family_id") : null;
  if (!token || !familyId) throw new Error("Not signed in");
  const res = await fetch(`${API_BASE_URL}/families/${familyId}/home/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export default function AdminHome() {
  const canManageZones = useHasPermission("home.manage_zones");
  const canManageAssets = useHasPermission("home.manage_assets");
  const canManageTemplates = useHasPermission("home.manage_templates");
  const [tab, setTab] = useState<Tab>("zones");
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const hasPermission = tab === "zones" ? canManageZones : tab === "assets" ? canManageAssets : canManageTemplates;

  const submit = async () => {
    if (!name.trim()) { setMsg({ kind: "err", text: "Name is required" }); return; }
    setSaving(true); setMsg(null);
    try {
      await apiPost(tab, { name: name.trim() });
      setMsg({ kind: "ok", text: `${tab.slice(0, -1)} created` });
      setName("");
    } catch (e: any) { setMsg({ kind: "err", text: e?.message ?? "Failed" }); }
    finally { setSaving(false); }
  };

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Home Maintenance</Text>

      <View style={styles.tabRow}>
        {(["zones", "assets", "templates"] as Tab[]).map(t => (
          <Pressable key={t} style={[styles.tab, tab === t && styles.tabActive]} onPress={() => { setTab(t); setMsg(null); }} accessibilityRole="button">
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>{t}</Text>
          </Pressable>
        ))}
      </View>

      {!hasPermission ? (
        <Text style={styles.muted}>You do not have permission to manage {tab}.</Text>
      ) : (
        <View style={shared.card}>
          <Text style={styles.label}>Name</Text>
          <TextInput
            style={styles.input}
            value={name}
            onChangeText={setName}
            placeholder={`New ${tab.slice(0, -1)} name`}
            placeholderTextColor={colors.muted}
            editable={!saving}
            accessibilityLabel={`${tab} name`}
          />
          {msg && <Text style={[styles.msg, msg.kind === "err" && styles.msgErr]}>{msg.text}</Text>}
          <Pressable style={[styles.btn, saving && styles.btnDisabled]} onPress={submit} disabled={saving} accessibilityRole="button" accessibilityLabel={`Create ${tab.slice(0, -1)}`}>
            {saving ? <ActivityIndicator size="small" color="#FFFFFF" /> : <Text style={styles.btnText}>Create {tab.slice(0, -1)}</Text>}
          </Pressable>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  h1: { fontSize: 22, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  muted: { fontSize: 13, color: colors.muted, fontFamily: fonts.body },
  tabRow: { flexDirection: "row", gap: 8 },
  tab: { backgroundColor: colors.surfaceMuted, borderRadius: 999, paddingHorizontal: 16, paddingVertical: 8, borderWidth: 1, borderColor: colors.border },
  tabActive: { backgroundColor: colors.purple, borderColor: colors.purple },
  tabText: { fontSize: 12, fontWeight: "600", color: colors.text, fontFamily: fonts.body, textTransform: "capitalize" },
  tabTextActive: { color: "#FFFFFF" },
  label: { fontSize: 11, fontWeight: "700", color: colors.muted, fontFamily: fonts.body, textTransform: "uppercase", letterSpacing: 0.8, marginTop: 10, marginBottom: 6 },
  input: { backgroundColor: colors.surfaceMuted, borderWidth: 1, borderColor: colors.border, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: colors.text, fontFamily: fonts.body },
  msg: { fontSize: 12, color: colors.green, fontFamily: fonts.body, marginTop: 10 },
  msgErr: { color: colors.red },
  btn: { backgroundColor: colors.purple, borderRadius: 10, paddingVertical: 12, alignItems: "center", marginTop: 16 },
  btnDisabled: { backgroundColor: colors.border },
  btnText: { color: "#FFFFFF", fontSize: 13, fontWeight: "600", fontFamily: fonts.body },
});
