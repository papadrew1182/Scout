import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";

import { createEvent } from "../../lib/api";
import { useHasPermission } from "../../lib/permissions";
import { colors } from "../../lib/styles";

interface Props {
  visible: boolean;
  onClose: () => void;
  onCreated: () => void;
}

export function AddEventSheet({ visible, onClose, onCreated }: Props) {
  const canManage = useHasPermission("calendar.manage_self");
  const [title, setTitle] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [allDay, setAllDay] = useState(false);
  const [location, setLocation] = useState("");
  const [hearthVisible, setHearthVisible] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!visible) return null;

  const validate = (): string | null => {
    if (!title.trim()) return "Title is required";
    if (!startsAt.trim()) return "Start time is required";
    if (!endsAt.trim()) return "End time is required";
    const s = new Date(startsAt);
    const e = new Date(endsAt);
    if (isNaN(s.getTime())) return "Invalid start date format";
    if (isNaN(e.getTime())) return "Invalid end date format";
    if (e <= s) return "End must be after start";
    return null;
  };

  const submit = async () => {
    const err = validate();
    if (err) {
      setError(err);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createEvent({
        title: title.trim(),
        starts_at: new Date(startsAt).toISOString(),
        ends_at: new Date(endsAt).toISOString(),
        all_day: allDay,
        location: location.trim() || undefined,
        is_hearth_visible: hearthVisible,
      });
      setTitle("");
      setStartsAt("");
      setEndsAt("");
      setAllDay(false);
      setLocation("");
      setHearthVisible(false);
      onCreated();
      onClose();
    } catch (e: any) {
      setError(e?.message ?? "Failed to create event");
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
      <Text style={styles.sheetTitle}>Add event</Text>

      <Text style={styles.label}>Title</Text>
      <TextInput
        style={styles.input}
        value={title}
        onChangeText={setTitle}
        placeholder="Event name"
        placeholderTextColor={colors.textPlaceholder}
        editable={!saving}
        autoFocus
        accessibilityLabel="Event title"
      />

      <Text style={styles.label}>Start</Text>
      <TextInput
        style={styles.input}
        value={startsAt}
        onChangeText={setStartsAt}
        placeholder="YYYY-MM-DDTHH:MM"
        placeholderTextColor={colors.textPlaceholder}
        editable={!saving}
        accessibilityLabel="Start time"
      />

      <Text style={styles.label}>End</Text>
      <TextInput
        style={styles.input}
        value={endsAt}
        onChangeText={setEndsAt}
        placeholder="YYYY-MM-DDTHH:MM"
        placeholderTextColor={colors.textPlaceholder}
        editable={!saving}
        accessibilityLabel="End time"
      />

      <Text style={styles.label}>Location (optional)</Text>
      <TextInput
        style={styles.input}
        value={location}
        onChangeText={setLocation}
        placeholder="Where?"
        placeholderTextColor={colors.textPlaceholder}
        editable={!saving}
        accessibilityLabel="Location"
      />

      <View style={styles.toggleRow}>
        <Text style={styles.toggleLabel}>All day</Text>
        <Switch
          value={allDay}
          onValueChange={setAllDay}
          disabled={saving}
          accessibilityLabel="All day toggle"
        />
      </View>

      <View style={styles.toggleRow}>
        <Text style={styles.toggleLabel}>Show on Hearth display</Text>
        <Switch
          value={hearthVisible}
          onValueChange={setHearthVisible}
          disabled={saving}
          accessibilityLabel="Hearth visible toggle"
        />
      </View>

      {error && <Text style={styles.error}>{error}</Text>}

      <View style={styles.actions}>
        <Pressable
          style={styles.cancelBtn}
          onPress={onClose}
          disabled={saving}
          accessibilityRole="button"
        >
          <Text style={styles.cancelText}>Cancel</Text>
        </Pressable>
        <Pressable
          style={[styles.confirmBtn, (saving || !canManage) && styles.confirmDisabled]}
          onPress={submit}
          disabled={saving || !canManage}
          accessibilityRole="button"
          accessibilityLabel="Create event"
        >
          {saving ? (
            <ActivityIndicator size="small" color={colors.buttonPrimaryText} />
          ) : (
            <Text style={styles.confirmText}>
              {canManage ? "Create" : "No permission"}
            </Text>
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
  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 12,
    paddingVertical: 6,
  },
  toggleLabel: { color: colors.textPrimary, fontSize: 13, fontWeight: "600" },
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
  confirmDisabled: { backgroundColor: colors.accentLight },
  confirmText: {
    color: colors.buttonPrimaryText,
    fontWeight: "800",
    fontSize: 13,
  },
});
