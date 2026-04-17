import { useEffect, useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { colors, fonts, shared } from "../../lib/styles";
import { useIsDesktop } from "../../lib/breakpoint";
import { useFamilyConfig } from "../../lib/config";
import type { GroceryStoreConfig } from "../../lib/grocery";
import { DEFAULT_STORE_CONFIG } from "../../lib/grocery";
import {
  fetchGroceryItems,
  fetchPendingReviewItems,
  fetchPurchaseRequests,
  updateGroceryItem,
  convertPurchaseRequestToGrocery,
  createGroceryItem,
} from "../../lib/api";
import type { GroceryItem, PurchaseRequest } from "../../lib/types";
import { ReceiptCaptureButton } from "../../components/ReceiptCaptureButton";
import { useHasPermission } from "../../lib/permissions";

export default function Grocery() {
  const isDesktop = useIsDesktop();
  const canApproveGrocery = useHasPermission("grocery.approve");
  const canApprovePurchase = useHasPermission("purchase_request.approve");
  const [items, setItems] = useState<GroceryItem[]>([]);
  const [pending, setPending] = useState<GroceryItem[]>([]);
  const [requests, setRequests] = useState<PurchaseRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [addTitle, setAddTitle] = useState("");
  const [addStore, setAddStore] = useState("");
  const [addBusy, setAddBusy] = useState(false);

  // Configured store list — replaces the hardcoded GROCERY from seedData
  const { value: storeConfig } = useFamilyConfig<GroceryStoreConfig>(
    "grocery.stores",
    DEFAULT_STORE_CONFIG,
  );

  const load = async () => {
    try {
      const [allItems, p, r] = await Promise.all([
        fetchGroceryItems(),
        fetchPendingReviewItems(),
        fetchPurchaseRequests("pending"),
      ]);
      setItems(allItems);
      setPending(p);
      setRequests(r);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load");
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleApprove = async (item: GroceryItem) => {
    try {
      await updateGroceryItem(item.id, { approval_status: "active" });
      load();
    } catch (e: any) {
      setError(e?.message ?? "Approve failed");
    }
  };

  const handleConvert = async (req: PurchaseRequest) => {
    try {
      await convertPurchaseRequestToGrocery(req.id);
      load();
    } catch (e: any) {
      setError(e?.message ?? "Convert failed");
    }
  };

  const handleAddItem = async () => {
    if (addTitle.trim().length === 0) {
      setError("Item title required");
      return;
    }
    setAddBusy(true);
    try {
      await createGroceryItem({
        title: addTitle.trim(),
        preferred_store: addStore.trim() || undefined,
      });
      setAddOpen(false);
      setAddTitle("");
      setAddStore("");
      setError(null);
      load();
    } catch (e: any) {
      setError(e?.message ?? "Add failed");
    } finally {
      setAddBusy(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Build per-store cards from configured stores + backend items
  // ---------------------------------------------------------------------------

  // Group items by preferred_store (case-insensitive match against store name)
  const buildStoreCards = () => {
    const configuredStores = storeConfig.stores;

    // Fallback: if no stores configured, render a single catch-all card
    if (configuredStores.length === 0) {
      return [{ storeId: "all", storeName: "Grocery", storeItems: items }];
    }

    // Build a lookup: normalized store name → items
    const byStore = new Map<string, GroceryItem[]>();
    for (const store of configuredStores) {
      byStore.set(store.name.toLowerCase(), []);
    }

    // Assign each item to a store card; unmatched items go to a catch-all bucket
    const unmatched: GroceryItem[] = [];
    for (const item of items) {
      const key = (item.preferred_store ?? "").toLowerCase().trim();
      if (key && byStore.has(key)) {
        byStore.get(key)!.push(item);
      } else {
        unmatched.push(item);
      }
    }

    const cards = configuredStores.map((store) => ({
      storeId: store.id,
      storeName: store.name,
      storeItems: byStore.get(store.name.toLowerCase()) ?? [],
    }));

    // If there are unmatched items append an "Other" card
    if (unmatched.length > 0) {
      cards.push({ storeId: "other", storeName: "Other", storeItems: unmatched });
    }

    return cards;
  };

  const storeCards = buildStoreCards();

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <View style={styles.headerRow}>
        <Text style={styles.h1}>Grocery List</Text>
        <View style={{ flexDirection: "row", gap: 8 }}>
          <ReceiptCaptureButton onAdded={load} />
          <Pressable style={styles.btnPrimary} onPress={() => setAddOpen(true)} accessibilityRole="button" accessibilityLabel="Add item"><Text style={styles.btnPrimaryText}>+ Add item</Text></Pressable>
        </View>
      </View>

      <View style={[styles.alert]}>
        <Text style={styles.alertText}>
          River's purchase request: <Text style={{ fontWeight: "700" }}>Paper towels</Text> — waiting for your approval.
        </Text>
      </View>

      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Needs Review</Text>
          <Text style={styles.itemCount}>{pending.length} pending</Text>
        </View>
        {pending.length === 0 ? (
          <Text style={styles.emptyText}>Nothing pending.</Text>
        ) : (
          pending.map((item) => (
            <View key={item.id} style={styles.reviewRow}>
              <Text style={styles.reviewName}>{item.title}</Text>
              {canApproveGrocery && (
                <Pressable
                  style={styles.btnPrimary}
                  onPress={() => handleApprove(item)}
                  accessibilityRole="button"
                  accessibilityLabel={`Approve ${item.title}`}
                >
                  <Text style={styles.btnPrimaryText}>Approve</Text>
                </Pressable>
              )}
            </View>
          ))
        )}
      </View>

      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Purchase Requests</Text>
          <Text style={styles.itemCount}>{requests.length} pending</Text>
        </View>
        {requests.length === 0 ? (
          <Text style={styles.emptyText}>No pending requests.</Text>
        ) : (
          requests.map((req) => (
            <View key={req.id} style={styles.reviewRow}>
              <Text style={styles.reviewName}>{req.title}</Text>
              {canApprovePurchase && (
                <Pressable
                  style={styles.btnPrimary}
                  onPress={() => handleConvert(req)}
                  accessibilityRole="button"
                  accessibilityLabel={`Add ${req.title} to list`}
                >
                  <Text style={styles.btnPrimaryText}>Add to List</Text>
                </Pressable>
              )}
            </View>
          ))
        )}
      </View>

      {error && (
        <View style={[styles.alert]}>
          <Text style={styles.alertText}>{error}</Text>
        </View>
      )}

      <Modal visible={addOpen} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Add Item</Text>
            <TextInput
              style={styles.input}
              placeholder="Item title"
              placeholderTextColor={colors.muted}
              value={addTitle}
              onChangeText={setAddTitle}
              editable={!addBusy}
            />
            <TextInput
              style={styles.input}
              placeholder="Preferred store (optional)"
              placeholderTextColor={colors.muted}
              value={addStore}
              onChangeText={setAddStore}
              editable={!addBusy}
            />
            <View style={styles.modalActions}>
              <Pressable
                style={styles.btnCancel}
                onPress={() => {
                  setAddOpen(false);
                  setAddTitle("");
                  setAddStore("");
                }}
                disabled={addBusy}
              >
                <Text style={styles.btnCancelText}>Cancel</Text>
              </Pressable>
              <Pressable
                style={styles.btnConfirm}
                onPress={handleAddItem}
                disabled={addBusy}
              >
                <Text style={styles.btnConfirmText}>{addBusy ? "Adding…" : "Add"}</Text>
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>

      {/* Per-store cards — driven by grocery.stores config */}
      <View style={[styles.grid2, !isDesktop && styles.grid2Stack]}>
        {storeCards.map((card) => (
          <View key={card.storeId} style={shared.card}>
            <View style={shared.cardTitleRow}>
              <Text style={shared.cardTitle}>{card.storeName}</Text>
              <Text style={styles.itemCount}>{card.storeItems.length} items</Text>
            </View>
            {card.storeItems.length === 0 ? (
              <Text style={styles.emptyText}>No items for this store yet.</Text>
            ) : (
              card.storeItems.map((item) => (
                <View key={item.id} style={styles.itemRow}>
                  <View style={styles.check}>
                    {/* approval_status "purchased" could show checkmark in future */}
                  </View>
                  <Text style={styles.itemName}>{item.title}</Text>
                  {item.category && (
                    <View style={styles.catTag}>
                      <Text style={styles.catTagText}>{item.category}</Text>
                    </View>
                  )}
                </View>
              ))
            )}
          </View>
        ))}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", rowGap: 8 },
  h1: { fontSize: 22, fontWeight: "600", color: colors.text, fontFamily: fonts.body },

  btnPrimary: {
    backgroundColor: colors.purple,
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  btnPrimaryText: { color: "#FFFFFF", fontSize: 12, fontWeight: "500", fontFamily: fonts.body },

  alert: {
    backgroundColor: colors.amberBg,
    borderWidth: 1,
    borderColor: "#FCD34D",
    borderLeftWidth: 3,
    borderLeftColor: colors.amber,
    borderRadius: 8,
    padding: 12,
  },
  alertText: { fontSize: 12, color: colors.amberText, fontFamily: fonts.body, lineHeight: 16 },

  grid2: { flexDirection: "row", gap: 12, alignItems: "flex-start" },
  grid2Stack: { flexDirection: "column" },
  itemCount: { fontSize: 11, color: colors.muted, fontFamily: fonts.body },

  itemRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 5,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  check: { width: 16, height: 16, borderRadius: 4, borderWidth: 1.5, borderColor: colors.border, alignItems: "center", justifyContent: "center" },
  itemName: { flex: 1, fontSize: 12, color: colors.text, fontFamily: fonts.body },
  catTag: { backgroundColor: colors.purpleLight, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 },
  catTagText: { fontSize: 9, color: colors.purpleDeep, fontWeight: "700", fontFamily: fonts.body },

  reviewRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  reviewName: { flex: 1, fontSize: 13, color: colors.text, fontFamily: fonts.body },
  emptyText: { fontSize: 12, color: colors.muted, fontFamily: fonts.body, paddingVertical: 6 },

  modalOverlay: { flex: 1, backgroundColor: "rgba(0, 0, 0, 0.5)", justifyContent: "flex-end" },
  modalContent: {
    backgroundColor: colors.bg,
    borderTopLeftRadius: 12,
    borderTopRightRadius: 12,
    padding: 20,
    gap: 12,
  },
  modalTitle: { fontSize: 16, fontWeight: "600", color: colors.text, fontFamily: fonts.body, marginBottom: 6 },
  input: {
    backgroundColor: colors.surfaceMuted,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 13,
    color: colors.text,
    fontFamily: fonts.body,
    outlineWidth: 0,
  } as any,
  modalActions: { flexDirection: "row", gap: 10, marginTop: 8 },
  btnCancel: {
    flex: 1,
    backgroundColor: colors.surfaceMuted,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: "center",
  },
  btnCancelText: { color: colors.text, fontSize: 12, fontWeight: "600", fontFamily: fonts.body },
  btnConfirm: {
    flex: 1,
    backgroundColor: colors.purple,
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: "center",
  },
  btnConfirmText: { color: "#FFFFFF", fontSize: 12, fontWeight: "600", fontFamily: fonts.body },
});
