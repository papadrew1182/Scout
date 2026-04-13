/**
 * Receipt photo → grocery items.
 *
 * Renders a "Scan receipt" button on the grocery page. Tapping opens
 * a file picker (camera on mobile web via `capture="environment"`).
 * After upload the component shows a review modal with each extracted
 * item editable, then bulk-creates grocery rows via the existing
 * createGroceryItem endpoint on confirm.
 *
 * Web-only (document + File API). On native Expo this renders a
 * no-op button that still exists but shows nothing when pressed —
 * a future native pass could swap in expo-image-picker.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { createGroceryItem, extractReceipt, type ReceiptItem } from "../lib/api";
import { colors } from "../lib/styles";

interface Props {
  onAdded?: (count: number) => void;
}

interface DraftItem extends ReceiptItem {
  _id: string;
  selected: boolean;
}

function hasDocument(): boolean {
  return typeof document !== "undefined" && typeof FormData !== "undefined";
}

export function ReceiptCaptureButton({ onAdded }: Props) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<DraftItem[] | null>(null);
  const [addingCount, setAddingCount] = useState(0);

  useEffect(() => {
    if (!hasDocument()) return;
    const el = document.createElement("input");
    el.type = "file";
    el.accept = "image/jpeg,image/png,image/webp";
    el.setAttribute("capture", "environment");
    el.style.display = "none";
    el.onchange = async () => {
      const file = el.files?.[0];
      if (!file) return;
      setBusy(true);
      setError(null);
      setDrafts(null);
      try {
        const res = await extractReceipt(file, file.name);
        if (res.items.length === 0) {
          setError("No items detected. Try a clearer photo.");
        } else {
          setDrafts(
            res.items.map((it, i) => ({
              ...it,
              _id: `draft-${i}`,
              selected: true,
            })),
          );
        }
      } catch (e: any) {
        setError(e?.message || "Upload failed.");
      } finally {
        setBusy(false);
        el.value = "";
      }
    };
    document.body.appendChild(el);
    fileInputRef.current = el;
    return () => {
      try {
        document.body.removeChild(el);
      } catch {}
      fileInputRef.current = null;
    };
  }, []);

  const openPicker = useCallback(() => {
    if (!hasDocument()) {
      setError("Receipt capture requires a browser.");
      return;
    }
    fileInputRef.current?.click();
  }, []);

  const patchDraft = (id: string, patch: Partial<DraftItem>) => {
    setDrafts((prev) => (prev ? prev.map((d) => (d._id === id ? { ...d, ...patch } : d)) : prev));
  };

  const removeDraft = (id: string) => {
    setDrafts((prev) => (prev ? prev.filter((d) => d._id !== id) : prev));
  };

  const confirmAll = async () => {
    if (!drafts) return;
    const toAdd = drafts.filter((d) => d.selected && d.title.trim());
    if (toAdd.length === 0) {
      setError("Nothing selected.");
      return;
    }
    setAddingCount(toAdd.length);
    let added = 0;
    for (const d of toAdd) {
      try {
        await createGroceryItem({
          title: d.title.trim(),
          quantity: d.quantity ?? undefined,
          unit: d.unit ?? undefined,
          category: d.category ?? undefined,
        });
        added += 1;
      } catch {
        // Best-effort — keep going so one bad row doesn't lose the rest.
      }
    }
    setAddingCount(0);
    setDrafts(null);
    onAdded?.(added);
  };

  return (
    <View>
      <Pressable style={styles.btn} onPress={openPicker} disabled={busy}>
        {busy ? (
          <ActivityIndicator size="small" color={colors.buttonPrimaryText} />
        ) : (
          <Text style={styles.btnText}>Scan receipt</Text>
        )}
      </Pressable>

      {error && <Text style={styles.errText}>{error}</Text>}

      {drafts && drafts.length > 0 && (
        <View style={styles.card}>
          <Text style={styles.title}>Review {drafts.length} items</Text>
          <Text style={styles.subtle}>
            Uncheck to skip. Tap a field to edit. Confirm to add to your
            grocery list.
          </Text>
          <ScrollView style={{ maxHeight: 360 }}>
            {drafts.map((d) => (
              <View key={d._id} style={styles.row}>
                <Pressable
                  onPress={() => patchDraft(d._id, { selected: !d.selected })}
                  style={[styles.check, d.selected && styles.checkOn]}
                >
                  {d.selected && <Text style={styles.checkMark}>✓</Text>}
                </Pressable>
                <View style={{ flex: 1 }}>
                  <TextInput
                    style={styles.input}
                    value={d.title}
                    onChangeText={(t) => patchDraft(d._id, { title: t })}
                    placeholder="Item"
                    placeholderTextColor={colors.textPlaceholder}
                  />
                  <View style={{ flexDirection: "row", gap: 8 }}>
                    <TextInput
                      style={[styles.input, { flex: 1 }]}
                      value={d.quantity != null ? String(d.quantity) : ""}
                      onChangeText={(t) => {
                        const n = t.trim() === "" ? null : Number(t);
                        patchDraft(d._id, {
                          quantity: Number.isFinite(n as number) ? (n as number) : null,
                        });
                      }}
                      placeholder="qty"
                      placeholderTextColor={colors.textPlaceholder}
                      keyboardType="numeric"
                    />
                    <TextInput
                      style={[styles.input, { flex: 1 }]}
                      value={d.unit ?? ""}
                      onChangeText={(t) => patchDraft(d._id, { unit: t || null })}
                      placeholder="unit"
                      placeholderTextColor={colors.textPlaceholder}
                    />
                  </View>
                </View>
                <Pressable onPress={() => removeDraft(d._id)} style={styles.remove}>
                  <Text style={styles.removeText}>×</Text>
                </Pressable>
              </View>
            ))}
          </ScrollView>
          <View style={styles.actions}>
            <Pressable style={styles.cancelBtn} onPress={() => setDrafts(null)} disabled={addingCount > 0}>
              <Text style={styles.cancelText}>Cancel</Text>
            </Pressable>
            <Pressable style={styles.confirmBtn} onPress={confirmAll} disabled={addingCount > 0}>
              <Text style={styles.confirmText}>
                {addingCount > 0 ? `Adding ${addingCount}…` : "Add to grocery"}
              </Text>
            </Pressable>
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  btn: {
    backgroundColor: colors.accent,
    borderRadius: 10,
    paddingVertical: 12,
    paddingHorizontal: 16,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 44,
  },
  btnText: { color: colors.buttonPrimaryText, fontSize: 14, fontWeight: "700" },
  errText: {
    color: colors.negative,
    fontSize: 13,
    marginTop: 8,
  },
  card: {
    marginTop: 12,
    padding: 12,
    borderRadius: 12,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    gap: 10,
  },
  title: { color: colors.textPrimary, fontSize: 16, fontWeight: "700" },
  subtle: { color: colors.textMuted, fontSize: 12 },
  row: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.cardBorder,
  },
  check: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: colors.accent,
    marginTop: 6,
    alignItems: "center",
    justifyContent: "center",
  },
  checkOn: { backgroundColor: colors.accent },
  checkMark: { color: colors.buttonPrimaryText, fontSize: 12, fontWeight: "700" },
  input: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    color: colors.textPrimary,
    fontSize: 14,
    marginBottom: 6,
  },
  remove: {
    width: 28,
    height: 28,
    alignItems: "center",
    justifyContent: "center",
  },
  removeText: { color: colors.textMuted, fontSize: 22 },
  actions: { flexDirection: "row", gap: 8, marginTop: 6 },
  cancelBtn: {
    flex: 1,
    backgroundColor: colors.surfaceMuted,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderRadius: 10,
    paddingVertical: 10,
    alignItems: "center",
  },
  cancelText: { color: colors.textPrimary, fontSize: 13, fontWeight: "600" },
  confirmBtn: {
    flex: 1,
    backgroundColor: colors.accent,
    borderRadius: 10,
    paddingVertical: 10,
    alignItems: "center",
  },
  confirmText: { color: colors.buttonPrimaryText, fontSize: 13, fontWeight: "700" },
});
