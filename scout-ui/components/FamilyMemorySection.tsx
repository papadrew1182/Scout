/**
 * Tier 5 F20 — Parent-facing family memory management.
 *
 * Lets parents add, edit the status of, and delete memories from
 * the safe memory layer. Designed to slot into the Settings page
 * alongside the existing AI chat controls. Keeps the UI deliberate:
 * proposed memories need explicit approval, active memories can be
 * archived, and everything is deletable outright.
 *
 * Memory type and scope are exposed as simple dropdowns; freeform
 * editing of the underlying JSON is deliberately NOT exposed.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  createFamilyMemory,
  deleteFamilyMemory,
  fetchFamilyMemories,
  updateFamilyMemory,
  type FamilyMemoryRecord,
} from "../lib/api";
import { colors, shared } from "../lib/styles";

const MEMORY_TYPES = [
  "planning_default",
  "meal_preference",
  "household_preference",
  "communication",
  "other",
] as const;

const SCOPES: FamilyMemoryRecord["scope"][] = ["family", "parent", "child"];

export function FamilyMemorySection() {
  const [items, setItems] = useState<FamilyMemoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const [draftContent, setDraftContent] = useState("");
  const [draftType, setDraftType] = useState<(typeof MEMORY_TYPES)[number]>(
    "planning_default",
  );
  const [draftScope, setDraftScope] = useState<FamilyMemoryRecord["scope"]>(
    "family",
  );
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await fetchFamilyMemories();
      setItems(rows);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const grouped = useMemo(() => {
    const byStatus: Record<string, FamilyMemoryRecord[]> = {
      proposed: [],
      active: [],
      archived: [],
    };
    for (const it of items) {
      (byStatus[it.status] ??= []).push(it);
    }
    return byStatus;
  }, [items]);

  const onAdd = async () => {
    const content = draftContent.trim();
    if (!content) return;
    setBusy(true);
    try {
      const row = await createFamilyMemory({
        memory_type: draftType,
        scope: draftScope,
        content,
      });
      setItems((prev) => [row, ...prev]);
      setDraftContent("");
      setMsg("Memory added.");
    } catch {
      setMsg("Failed to add memory.");
    } finally {
      setBusy(false);
    }
  };

  const onApprove = async (id: string) => {
    try {
      const row = await updateFamilyMemory(id, { status: "active" });
      setItems((prev) => prev.map((p) => (p.id === id ? row : p)));
    } catch {
      setMsg("Approve failed.");
    }
  };

  const onArchive = async (id: string) => {
    try {
      const row = await updateFamilyMemory(id, { status: "archived" });
      setItems((prev) => prev.map((p) => (p.id === id ? row : p)));
    } catch {
      setMsg("Archive failed.");
    }
  };

  const onDelete = async (id: string) => {
    try {
      await deleteFamilyMemory(id);
      setItems((prev) => prev.filter((p) => p.id !== id));
    } catch {
      setMsg("Delete failed.");
    }
  };

  if (loading) {
    return (
      <View style={shared.card}>
        <Text style={shared.cardTitle}>Family memory</Text>
        <ActivityIndicator size="small" color={colors.accent} />
      </View>
    );
  }
  if (error) {
    return (
      <View style={shared.card}>
        <Text style={shared.cardTitle}>Family memory</Text>
        <Text style={shared.errorText}>{error}</Text>
      </View>
    );
  }

  return (
    <View style={shared.card}>
      <Text style={shared.cardTitle}>Family memory</Text>
      <Text style={shared.cardSubtle}>
        Persistent preferences and planning defaults Scout uses when
        drafting meal plans and weekly schedules. This is separate from
        per-child learning and coaching notes.
      </Text>

      {msg && <Text style={s.msg}>{msg}</Text>}

      <View style={s.addBlock}>
        <Text style={s.fieldLabel}>New memory</Text>
        <TextInput
          style={[s.input, { minHeight: 56 }]}
          value={draftContent}
          onChangeText={setDraftContent}
          placeholder="e.g. We shop at H-E-B on Sundays"
          placeholderTextColor={colors.textPlaceholder}
          multiline
          maxLength={2000}
        />
        <View style={s.row}>
          <View style={[s.pickerCol, { marginRight: 6 }]}>
            <Text style={s.fieldLabel}>Type</Text>
            <View style={s.pickerRow}>
              {MEMORY_TYPES.map((t) => (
                <Pressable
                  key={t}
                  style={[s.pill, draftType === t && s.pillActive]}
                  onPress={() => setDraftType(t)}
                >
                  <Text
                    style={[s.pillText, draftType === t && s.pillTextActive]}
                  >
                    {t.replace("_", " ")}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>
        </View>
        <View style={s.row}>
          <View style={s.pickerCol}>
            <Text style={s.fieldLabel}>Scope</Text>
            <View style={s.pickerRow}>
              {SCOPES.map((sc) => (
                <Pressable
                  key={sc}
                  style={[s.pill, draftScope === sc && s.pillActive]}
                  onPress={() => setDraftScope(sc)}
                >
                  <Text
                    style={[s.pillText, draftScope === sc && s.pillTextActive]}
                  >
                    {sc}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>
        </View>

        <Pressable
          style={[shared.buttonSmall, { marginTop: 8, alignSelf: "flex-start" }]}
          onPress={onAdd}
          disabled={busy || !draftContent.trim()}
        >
          <Text style={shared.buttonSmallText}>
            {busy ? "Adding…" : "Add memory"}
          </Text>
        </Pressable>
      </View>

      <MemoryGroup
        title="Proposed (need your approval)"
        rows={grouped.proposed}
        primaryLabel="Approve"
        onPrimary={onApprove}
        onDelete={onDelete}
      />
      <MemoryGroup
        title="Active"
        rows={grouped.active}
        primaryLabel="Archive"
        onPrimary={onArchive}
        onDelete={onDelete}
      />
      <MemoryGroup
        title="Archived"
        rows={grouped.archived}
        primaryLabel={null}
        onPrimary={() => {}}
        onDelete={onDelete}
      />
    </View>
  );
}

function MemoryGroup({
  title,
  rows,
  primaryLabel,
  onPrimary,
  onDelete,
}: {
  title: string;
  rows: FamilyMemoryRecord[];
  primaryLabel: string | null;
  onPrimary: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  if (rows.length === 0) return null;
  return (
    <View style={s.group}>
      <Text style={s.groupTitle}>
        {title} ({rows.length})
      </Text>
      {rows.map((r) => (
        <View key={r.id} style={s.rowItem}>
          <View style={{ flex: 1 }}>
            <Text style={s.rowContent}>{r.content}</Text>
            <Text style={s.rowMeta}>
              {r.memory_type.replace("_", " ")} · {r.scope} · {r.source_kind}
            </Text>
          </View>
          <View style={s.rowActions}>
            {primaryLabel && (
              <Pressable
                style={shared.buttonSmall}
                onPress={() => onPrimary(r.id)}
              >
                <Text style={shared.buttonSmallText}>{primaryLabel}</Text>
              </Pressable>
            )}
            <Pressable style={s.deleteBtn} onPress={() => onDelete(r.id)}>
              <Text style={s.deleteBtnText}>Delete</Text>
            </Pressable>
          </View>
        </View>
      ))}
    </View>
  );
}

const s = StyleSheet.create({
  msg: {
    color: colors.accent,
    fontSize: 12,
    marginTop: 4,
  },
  addBlock: {
    marginTop: 10,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.cardBorder,
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
    marginTop: 6,
  },
  row: { flexDirection: "row", marginTop: 8 },
  pickerCol: { flex: 1 },
  pickerRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 4 },
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
  fieldLabel: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  group: {
    marginTop: 12,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: colors.cardBorder,
  },
  groupTitle: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  rowItem: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 8,
    paddingVertical: 6,
    borderTopWidth: 1,
    borderTopColor: colors.cardBorder,
  },
  rowContent: {
    color: colors.textPrimary,
    fontSize: 13,
    lineHeight: 18,
  },
  rowMeta: {
    color: colors.textMuted,
    fontSize: 10,
    marginTop: 2,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  rowActions: {
    flexDirection: "column",
    gap: 4,
  },
  deleteBtn: {
    borderWidth: 1,
    borderColor: colors.negative,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  deleteBtnText: {
    color: colors.negative,
    fontSize: 11,
    fontWeight: "600",
  },
});
