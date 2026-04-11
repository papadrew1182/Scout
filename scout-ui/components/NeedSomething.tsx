/**
 * Universal "Need Something?" entry point.
 * Available on Personal, Parent, and Child surfaces.
 * Two actions: Add to Grocery List, Request Purchase.
 */

import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { CURRENT_USER_ID } from "../lib/config";
import { createGroceryItem, createPurchaseRequest } from "../lib/api";
import { colors } from "../lib/styles";

interface Props {
  memberId?: string;
  isChild?: boolean;
  onComplete?: () => void;
}

export function NeedSomething({ memberId, isChild, onComplete }: Props) {
  const [mode, setMode] = useState<null | "grocery" | "purchase">(null);
  const [title, setTitle] = useState("");
  const [quantity, setQuantity] = useState("");
  const [notes, setNotes] = useState("");
  const [details, setDetails] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const actorId = memberId ?? CURRENT_USER_ID;

  const reset = () => {
    setMode(null);
    setTitle("");
    setQuantity("");
    setNotes("");
    setDetails("");
    setMsg(null);
  };

  const handleGrocery = async () => {
    if (!title.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      await createGroceryItem(actorId, {
        title: title.trim(),
        quantity: quantity ? Number(quantity) : undefined,
        notes: notes || undefined,
      });
      setMsg(isChild ? "Added — a parent will review" : "Added to grocery list");
      setTimeout(() => { reset(); onComplete?.(); }, 1500);
    } catch {
      setMsg("Failed to add");
    } finally {
      setBusy(false);
    }
  };

  const handlePurchase = async () => {
    if (!title.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      await createPurchaseRequest(actorId, {
        title: title.trim(),
        details: details || undefined,
        quantity: quantity ? Number(quantity) : undefined,
      });
      setMsg("Request submitted");
      setTimeout(() => { reset(); onComplete?.(); }, 1500);
    } catch {
      setMsg("Failed to submit");
    } finally {
      setBusy(false);
    }
  };

  if (!mode) {
    return (
      <View style={styles.card}>
        <Text style={styles.heading}>Need something?</Text>
        <View style={styles.buttonRow}>
          <Pressable style={styles.optionButton} onPress={() => setMode("grocery")}>
            <Text style={styles.optionText}>Add to Grocery List</Text>
          </Pressable>
          <Pressable style={styles.optionButton} onPress={() => setMode("purchase")}>
            <Text style={styles.optionText}>Request Purchase</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <Text style={styles.heading}>
          {mode === "grocery" ? "Add to Grocery List" : "Request Purchase"}
        </Text>
        <Pressable onPress={reset}>
          <Text style={styles.cancel}>Cancel</Text>
        </Pressable>
      </View>

      {isChild && mode === "grocery" && (
        <Text style={styles.hint}>A parent will review before it's added</Text>
      )}

      <TextInput
        style={styles.input}
        placeholder="Item name"
        placeholderTextColor={colors.textPlaceholder}
        value={title}
        onChangeText={setTitle}
      />
      <TextInput
        style={styles.input}
        placeholder="Quantity (optional)"
        placeholderTextColor={colors.textPlaceholder}
        value={quantity}
        onChangeText={setQuantity}
        keyboardType="numeric"
      />

      {mode === "grocery" && (
        <TextInput
          style={styles.input}
          placeholder="Note (optional)"
          placeholderTextColor={colors.textPlaceholder}
          value={notes}
          onChangeText={setNotes}
        />
      )}

      {mode === "purchase" && (
        <TextInput
          style={[styles.input, { minHeight: 60 }]}
          placeholder="Details / why you need it"
          placeholderTextColor={colors.textPlaceholder}
          value={details}
          onChangeText={setDetails}
          multiline
        />
      )}

      <Pressable
        style={[styles.submitButton, (!title.trim() || busy) && styles.submitDisabled]}
        onPress={mode === "grocery" ? handleGrocery : handlePurchase}
        disabled={!title.trim() || busy}
      >
        {busy ? (
          <ActivityIndicator size="small" color={colors.buttonPrimaryText} />
        ) : (
          <Text style={styles.submitText}>
            {mode === "grocery" ? "Add" : "Submit Request"}
          </Text>
        )}
      </Pressable>

      {msg && <Text style={styles.msg}>{msg}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 16,
    marginBottom: 12,
  },
  heading: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: "600",
    marginBottom: 10,
  },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 10,
  },
  cancel: { color: colors.accent, fontSize: 13, fontWeight: "600" },
  hint: { color: colors.warning, fontSize: 12, marginBottom: 8 },
  buttonRow: { flexDirection: "row", gap: 8 },
  optionButton: {
    flex: 1,
    backgroundColor: colors.surfaceMuted,
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: "center",
  },
  optionText: { color: colors.textPrimary, fontSize: 13, fontWeight: "600" },
  input: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 8,
    padding: 12,
    color: colors.textPrimary,
    fontSize: 14,
    marginBottom: 8,
  },
  submitButton: {
    backgroundColor: colors.buttonPrimary,
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: "center",
    marginTop: 4,
  },
  submitDisabled: { backgroundColor: colors.buttonDisabledBg },
  submitText: { color: colors.buttonPrimaryText, fontSize: 14, fontWeight: "600" },
  msg: { color: colors.textSecondary, fontSize: 12, marginTop: 8 },
});
