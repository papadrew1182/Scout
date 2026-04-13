import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { NeedSomething } from "../../components/NeedSomething";
import { ReceiptCaptureButton } from "../../components/ReceiptCaptureButton";
import {
  fetchGroceryItems,
  fetchPendingReviewItems,
  fetchPurchaseRequests,
  updateGroceryItem,
  approvePurchaseRequest,
  rejectPurchaseRequest,
  convertPurchaseRequestToGrocery,
} from "../../lib/api";
import { sourceLabel } from "../../lib/format";
import { shared, colors } from "../../lib/styles";
import type { GroceryItem, PurchaseRequest } from "../../lib/types";

export default function GroceryPage() {
  const [items, setItems] = useState<GroceryItem[]>([]);
  const [pending, setPending] = useState<GroceryItem[]>([]);
  const [requests, setRequests] = useState<PurchaseRequest[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [g, p, r] = await Promise.all([
        fetchGroceryItems(),
        fetchPendingReviewItems(),
        fetchPurchaseRequests("pending"),
      ]);
      setItems(g);
      setPending(p);
      setRequests(r);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleTogglePurchased = async (item: GroceryItem) => {
    try {
      await updateGroceryItem(item.id, { is_purchased: !item.is_purchased });
      load();
    } catch (e) {
      console.error(e);
    }
  };

  const handleApproveItem = async (item: GroceryItem) => {
    try {
      await updateGroceryItem(item.id, { approval_status: "active" });
      load();
    } catch (e) {
      console.error(e);
    }
  };

  const handleApproveRequest = async (req: PurchaseRequest) => {
    try {
      await approvePurchaseRequest(req.id);
      load();
    } catch (e) {
      console.error(e);
    }
  };

  const handleRejectRequest = async (req: PurchaseRequest) => {
    try {
      await rejectPurchaseRequest(req.id);
      load();
    } catch (e) {
      console.error(e);
    }
  };

  const handleConvertRequest = async (req: PurchaseRequest) => {
    try {
      await convertPurchaseRequestToGrocery(req.id);
      load();
    } catch (e) {
      console.error(e);
    }
  };

  // Group items by store
  const activeItems = items.filter((i) => i.approval_status === "active" && !i.is_purchased);
  const purchasedItems = items.filter((i) => i.is_purchased);
  const stores = [...new Set(activeItems.map((i) => i.preferred_store || "Other"))].sort();

  if (loading) {
    return (
      <View style={shared.pageCenter}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={shared.pageContent}>
      <View style={shared.headerBlock}>
        <Text style={shared.headerTitle}>Grocery List</Text>
      </View>

      <View style={{ marginBottom: 12 }}>
        <ReceiptCaptureButton onAdded={() => load()} />
      </View>

      <NeedSomething onComplete={load} />

      {/* Pending review (parent only) */}
      {pending.length > 0 && (
        <>
          <Text style={shared.sectionTitle}>Needs Review</Text>
          {pending.map((item) => (
            <View key={item.id} style={s.reviewCard}>
              <Text style={s.reviewTitle}>{item.title}</Text>
              {item.notes && <Text style={s.reviewMeta}>{item.notes}</Text>}
              <View style={s.reviewActions}>
                <Pressable style={s.approveBtn} onPress={() => handleApproveItem(item)}>
                  <Text style={s.approveBtnText}>Approve</Text>
                </Pressable>
              </View>
            </View>
          ))}
        </>
      )}

      {/* Pending purchase requests (parent only) */}
      {requests.length > 0 && (
        <>
          <Text style={shared.sectionTitle}>Purchase Requests</Text>
          {requests.map((req) => (
            <View key={req.id} style={s.reviewCard}>
              <Text style={s.reviewTitle}>{req.title}</Text>
              {req.details && <Text style={s.reviewMeta}>{req.details}</Text>}
              {req.urgency && <Text style={s.urgencyBadge}>{req.urgency}</Text>}
              <View style={s.reviewActions}>
                <Pressable style={s.approveBtn} onPress={() => handleConvertRequest(req)}>
                  <Text style={s.approveBtnText}>Add to List</Text>
                </Pressable>
                <Pressable style={s.approveBtn} onPress={() => handleApproveRequest(req)}>
                  <Text style={s.approveBtnText}>Approve</Text>
                </Pressable>
                <Pressable style={s.rejectBtn} onPress={() => handleRejectRequest(req)}>
                  <Text style={s.rejectBtnText}>Reject</Text>
                </Pressable>
              </View>
            </View>
          ))}
        </>
      )}

      {/* Active grocery list grouped by store */}
      <Text style={shared.sectionTitle}>Shopping List</Text>
      {activeItems.length === 0 && (
        <View style={shared.card}>
          <Text style={shared.emptyText}>No items on the list</Text>
        </View>
      )}
      {stores.map((store) => {
        const storeItems = activeItems.filter((i) => (i.preferred_store || "Other") === store);
        return (
          <View key={store}>
            <Text style={s.storeLabel}>{store}</Text>
            {storeItems.map((item) => (
              <Pressable
                key={item.id}
                style={s.itemRow}
                onPress={() => handleTogglePurchased(item)}
              >
                <View style={s.checkbox}>
                  {item.is_purchased && <Text style={s.checkmark}>✓</Text>}
                </View>
                <View style={s.itemContent}>
                  <Text style={s.itemTitle}>{item.title}</Text>
                  {(item.quantity || item.unit) && (
                    <Text style={s.itemMeta}>
                      {item.quantity}{item.unit ? ` ${item.unit}` : ""}
                    </Text>
                  )}
                </View>
                {item.source !== "manual" && (
                  <Text style={shared.itemBadge}>{item.source === "meal_ai" ? "MEAL" : "REQ"}</Text>
                )}
              </Pressable>
            ))}
          </View>
        );
      })}

      {/* Purchased */}
      {purchasedItems.length > 0 && (
        <>
          <Text style={shared.sectionTitle}>Purchased</Text>
          {purchasedItems.map((item) => (
            <Pressable
              key={item.id}
              style={[s.itemRow, s.itemPurchased]}
              onPress={() => handleTogglePurchased(item)}
            >
              <View style={[s.checkbox, s.checkboxDone]}>
                <Text style={s.checkmark}>✓</Text>
              </View>
              <Text style={s.itemTitleDone}>{item.title}</Text>
            </Pressable>
          ))}
        </>
      )}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  reviewCard: {
    backgroundColor: colors.warningBg,
    borderRadius: 10,
    borderLeftWidth: 3,
    borderLeftColor: colors.warning,
    padding: 14,
    marginBottom: 8,
  },
  reviewTitle: { color: colors.textPrimary, fontSize: 15, fontWeight: "600" },
  reviewMeta: { color: colors.textSecondary, fontSize: 13, marginTop: 4 },
  urgencyBadge: {
    color: colors.warning,
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    marginTop: 4,
  },
  reviewActions: { flexDirection: "row", gap: 8, marginTop: 10 },
  approveBtn: {
    backgroundColor: colors.positive,
    borderRadius: 6,
    paddingVertical: 6,
    paddingHorizontal: 12,
  },
  approveBtnText: { color: "#fff", fontSize: 12, fontWeight: "600" },
  rejectBtn: {
    backgroundColor: colors.negativeBg,
    borderRadius: 6,
    paddingVertical: 6,
    paddingHorizontal: 12,
  },
  rejectBtnText: { color: colors.negative, fontSize: 12, fontWeight: "600" },

  storeLabel: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 1,
    marginTop: 12,
    marginBottom: 6,
  },
  itemRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.card,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 14,
    marginBottom: 6,
  },
  itemPurchased: { opacity: 0.5 },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: colors.accent,
    justifyContent: "center",
    alignItems: "center",
    marginRight: 12,
  },
  checkboxDone: { backgroundColor: colors.positive, borderColor: colors.positive },
  checkmark: { color: "#fff", fontSize: 13, fontWeight: "700" },
  itemContent: { flex: 1 },
  itemTitle: { color: colors.textPrimary, fontSize: 15, fontWeight: "500" },
  itemTitleDone: { color: colors.textMuted, fontSize: 15, textDecorationLine: "line-through", flex: 1 },
  itemMeta: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
});
