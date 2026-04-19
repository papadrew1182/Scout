import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { createPersonalTask } from "../../lib/api";
import { useMe } from "../hooks";
import { colors } from "../../lib/styles";

interface Props {
  visible: boolean;
  onClose: () => void;
  onCreated: () => void;
}

export function AddTaskSheet({ visible, onClose, onCreated }: Props) {
  const me = useMe();
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!visible) return null;

  const memberId = me.data?.user.family_member_id;

  const submit = async () => {
    if (!title.trim()) {
      setError("Title is required");
      return;
    }
    if (!memberId) {
      setError("Not signed in");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createPersonalTask({
        title: title.trim(),
        assigned_to: memberId,
        due_at: dueDate.trim() || undefined,
      });
      setTitle("");
      setDueDate("");
      onCreated();
      onClose();
    } catch (e: any) {
      setError(e?.message ?? "Failed to create task");
    } finally {
      setSaving(false);
    }
  };

  return (
    <View
      style={styles.sheet}
      onStartShouldSetResponder={() => true}
      onResponderTerminationRequest={() => false}
    >
      <Text style={styles.sheetTitle}>Add personal task</Text>

      <Text style={styles.label}>Title</Text>
      <TextInput
        style={styles.input}
        value={title}
        onChangeText={setTitle}
        placeholder="What needs to be done?"
        placeholderTextColor={colors.textPlaceholder}
        editable={!saving}
        autoFocus
        accessibilityLabel="Task title"
      />

      <Text style={styles.label}>Due date (optional)</Text>
      <TextInput
        style={styles.input}
        value={dueDate}
        onChangeText={setDueDate}
        placeholder="YYYY-MM-DD or YYYY-MM-DDTHH:MM"
        placeholderTextColor={colors.textPlaceholder}
        editable={!saving}
        accessibilityLabel="Due date"
      />

      {error && <Text style={styles.error}>{error}</Text>}

      <View style={styles.actions}>
        <Pressable
          style={styles.cancelBtn}
          onPress={onClose}
          disabled={saving}
          accessibilityRole="button"
          accessibilityLabel="Cancel"
        >
          <Text style={styles.cancelText}>Cancel</Text>
        </Pressable>
        <Pressable
          style={[styles.confirmBtn, saving && styles.confirmSaving]}
          onPress={submit}
          disabled={saving || !title.trim()}
          accessibilityRole="button"
          accessibilityLabel="Add task"
        >
          {saving ? (
            <ActivityIndicator size="small" color={colors.buttonPrimaryText} />
          ) : (
            <Text style={styles.confirmText}>Add</Text>
          )}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  sheet: {
    backgroundColor: colors.card,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 18,
    marginTop: 18,
    marginBottom: 12,
  },
  sheetTitle: {
    color: colors.textPrimary,
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 14,
  },
  label: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 1.2,
    marginBottom: 6,
    marginTop: 10,
  },
  input: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 10,
    padding: 12,
    color: colors.textPrimary,
    fontSize: 13,
  },
  error: { color: colors.negative, fontSize: 12, marginTop: 8 },
  actions: { flexDirection: "row", gap: 10, marginTop: 18 },
  cancelBtn: {
    flex: 1,
    backgroundColor: colors.surfaceMuted,
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
  },
  cancelText: { color: colors.textSecondary, fontWeight: "700", fontSize: 13 },
  confirmBtn: {
    flex: 1,
    backgroundColor: colors.accent,
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
  },
  confirmSaving: { backgroundColor: colors.accentLight },
  confirmText: {
    color: colors.buttonPrimaryText,
    fontWeight: "800",
    fontSize: 13,
  },
});
