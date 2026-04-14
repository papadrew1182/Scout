/**
 * Settings — My Account + Accounts & Access (adults only)
 */

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { useAuth } from "../../lib/auth";
import { API_BASE_URL } from "../../lib/config";
import {
  fetchAISettings,
  fetchMembers,
  updateAISettings,
  updateMemberLearning,
} from "../../lib/api";
import type { FamilyAISettings, FamilyMember } from "../../lib/types";
import { shared, colors } from "../../lib/styles";

// ---------------------------------------------------------------------------
// API helpers (settings-specific, use auth token)
// ---------------------------------------------------------------------------

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

async function api(method: string, path: string, token: string, body?: unknown) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: authHeaders(token),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Request failed (${res.status})`);
  }
  if (res.status === 204) return null;
  return res.json();
}

// ---------------------------------------------------------------------------
// Password change form
// ---------------------------------------------------------------------------

function PasswordChangeForm() {
  const { token } = useAuth();
  const [current, setCurrent] = useState("");
  const [newPass, setNewPass] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ text: string; error: boolean } | null>(null);

  const submit = async () => {
    if (!current || !newPass || newPass.length < 6 || !token) return;
    setBusy(true);
    setMsg(null);
    try {
      await api("POST", "/api/auth/password/change", token, {
        current_password: current,
        new_password: newPass,
      });
      setMsg({ text: "Password changed.", error: false });
      setCurrent("");
      setNewPass("");
    } catch {
      setMsg({ text: "Failed. Check your current password.", error: true });
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={shared.card}>
      <Text style={shared.cardTitle}>Change Password</Text>
      <TextInput
        style={s.input}
        value={current}
        onChangeText={setCurrent}
        placeholder="Current password"
        placeholderTextColor={colors.textPlaceholder}
        secureTextEntry
      />
      <TextInput
        style={s.input}
        value={newPass}
        onChangeText={setNewPass}
        placeholder="New password (min 6 chars)"
        placeholderTextColor={colors.textPlaceholder}
        secureTextEntry
      />
      {msg && (
        <Text style={msg.error ? shared.errorText : s.successText}>{msg.text}</Text>
      )}
      <Pressable
        style={[shared.button, (!current || newPass.length < 6 || busy) && shared.buttonDisabled]}
        onPress={submit}
        disabled={!current || newPass.length < 6 || busy}
      >
        <Text style={shared.buttonText}>{busy ? "Saving..." : "Change Password"}</Text>
      </Pressable>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Session management
// ---------------------------------------------------------------------------

function SessionSection() {
  const { token } = useAuth();
  const [sessions, setSessions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await api("GET", "/api/auth/sessions", token);
      setSessions(data || []);
    } catch { /* ignore */ }
    setLoading(false);
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const revokeOthers = async () => {
    if (!token) return;
    setMsg(null);
    try {
      const r = await api("POST", "/api/auth/sessions/revoke-others", token);
      setMsg(`Revoked ${r.revoked} other session(s).`);
      load();
    } catch {
      setMsg("Failed to revoke sessions.");
    }
  };

  return (
    <View style={shared.card}>
      <Text style={shared.cardTitle}>Active Sessions</Text>
      {loading && <ActivityIndicator size="small" color={colors.accent} />}
      {!loading && <Text style={shared.cardSubtle}>{sessions.length} active session(s)</Text>}
      {msg && <Text style={s.successText}>{msg}</Text>}
      <Pressable style={[shared.buttonSmall, { marginTop: 12 }]} onPress={revokeOthers}>
        <Text style={shared.buttonSmallText}>Sign Out Other Sessions</Text>
      </Pressable>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Account management (adults only)
// ---------------------------------------------------------------------------

interface AccountInfo {
  member_id: string;
  first_name: string;
  last_name: string | null;
  role: string;
  is_active: boolean;
  has_account: boolean;
  account_id: string | null;
  email: string | null;
  account_active: boolean | null;
  last_login_at: string | null;
  active_sessions: number;
}

function AccountsSection() {
  const { token } = useAuth();
  const [accounts, setAccounts] = useState<AccountInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<{ text: string; error: boolean } | null>(null);

  // Create account form
  const [createFor, setCreateFor] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  // Reset password form
  const [resetFor, setResetFor] = useState<string | null>(null);
  const [resetPass, setResetPass] = useState("");

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await api("GET", "/api/auth/accounts", token);
      setAccounts(data || []);
    } catch { /* ignore */ }
    setLoading(false);
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const createAccount = async () => {
    if (!token || !createFor || !email || password.length < 6) return;
    setBusy(true);
    setMsg(null);
    try {
      await api("POST", "/api/auth/accounts", token, {
        family_member_id: createFor,
        email,
        password,
      });
      setMsg({ text: "Account created.", error: false });
      setCreateFor(null);
      setEmail("");
      setPassword("");
      load();
    } catch {
      setMsg({ text: "Failed to create account.", error: true });
    } finally {
      setBusy(false);
    }
  };

  const resetPassword = async () => {
    if (!token || !resetFor || resetPass.length < 6) return;
    setBusy(true);
    setMsg(null);
    try {
      await api("POST", `/api/auth/accounts/${resetFor}/reset-password`, token, {
        account_id: resetFor,
        new_password: resetPass,
      });
      setMsg({ text: "Password reset.", error: false });
      setResetFor(null);
      setResetPass("");
    } catch {
      setMsg({ text: "Failed to reset password.", error: true });
    } finally {
      setBusy(false);
    }
  };

  const toggleActive = async (accountId: string, isActive: boolean) => {
    if (!token) return;
    setMsg(null);
    try {
      await api("POST", `/api/auth/accounts/${accountId}/${isActive ? "deactivate" : "activate"}`, token);
      setMsg({ text: isActive ? "Account deactivated." : "Account activated.", error: false });
      load();
    } catch {
      setMsg({ text: "Failed.", error: true });
    }
  };

  const revokeSessions = async (accountId: string) => {
    if (!token) return;
    setMsg(null);
    try {
      await api("POST", `/api/auth/accounts/${accountId}/revoke-sessions`, token);
      setMsg({ text: "Sessions revoked.", error: false });
      load();
    } catch {
      setMsg({ text: "Failed.", error: true });
    }
  };

  if (loading) {
    return (
      <View style={shared.card}>
        <Text style={shared.cardTitle}>Accounts & Access</Text>
        <ActivityIndicator size="small" color={colors.accent} />
      </View>
    );
  }

  return (
    <>
      <Text style={shared.sectionTitle}>Accounts & Access</Text>
      {msg && (
        <View style={msg.error ? [shared.msgBox, shared.msgBoxError] : shared.msgBox}>
          <Text style={msg.error ? [shared.msgText, shared.msgTextError] : shared.msgText}>{msg.text}</Text>
        </View>
      )}

      {accounts.map((a) => (
        <View key={a.member_id} style={shared.card}>
          <View style={shared.cardRow}>
            <Text style={shared.cardTitle}>{a.first_name} {a.last_name || ""}</Text>
            <Text style={s.roleBadge}>{a.role}</Text>
          </View>
          {a.has_account ? (
            <>
              <Text style={shared.cardSubtle}>{a.email}</Text>
              <Text style={shared.cardSubtle}>
                {a.account_active ? "Active" : "Deactivated"}
                {a.active_sessions > 0 ? ` · ${a.active_sessions} session(s)` : ""}
                {a.last_login_at ? ` · Last login ${new Date(a.last_login_at).toLocaleDateString()}` : ""}
              </Text>
              <View style={shared.buttonRow}>
                <Pressable style={shared.buttonSmall} onPress={() => { setResetFor(a.account_id); setResetPass(""); }}>
                  <Text style={shared.buttonSmallText}>Reset Password</Text>
                </Pressable>
                <Pressable style={shared.buttonSmall} onPress={() => toggleActive(a.account_id!, a.account_active!)}>
                  <Text style={shared.buttonSmallText}>{a.account_active ? "Deactivate" : "Activate"}</Text>
                </Pressable>
                {a.active_sessions > 0 && (
                  <Pressable style={shared.buttonSmall} onPress={() => revokeSessions(a.account_id!)}>
                    <Text style={shared.buttonSmallText}>Revoke Sessions</Text>
                  </Pressable>
                )}
              </View>
            </>
          ) : (
            <>
              <Text style={shared.cardSubtle}>No account</Text>
              <Pressable
                style={[shared.buttonSmall, { marginTop: 8 }]}
                onPress={() => { setCreateFor(a.member_id); setEmail(""); setPassword(""); }}
              >
                <Text style={shared.buttonSmallText}>Create Account</Text>
              </Pressable>
            </>
          )}
        </View>
      ))}

      {/* Create account modal inline */}
      {createFor && (
        <View style={shared.card}>
          <Text style={shared.cardTitle}>Create Account</Text>
          <Text style={shared.cardSubtle}>
            For: {accounts.find((a) => a.member_id === createFor)?.first_name}
          </Text>
          <TextInput style={s.input} value={email} onChangeText={setEmail} placeholder="Email" placeholderTextColor={colors.textPlaceholder} autoCapitalize="none" keyboardType="email-address" />
          <TextInput style={s.input} value={password} onChangeText={setPassword} placeholder="Password (min 6)" placeholderTextColor={colors.textPlaceholder} secureTextEntry />
          <View style={{ flexDirection: "row", gap: 8, marginTop: 8 }}>
            <Pressable style={shared.button} onPress={createAccount} disabled={busy || !email || password.length < 6}>
              <Text style={shared.buttonText}>{busy ? "Creating..." : "Create"}</Text>
            </Pressable>
            <Pressable style={[shared.button, s.cancelBtn]} onPress={() => setCreateFor(null)}>
              <Text style={shared.buttonText}>Cancel</Text>
            </Pressable>
          </View>
        </View>
      )}

      {/* Reset password modal inline */}
      {resetFor && (
        <View style={shared.card}>
          <Text style={shared.cardTitle}>Reset Password</Text>
          <TextInput style={s.input} value={resetPass} onChangeText={setResetPass} placeholder="New password (min 6)" placeholderTextColor={colors.textPlaceholder} secureTextEntry />
          <View style={{ flexDirection: "row", gap: 8, marginTop: 8 }}>
            <Pressable style={shared.button} onPress={resetPassword} disabled={busy || resetPass.length < 6}>
              <Text style={shared.buttonText}>{busy ? "Resetting..." : "Reset"}</Text>
            </Pressable>
            <Pressable style={[shared.button, s.cancelBtn]} onPress={() => setResetFor(null)}>
              <Text style={shared.buttonText}>Cancel</Text>
            </Pressable>
          </View>
        </View>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function SettingsPage() {
  const { member, logout } = useAuth();
  const isAdult = member?.role === "adult";

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={shared.pageContent}>
      <View style={shared.headerBlock}>
        <Text style={shared.headerEyebrow}>Settings</Text>
        <Text style={shared.headerTitle}>My Account</Text>
        <Text style={shared.headerSubtitle}>
          {member?.first_name} · {member?.role} · {member?.family_name}
        </Text>
      </View>

      <PasswordChangeForm />
      <SessionSection />

      <Pressable style={[shared.button, s.logoutBtn]} onPress={logout}>
        <Text style={shared.buttonText}>Sign Out</Text>
      </Pressable>

      {isAdult && <AIChatSection />}
      {isAdult && <AccountsSection />}
    </ScrollView>
  );
}

// ---------------------------------------------------------------------------
// AI Chat settings (adult-only)
// ---------------------------------------------------------------------------

function AIChatSection() {
  const [settings, setSettings] = useState<FamilyAISettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ text: string; error: boolean } | null>(null);
  const [homeInput, setHomeInput] = useState("");
  const [children, setChildren] = useState<FamilyMember[]>([]);
  const [kidDrafts, setKidDrafts] = useState<
    Record<string, { grade_level: string; learning_notes: string; personality_notes: string }>
  >({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, members] = await Promise.all([fetchAISettings(), fetchMembers()]);
      setSettings(s);
      setHomeInput(s.home_location ?? "");
      const kids = members.filter((m) => m.role === "child");
      setChildren(kids);
      const drafts: Record<
        string,
        { grade_level: string; learning_notes: string; personality_notes: string }
      > = {};
      for (const k of kids) {
        drafts[k.id] = {
          grade_level: k.grade_level ?? "",
          learning_notes: k.learning_notes ?? "",
          personality_notes: k.personality_notes ?? "",
        };
      }
      setKidDrafts(drafts);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load AI settings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const toggleGeneral = async () => {
    if (!settings) return;
    try {
      const next = await updateAISettings({
        allow_general_chat: !settings.allow_general_chat,
      });
      setSettings(next);
      setMsg({ text: "General chat updated.", error: false });
    } catch {
      setMsg({ text: "Failed to update general chat.", error: true });
    }
  };

  const toggleHomework = async () => {
    if (!settings) return;
    try {
      const next = await updateAISettings({
        allow_homework_help: !settings.allow_homework_help,
      });
      setSettings(next);
      setMsg({ text: "Homework help updated.", error: false });
    } catch {
      setMsg({ text: "Failed to update homework help.", error: true });
    }
  };

  const saveHome = async () => {
    try {
      const next = await updateAISettings({ home_location: homeInput });
      setSettings(next);
      setMsg({ text: "Home location saved.", error: false });
    } catch {
      setMsg({ text: "Failed to save home location.", error: true });
    }
  };

  const saveKid = async (childId: string) => {
    const draft = kidDrafts[childId];
    if (!draft) return;
    try {
      const updated = await updateMemberLearning(childId, {
        grade_level: draft.grade_level || null,
        learning_notes: draft.learning_notes || null,
        personality_notes: draft.personality_notes || null,
      });
      setChildren((prev) => prev.map((c) => (c.id === childId ? updated : c)));
      setMsg({ text: `Saved learning info for ${updated.first_name}.`, error: false });
    } catch {
      setMsg({ text: "Failed to save.", error: true });
    }
  };

  const toggleKidReadAloud = async (childId: string) => {
    const current = children.find((c) => c.id === childId);
    if (!current) return;
    try {
      const updated = await updateMemberLearning(childId, {
        read_aloud_enabled: !current.read_aloud_enabled,
      });
      setChildren((prev) => prev.map((c) => (c.id === childId ? updated : c)));
      setMsg({
        text: `Read-aloud ${updated.read_aloud_enabled ? "on" : "off"} for ${updated.first_name}.`,
        error: false,
      });
    } catch {
      setMsg({ text: "Failed to update read-aloud.", error: true });
    }
  };

  if (loading) {
    return (
      <View style={shared.card}>
        <Text style={shared.cardTitle}>Scout AI</Text>
        <ActivityIndicator size="small" color={colors.accent} />
      </View>
    );
  }
  if (error || !settings) {
    return (
      <View style={shared.card}>
        <Text style={shared.cardTitle}>Scout AI</Text>
        <Text style={[shared.cardSubtle, { color: colors.negative }]}>
          {error ?? "Failed to load"}
        </Text>
      </View>
    );
  }

  return (
    <>
      <Text style={shared.sectionTitle}>Scout AI</Text>
      {msg && (
        <View style={msg.error ? [shared.msgBox, shared.msgBoxError] : shared.msgBox}>
          <Text style={msg.error ? [shared.msgText, shared.msgTextError] : shared.msgText}>
            {msg.text}
          </Text>
        </View>
      )}

      <View style={shared.card}>
        <Text style={shared.cardTitle}>Chat mode</Text>
        <Text style={shared.cardSubtle}>
          Scout AI can answer general questions, help with homework, and have
          friendly conversations in addition to family operations. Toggle these
          if you want a more focused or a more open assistant.
        </Text>

        <Pressable
          style={[s.toggleRow, !settings.allow_general_chat && s.toggleRowOff]}
          onPress={toggleGeneral}
        >
          <View style={{ flex: 1 }}>
            <Text style={s.toggleLabel}>Allow general chat</Text>
            <Text style={shared.cardSubtle}>
              Q&amp;A, explanations, creative writing, coding help (adults &amp; kids).
            </Text>
          </View>
          <Text style={s.toggleState}>
            {settings.allow_general_chat ? "ON" : "OFF"}
          </Text>
        </Pressable>

        <Pressable
          style={[s.toggleRow, !settings.allow_homework_help && s.toggleRowOff]}
          onPress={toggleHomework}
        >
          <View style={{ flex: 1 }}>
            <Text style={s.toggleLabel}>Allow homework help (kids)</Text>
            <Text style={shared.cardSubtle}>
              Socratic tutoring — Scout walks through reasoning, doesn&apos;t
              just give answers.
            </Text>
          </View>
          <Text style={s.toggleState}>
            {settings.allow_homework_help ? "ON" : "OFF"}
          </Text>
        </Pressable>
      </View>

      <View style={shared.card}>
        <Text style={shared.cardTitle}>Home location</Text>
        <Text style={shared.cardSubtle}>
          Used by the weather tool and other location-aware helpers. A zip
          code or &quot;City, State&quot; works best.
        </Text>
        <TextInput
          style={s.input}
          value={homeInput}
          onChangeText={setHomeInput}
          placeholder="e.g. 76126 or Fort Worth, TX"
          placeholderTextColor={colors.textPlaceholder}
        />
        <Pressable style={[shared.buttonSmall, { marginTop: 8 }]} onPress={saveHome}>
          <Text style={shared.buttonSmallText}>Save</Text>
        </Pressable>
      </View>

      {children.length > 0 && (
        <View style={shared.card}>
          <Text style={shared.cardTitle}>Per-child learning context</Text>
          <Text style={shared.cardSubtle}>
            Optional. Scout uses these to tune its tone and explanations when
            kids ask for help. Notes are private to the family and visible
            only inside Scout&apos;s prompt.
          </Text>

          {children.map((kid) => {
            const draft = kidDrafts[kid.id] ?? {
              grade_level: "",
              learning_notes: "",
              personality_notes: "",
            };
            return (
              <View key={kid.id} style={s.kidBlock}>
                <Text style={s.kidName}>{kid.first_name}</Text>
                <TextInput
                  style={s.input}
                  value={draft.grade_level}
                  onChangeText={(t) =>
                    setKidDrafts((prev) => ({
                      ...prev,
                      [kid.id]: { ...prev[kid.id], grade_level: t },
                    }))
                  }
                  placeholder="Grade (e.g. K, 3rd, 8th)"
                  placeholderTextColor={colors.textPlaceholder}
                />
                <Text style={s.fieldLabel}>Learning context</Text>
                <TextInput
                  style={[s.input, { minHeight: 60 }]}
                  value={draft.learning_notes}
                  onChangeText={(t) =>
                    setKidDrafts((prev) => ({
                      ...prev,
                      [kid.id]: { ...prev[kid.id], learning_notes: t },
                    }))
                  }
                  placeholder="Strengths, struggles, reading level, IEP accommodations…"
                  placeholderTextColor={colors.textPlaceholder}
                  multiline
                />
                <Text style={s.fieldLabel}>How to talk to them</Text>
                <TextInput
                  style={[s.input, { minHeight: 60 }]}
                  value={draft.personality_notes}
                  onChangeText={(t) =>
                    setKidDrafts((prev) => ({
                      ...prev,
                      [kid.id]: { ...prev[kid.id], personality_notes: t },
                    }))
                  }
                  placeholder="Tone, encouragement style, how Scout should handle frustration…"
                  placeholderTextColor={colors.textPlaceholder}
                  multiline
                  maxLength={1000}
                />
                <Pressable
                  style={[shared.buttonSmall, { marginTop: 8, alignSelf: "flex-start" }]}
                  onPress={() => saveKid(kid.id)}
                >
                  <Text style={shared.buttonSmallText}>Save {kid.first_name}</Text>
                </Pressable>

                <Pressable
                  style={[s.toggleRow, !kid.read_aloud_enabled && s.toggleRowOff]}
                  onPress={() => toggleKidReadAloud(kid.id)}
                >
                  <View style={{ flex: 1 }}>
                    <Text style={s.toggleLabel}>Read answers aloud</Text>
                    <Text style={shared.cardSubtle}>
                      Scout speaks replies with the browser voice on this
                      child&apos;s surface. Early readers love it.
                    </Text>
                  </View>
                  <Text style={s.toggleState}>
                    {kid.read_aloud_enabled ? "ON" : "OFF"}
                  </Text>
                </Pressable>
              </View>
            );
          })}
        </View>
      )}
    </>
  );
}

const s = StyleSheet.create({
  input: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: colors.textPrimary,
    fontSize: 14,
    marginTop: 8,
  },
  successText: {
    color: colors.positive,
    fontSize: 13,
    marginTop: 8,
  },
  roleBadge: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  logoutBtn: {
    backgroundColor: colors.surfaceMuted,
    marginTop: 24,
  },
  cancelBtn: {
    backgroundColor: colors.surfaceMuted,
  },
  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 12,
    paddingHorizontal: 4,
    borderTopWidth: 1,
    borderTopColor: colors.cardBorder,
  },
  toggleRowOff: {
    opacity: 0.6,
  },
  toggleLabel: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: "600",
  },
  toggleState: {
    color: colors.accent,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  kidBlock: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.cardBorder,
  },
  kidName: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 4,
  },
  fieldLabel: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginTop: 10,
  },
});
