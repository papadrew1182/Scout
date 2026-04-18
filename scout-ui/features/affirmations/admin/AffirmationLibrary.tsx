import React, { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { colors, fonts, shared } from "../../../lib/styles";
import {
  AffirmationItem,
  createAffirmation,
  fetchAffirmationLibrary,
  toggleAffirmationActive,
  updateAffirmation,
} from "../../../lib/affirmations";

export function AffirmationLibrary() {
  const [items, setItems] = useState<AffirmationItem[]>([]);
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);

  const load = useCallback(() => {
    fetchAffirmationLibrary(search ? { q: search } : undefined).then(setItems).catch(() => {});
  }, [search]);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async (text: string) => {
    await createAffirmation({ text });
    setCreating(false);
    load();
  };

  const handleToggle = async (id: string, active: boolean) => {
    await toggleAffirmationActive(id, !active);
    load();
  };

  return (
    <View style={{ gap: 12 }}>
      <View style={styles.toolbar}>
        <TextInput
          style={styles.search}
          placeholder="Search affirmations..."
          placeholderTextColor={colors.muted}
          value={search}
          onChangeText={setSearch}
          onSubmitEditing={load}
          accessibilityLabel="Search affirmations"
        />
        <Pressable style={styles.addBtn} onPress={() => setCreating(true)} accessibilityRole="button">
          <Text style={styles.addBtnText}>+ New</Text>
        </Pressable>
      </View>

      {creating && <CreateRow onSave={handleCreate} onCancel={() => setCreating(false)} />}

      {items.map((item) => (
        <View key={item.id} style={[shared.card, styles.row]}>
          {editId === item.id ? (
            <EditRow
              item={item}
              onSave={async (data) => {
                await updateAffirmation(item.id, data);
                setEditId(null);
                load();
              }}
              onCancel={() => setEditId(null)}
            />
          ) : (
            <Pressable onPress={() => setEditId(item.id)} style={{ flex: 1 }}>
              <Text style={styles.rowText} numberOfLines={2}>{item.text}</Text>
              <Text style={styles.rowMeta}>
                {item.category ?? "—"} · {item.tone ?? "—"} · {item.audience_type}
              </Text>
            </Pressable>
          )}
          <Pressable
            onPress={() => handleToggle(item.id, item.active)}
            accessibilityRole="switch"
            accessibilityState={{ checked: item.active }}
            style={[styles.toggle, item.active && styles.toggleActive]}
          >
            <Text style={styles.toggleText}>{item.active ? "✓" : "✗"}</Text>
          </Pressable>
        </View>
      ))}

      {items.length === 0 && (
        <Text style={styles.empty}>No affirmations found.</Text>
      )}
    </View>
  );
}

function CreateRow({ onSave, onCancel }: { onSave: (text: string) => void; onCancel: () => void }) {
  const [text, setText] = useState("");
  return (
    <View style={[shared.card, styles.editRow]}>
      <TextInput
        style={styles.editInput}
        placeholder="Write a new affirmation..."
        placeholderTextColor={colors.muted}
        value={text}
        onChangeText={setText}
        multiline
        accessibilityLabel="New affirmation text"
      />
      <View style={styles.editActions}>
        <Pressable style={styles.saveBtn} onPress={() => text.trim() && onSave(text.trim())}>
          <Text style={styles.saveBtnText}>Save</Text>
        </Pressable>
        <Pressable onPress={onCancel}><Text style={styles.cancelText}>Cancel</Text></Pressable>
      </View>
    </View>
  );
}

function EditRow({
  item,
  onSave,
  onCancel,
}: {
  item: AffirmationItem;
  onSave: (data: Partial<AffirmationItem>) => void;
  onCancel: () => void;
}) {
  const [text, setText] = useState(item.text);
  const [category, setCategory] = useState(item.category ?? "");
  const [tone, setTone] = useState(item.tone ?? "");
  const [audience, setAudience] = useState(item.audience_type);

  return (
    <View style={styles.editRow}>
      <TextInput style={styles.editInput} value={text} onChangeText={setText} multiline accessibilityLabel="Affirmation text" />
      <TextInput style={styles.editInputSmall} value={category} onChangeText={setCategory} placeholder="category" placeholderTextColor={colors.muted} accessibilityLabel="Category" />
      <TextInput style={styles.editInputSmall} value={tone} onChangeText={setTone} placeholder="tone" placeholderTextColor={colors.muted} accessibilityLabel="Tone" />
      <TextInput style={styles.editInputSmall} value={audience} onChangeText={setAudience} placeholder="audience" placeholderTextColor={colors.muted} accessibilityLabel="Audience type" />
      <View style={styles.editActions}>
        <Pressable style={styles.saveBtn} onPress={() => onSave({ text, category: category || undefined, tone: tone || undefined, audience_type: audience })}>
          <Text style={styles.saveBtnText}>Save</Text>
        </Pressable>
        <Pressable onPress={onCancel}><Text style={styles.cancelText}>Cancel</Text></Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  toolbar: { flexDirection: "row", gap: 10, alignItems: "center" },
  search: { flex: 1, borderWidth: 1, borderColor: colors.border, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 8, fontSize: 14, fontFamily: fonts.body, color: colors.text, backgroundColor: colors.card },
  addBtn: { backgroundColor: colors.purple, borderRadius: 8, paddingHorizontal: 14, paddingVertical: 8 },
  addBtnText: { color: "#fff", fontWeight: "600", fontSize: 14, fontFamily: fonts.body },
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 12, paddingHorizontal: 14, gap: 10 },
  rowText: { fontSize: 14, color: colors.text, fontFamily: fonts.body, lineHeight: 20 },
  rowMeta: { fontSize: 12, color: colors.muted, fontFamily: fonts.body, marginTop: 4 },
  toggle: { width: 32, height: 32, borderRadius: 16, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: colors.border },
  toggleActive: { backgroundColor: colors.greenBg, borderColor: colors.green },
  toggleText: { fontSize: 14 },
  editRow: { gap: 8, flex: 1 },
  editInput: { borderWidth: 1, borderColor: colors.border, borderRadius: 8, padding: 10, fontSize: 14, fontFamily: fonts.body, color: colors.text, minHeight: 60 },
  editInputSmall: { borderWidth: 1, borderColor: colors.border, borderRadius: 8, padding: 8, fontSize: 13, fontFamily: fonts.body, color: colors.text },
  editActions: { flexDirection: "row", gap: 12, alignItems: "center" },
  saveBtn: { backgroundColor: colors.purple, borderRadius: 8, paddingHorizontal: 14, paddingVertical: 8 },
  saveBtnText: { color: "#fff", fontWeight: "600", fontSize: 13, fontFamily: fonts.body },
  cancelText: { color: colors.muted, fontSize: 13, fontFamily: fonts.body },
  empty: { fontSize: 14, color: colors.muted, fontFamily: fonts.body, textAlign: "center", paddingVertical: 20 },
});
