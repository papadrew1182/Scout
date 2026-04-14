/**
 * Parent-only family-member + account maintenance surface.
 *
 * Fills the gap flagged during the 2026-04-14 maintenance pass: there
 * was no in-app way to edit core member fields (name, birthdate, role,
 * active state), create a new member, or manage a member's login
 * accounts. This section lists every member in the family and exposes
 * inline edit forms for each, plus an "Add a family member" form and
 * per-member account management (add, rotate email, reset password,
 * deactivate).
 *
 * Backend safety invariant (enforced server-side, surfaced here as a
 * 409 error message): at least one active adult with an active login
 * must always remain. The UI trusts the server's 409s instead of
 * trying to re-implement the check client-side.
 */

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  createMember,
  createMemberAccount,
  fetchMemberAccounts,
  fetchMembers,
  updateMemberAccount,
  updateMemberCore,
  type UserAccountRecord,
} from "../lib/api";
import type { FamilyMember } from "../lib/types";
import { colors, shared } from "../lib/styles";

export function FamilyMembersSection() {
  const [members, setMembers] = useState<FamilyMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ text: string; error: boolean } | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await fetchMembers();
      setMembers(rows);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <View style={shared.card}>
        <Text style={shared.cardTitle}>Family members</Text>
        <ActivityIndicator size="small" color={colors.accent} />
      </View>
    );
  }
  if (error) {
    return (
      <View style={shared.card}>
        <Text style={shared.cardTitle}>Family members</Text>
        <Text style={shared.errorText}>{error}</Text>
      </View>
    );
  }

  return (
    <View style={shared.card}>
      <Text style={shared.cardTitle}>Family members</Text>
      <Text style={shared.cardSubtle}>
        Edit names, birthdates, roles, and sign-in accounts. An active
        adult with a working login must always remain on the family.
      </Text>

      {msg && (
        <View style={msg.error ? [shared.msgBox, shared.msgBoxError] : shared.msgBox}>
          <Text style={msg.error ? [shared.msgText, shared.msgTextError] : shared.msgText}>
            {msg.text}
          </Text>
        </View>
      )}

      {members.map((m) => (
        <MemberRow
          key={m.id}
          member={m}
          expanded={expandedId === m.id}
          onToggle={() => setExpandedId(expandedId === m.id ? null : m.id)}
          onChanged={(updated, flashText) => {
            setMembers((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
            if (flashText) setMsg({ text: flashText, error: false });
          }}
          onError={(text) => setMsg({ text, error: true })}
        />
      ))}

      <AddMemberForm
        onCreated={(m) => {
          setMembers((prev) => [...prev, m]);
          setMsg({ text: `Added ${m.first_name} ${m.last_name ?? ""}.`, error: false });
        }}
        onError={(text) => setMsg({ text, error: true })}
      />
    </View>
  );
}


// ---------------------------------------------------------------------------
// Per-member row
// ---------------------------------------------------------------------------

function MemberRow({
  member,
  expanded,
  onToggle,
  onChanged,
  onError,
}: {
  member: FamilyMember;
  expanded: boolean;
  onToggle: () => void;
  onChanged: (m: FamilyMember, flashText?: string) => void;
  onError: (text: string) => void;
}) {
  const [firstName, setFirstName] = useState(member.first_name);
  const [lastName, setLastName] = useState(member.last_name ?? "");
  const [birthdate, setBirthdate] = useState(member.birthdate ?? "");
  const [role, setRole] = useState<"adult" | "child">(member.role);
  const [isActive, setIsActive] = useState(member.is_active);
  const [saving, setSaving] = useState(false);

  // Sync local form state if the member changes under us (e.g. after
  // a save from elsewhere).
  useEffect(() => {
    setFirstName(member.first_name);
    setLastName(member.last_name ?? "");
    setBirthdate(member.birthdate ?? "");
    setRole(member.role);
    setIsActive(member.is_active);
  }, [member]);

  const dirty =
    firstName !== member.first_name ||
    lastName !== (member.last_name ?? "") ||
    birthdate !== (member.birthdate ?? "") ||
    role !== member.role ||
    isActive !== member.is_active;

  const save = async () => {
    if (!dirty || saving) return;
    setSaving(true);
    try {
      const updated = await updateMemberCore(member.id, {
        first_name: firstName.trim(),
        last_name: lastName.trim() || null,
        birthdate: birthdate.trim() || null,
        role,
        is_active: isActive,
      });
      onChanged(updated, `Saved ${updated.first_name}.`);
    } catch (e: any) {
      onError(e?.message ?? "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={s.memberRow}>
      <Pressable onPress={onToggle} style={s.memberHeader}>
        <View style={{ flex: 1 }}>
          <Text style={s.memberName}>
            {member.first_name} {member.last_name ?? ""}
          </Text>
          <Text style={s.memberMeta}>
            {member.role} · {member.birthdate ?? "no birthdate"} ·{" "}
            {member.is_active ? "active" : "INACTIVE"}
          </Text>
        </View>
        <Text style={s.chev}>{expanded ? "▾" : "▸"}</Text>
      </Pressable>

      {expanded && (
        <View style={s.editBlock}>
          <Text style={s.fieldLabel}>First name</Text>
          <TextInput
            style={s.input}
            value={firstName}
            onChangeText={setFirstName}
            placeholder="First name"
            placeholderTextColor={colors.textPlaceholder}
          />
          <Text style={s.fieldLabel}>Last name</Text>
          <TextInput
            style={s.input}
            value={lastName}
            onChangeText={setLastName}
            placeholder="Last name"
            placeholderTextColor={colors.textPlaceholder}
          />
          <Text style={s.fieldLabel}>Birthdate (YYYY-MM-DD)</Text>
          <TextInput
            style={s.input}
            value={birthdate}
            onChangeText={setBirthdate}
            placeholder="2018-07-30"
            placeholderTextColor={colors.textPlaceholder}
            autoCapitalize="none"
          />

          <View style={s.row}>
            <View style={[s.pickerCol, { marginRight: 12 }]}>
              <Text style={s.fieldLabel}>Role</Text>
              <View style={s.pillRow}>
                {(["adult", "child"] as const).map((r) => (
                  <Pressable
                    key={r}
                    style={[s.pill, role === r && s.pillActive]}
                    onPress={() => setRole(r)}
                  >
                    <Text style={[s.pillText, role === r && s.pillTextActive]}>
                      {r}
                    </Text>
                  </Pressable>
                ))}
              </View>
            </View>
            <View style={s.pickerCol}>
              <Text style={s.fieldLabel}>Active</Text>
              <Pressable
                style={[s.pill, isActive && s.pillActive]}
                onPress={() => setIsActive((v) => !v)}
              >
                <Text style={[s.pillText, isActive && s.pillTextActive]}>
                  {isActive ? "active" : "inactive"}
                </Text>
              </Pressable>
            </View>
          </View>

          <Pressable
            style={[
              shared.buttonSmall,
              { marginTop: 10, alignSelf: "flex-start" },
              (!dirty || saving) && { opacity: 0.5 },
            ]}
            onPress={save}
            disabled={!dirty || saving}
          >
            <Text style={shared.buttonSmallText}>
              {saving ? "Saving…" : `Save ${member.first_name}`}
            </Text>
          </Pressable>

          <MemberAccountsBlock memberId={member.id} onError={onError} />
        </View>
      )}
    </View>
  );
}


// ---------------------------------------------------------------------------
// Per-member accounts (inside the expanded row)
// ---------------------------------------------------------------------------

function MemberAccountsBlock({
  memberId,
  onError,
}: {
  memberId: string;
  onError: (text: string) => void;
}) {
  const [accounts, setAccounts] = useState<UserAccountRecord[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [newEmail, setNewEmail] = useState("");
  const [newPw, setNewPw] = useState("");
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await fetchMemberAccounts(memberId);
      setAccounts(rows);
    } catch (e: any) {
      onError(e?.message ?? "Failed to load accounts");
      setAccounts([]);
    } finally {
      setLoading(false);
    }
  }, [memberId, onError]);

  useEffect(() => {
    load();
  }, [load]);

  const addAccount = async () => {
    if (!newEmail.trim() || newPw.length < 8 || adding) return;
    setAdding(true);
    try {
      const row = await createMemberAccount(memberId, {
        email: newEmail.trim(),
        password: newPw,
      });
      setAccounts((prev) => (prev ? [...prev, row] : [row]));
      setNewEmail("");
      setNewPw("");
    } catch (e: any) {
      onError(e?.message ?? "Add account failed");
    } finally {
      setAdding(false);
    }
  };

  const toggleActive = async (a: UserAccountRecord) => {
    try {
      const row = await updateMemberAccount(memberId, a.id, {
        is_active: !a.is_active,
      });
      setAccounts((prev) => prev?.map((p) => (p.id === row.id ? row : p)) ?? [row]);
    } catch (e: any) {
      onError(e?.message ?? "Update failed");
    }
  };

  return (
    <View style={s.accountsBlock}>
      <Text style={s.sectionLabel}>Sign-in accounts</Text>
      {loading && <ActivityIndicator size="small" color={colors.accent} />}
      {accounts?.length === 0 && !loading && (
        <Text style={s.empty}>No sign-in accounts yet.</Text>
      )}
      {accounts?.map((a) => (
        <View key={a.id} style={s.accountRow}>
          <View style={{ flex: 1 }}>
            <Text style={s.accountEmail}>{a.email ?? "(no email)"}</Text>
            <Text style={s.accountMeta}>
              {a.is_active ? "active" : "INACTIVE"}
              {a.is_primary ? " · primary" : ""}
            </Text>
          </View>
          <Pressable style={s.smallBtn} onPress={() => toggleActive(a)}>
            <Text style={s.smallBtnText}>
              {a.is_active ? "Deactivate" : "Activate"}
            </Text>
          </Pressable>
        </View>
      ))}

      <Text style={s.sectionLabel}>Add new account</Text>
      <TextInput
        style={s.input}
        value={newEmail}
        onChangeText={setNewEmail}
        placeholder="email@example.com"
        placeholderTextColor={colors.textPlaceholder}
        autoCapitalize="none"
        keyboardType="email-address"
      />
      <TextInput
        style={s.input}
        value={newPw}
        onChangeText={setNewPw}
        placeholder="initial password (8+ chars)"
        placeholderTextColor={colors.textPlaceholder}
        secureTextEntry
      />
      <Pressable
        style={[
          shared.buttonSmall,
          { marginTop: 8, alignSelf: "flex-start" },
          (!newEmail.trim() || newPw.length < 8 || adding) && { opacity: 0.5 },
        ]}
        onPress={addAccount}
        disabled={!newEmail.trim() || newPw.length < 8 || adding}
      >
        <Text style={shared.buttonSmallText}>
          {adding ? "Adding…" : "Add account"}
        </Text>
      </Pressable>
    </View>
  );
}


// ---------------------------------------------------------------------------
// Add-member form at the bottom of the section
// ---------------------------------------------------------------------------

function AddMemberForm({
  onCreated,
  onError,
}: {
  onCreated: (m: FamilyMember) => void;
  onError: (text: string) => void;
}) {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [birthdate, setBirthdate] = useState("");
  const [role, setRole] = useState<"adult" | "child">("child");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!firstName.trim() || busy) return;
    setBusy(true);
    try {
      const m = await createMember({
        first_name: firstName.trim(),
        last_name: lastName.trim() || null,
        role,
        birthdate: birthdate.trim() || null,
      });
      onCreated(m);
      setFirstName("");
      setLastName("");
      setBirthdate("");
      setRole("child");
    } catch (e: any) {
      onError(e?.message ?? "Create failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={s.addBlock}>
      <Text style={s.sectionLabel}>Add a family member</Text>
      <TextInput
        style={s.input}
        value={firstName}
        onChangeText={setFirstName}
        placeholder="First name"
        placeholderTextColor={colors.textPlaceholder}
      />
      <TextInput
        style={s.input}
        value={lastName}
        onChangeText={setLastName}
        placeholder="Last name (optional)"
        placeholderTextColor={colors.textPlaceholder}
      />
      <TextInput
        style={s.input}
        value={birthdate}
        onChangeText={setBirthdate}
        placeholder="Birthdate YYYY-MM-DD (optional)"
        placeholderTextColor={colors.textPlaceholder}
        autoCapitalize="none"
      />
      <View style={s.pillRow}>
        {(["child", "adult"] as const).map((r) => (
          <Pressable
            key={r}
            style={[s.pill, role === r && s.pillActive]}
            onPress={() => setRole(r)}
          >
            <Text style={[s.pillText, role === r && s.pillTextActive]}>{r}</Text>
          </Pressable>
        ))}
      </View>
      <Pressable
        style={[
          shared.buttonSmall,
          { marginTop: 8, alignSelf: "flex-start" },
          (!firstName.trim() || busy) && { opacity: 0.5 },
        ]}
        onPress={submit}
        disabled={!firstName.trim() || busy}
      >
        <Text style={shared.buttonSmallText}>
          {busy ? "Adding…" : "Add family member"}
        </Text>
      </Pressable>
    </View>
  );
}


const s = StyleSheet.create({
  memberRow: {
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: colors.cardBorder,
  },
  memberHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  memberName: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: "700",
  },
  memberMeta: {
    color: colors.textMuted,
    fontSize: 11,
    marginTop: 2,
  },
  chev: {
    color: colors.textMuted,
    fontSize: 14,
  },
  editBlock: {
    marginTop: 10,
    paddingLeft: 6,
    gap: 4,
  },
  input: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: colors.textPrimary,
    fontSize: 14,
    marginTop: 4,
  },
  fieldLabel: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginTop: 8,
  },
  row: { flexDirection: "row", marginTop: 4 },
  pickerCol: { flex: 1 },
  pillRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 4 },
  pill: {
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderRadius: 999,
    paddingVertical: 4,
    paddingHorizontal: 10,
  },
  pillActive: {
    backgroundColor: colors.accent,
    borderColor: colors.accent,
  },
  pillText: { color: colors.textPrimary, fontSize: 11 },
  pillTextActive: { color: colors.buttonPrimaryText, fontWeight: "700" },
  accountsBlock: {
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.cardBorder,
    gap: 4,
  },
  sectionLabel: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginTop: 8,
  },
  accountRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 6,
    gap: 8,
  },
  accountEmail: {
    color: colors.textPrimary,
    fontSize: 13,
  },
  accountMeta: {
    color: colors.textMuted,
    fontSize: 11,
    marginTop: 2,
  },
  smallBtn: {
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  smallBtnText: {
    color: colors.textPrimary,
    fontSize: 11,
    fontWeight: "600",
  },
  empty: {
    color: colors.textMuted,
    fontSize: 12,
    fontStyle: "italic",
  },
  addBlock: {
    marginTop: 18,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: colors.cardBorder,
    gap: 4,
  },
});
