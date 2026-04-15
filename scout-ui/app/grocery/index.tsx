import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { colors, fonts, shared } from "../../lib/styles";
import { GROCERY } from "../../lib/seedData";
import {
  fetchPendingReviewItems,
  fetchPurchaseRequests,
  updateGroceryItem,
  convertPurchaseRequestToGrocery,
} from "../../lib/api";
import type { GroceryItem, PurchaseRequest } from "../../lib/types";

export default function Grocery() {
  const [pending, setPending] = useState<GroceryItem[]>([]);
  const [requests, setRequests] = useState<PurchaseRequest[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const [p, r] = await Promise.all([
        fetchPendingReviewItems(),
        fetchPurchaseRequests("pending"),
      ]);
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

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <View style={styles.headerRow}>
        <Text style={styles.h1}>Grocery List</Text>
        <View style={{ flexDirection: "row", gap: 8 }}>
          <Pressable style={styles.btnGhost} accessibilityRole="button" accessibilityLabel="Scan receipt"><Text style={styles.btnGhostText}>Scan receipt</Text></Pressable>
          <Pressable style={styles.btnPrimary} accessibilityRole="button" accessibilityLabel="Add item"><Text style={styles.btnPrimaryText}>+ Add item</Text></Pressable>
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
              <Pressable
                style={styles.btnPrimary}
                onPress={() => handleApprove(item)}
                accessibilityRole="button"
                accessibilityLabel={`Approve ${item.title}`}
              >
                <Text style={styles.btnPrimaryText}>Approve</Text>
              </Pressable>
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
              <Pressable
                style={styles.btnPrimary}
                onPress={() => handleConvert(req)}
                accessibilityRole="button"
                accessibilityLabel={`Add ${req.title} to list`}
              >
                <Text style={styles.btnPrimaryText}>Add to List</Text>
              </Pressable>
            </View>
          ))
        )}
      </View>

      {error && (
        <View style={[styles.alert]}>
          <Text style={styles.alertText}>{error}</Text>
        </View>
      )}

      <View style={styles.grid2}>
        {GROCERY.map((store) => {
          const sections: Record<string, typeof store.items> = {};
          store.items.forEach((i) => {
            (sections[i.section] ||= []).push(i);
          });
          const isTomThumb = store.name === "Tom Thumb";
          return (
            <View key={store.name} style={shared.card}>
              <View style={shared.cardTitleRow}>
                <Text style={shared.cardTitle}>{store.name}</Text>
                <Text style={styles.itemCount}>{store.items.length} items</Text>
              </View>
              {Object.entries(sections).map(([section, items]) => (
                <View key={section}>
                  <Text style={shared.sectionHead}>{section}</Text>
                  {items.map((i) => (
                    <View key={i.name} style={styles.itemRow}>
                      <View style={[styles.check, i.done && styles.checkDone]}>
                        {i.done && <Text style={styles.checkMark}>✓</Text>}
                      </View>
                      <Text style={[styles.itemName, i.done && { color: colors.muted, textDecorationLine: "line-through" }]}>
                        {i.name}
                      </Text>
                      {i.requestedBy && (
                        <View style={styles.reqTag}>
                          <Text style={styles.reqTagText}>{i.requestedBy}'s request</Text>
                        </View>
                      )}
                    </View>
                  ))}
                </View>
              ))}
              {isTomThumb && (
                <View style={styles.approveRow}>
                  <Pressable style={[styles.btnPrimary, { flex: 1 }]} accessibilityRole="button" accessibilityLabel="Approve request">
                    <Text style={styles.btnPrimaryText}>Approve request</Text>
                  </Pressable>
                  <Pressable style={styles.btnGhost} accessibilityRole="button" accessibilityLabel="Reject request">
                    <Text style={styles.btnGhostText}>Reject</Text>
                  </Pressable>
                </View>
              )}
            </View>
          );
        })}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 14, paddingBottom: 48 },
  headerRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
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
  btnGhost: {
    borderWidth: 1,
    borderColor: colors.purpleMid,
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  btnGhostText: { color: colors.purple, fontSize: 12, fontWeight: "500", fontFamily: fonts.body },

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
  checkDone: { backgroundColor: colors.green, borderColor: colors.green },
  checkMark: { color: "#FFFFFF", fontSize: 10, fontWeight: "700" },
  itemName: { flex: 1, fontSize: 12, color: colors.text, fontFamily: fonts.body },
  reqTag: { backgroundColor: colors.amberBg, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 },
  reqTagText: { fontSize: 9, color: colors.amberText, fontWeight: "700", fontFamily: fonts.body },

  approveRow: { flexDirection: "row", gap: 8, marginTop: 10 },

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
});
