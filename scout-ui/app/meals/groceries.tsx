import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { CURRENT_USER_ID } from "../../lib/config";
import { fetchWeeklyPlanGroceries, updateGroceryItem } from "../../lib/api";
import { useCurrentWeeklyPlan, formatWeekStart } from "../../lib/meal_plan_hooks";
import { shared, colors } from "../../lib/styles";
import type { GroceryItem } from "../../lib/types";

export default function MealsGroceriesPage() {
  const { plan, loading: planLoading, notFound, error: planError, reload: reloadPlan } = useCurrentWeeklyPlan();
  const [items, setItems] = useState<GroceryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!plan) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchWeeklyPlanGroceries(plan.id);
      setItems(data);
    } catch (e: any) {
      setError(e.message ?? "Failed to load groceries");
    } finally {
      setLoading(false);
    }
  }, [plan]);

  useEffect(() => {
    load();
  }, [load]);

  const togglePurchased = async (item: GroceryItem) => {
    try {
      await updateGroceryItem(CURRENT_USER_ID, item.id, {
        is_purchased: !item.is_purchased,
      });
      load();
    } catch (e) {
      console.error(e);
    }
  };

  if (planLoading) {
    return (
      <View style={shared.pageCenter}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  if (planError) {
    return (
      <View style={shared.pageCenter}>
        <Text style={shared.errorLarge}>{planError}</Text>
        <Pressable style={[shared.button, { marginTop: 16 }]} onPress={reloadPlan}>
          <Text style={shared.buttonText}>Retry</Text>
        </Pressable>
      </View>
    );
  }

  if (notFound || !plan) {
    return (
      <ScrollView style={shared.pageContainer} contentContainerStyle={shared.pageContent}>
        <View style={shared.headerBlock}>
          <Text style={shared.headerEyebrow}>Meals</Text>
          <Text style={shared.headerTitle}>Groceries</Text>
        </View>
        <View style={shared.card}>
          <Text style={shared.emptyText}>No plan yet. Generate one to see its groceries.</Text>
        </View>
      </ScrollView>
    );
  }

  // Group by store; unknown store goes last.
  const byStore = new Map<string, GroceryItem[]>();
  for (const it of items) {
    const store = it.preferred_store || "Other";
    if (!byStore.has(store)) byStore.set(store, []);
    byStore.get(store)!.push(it);
  }
  const storeOrder = Array.from(byStore.keys()).sort((a, b) => {
    if (a === "Other") return 1;
    if (b === "Other") return -1;
    return a.localeCompare(b);
  });

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={shared.pageContent}>
      <View style={shared.headerBlock}>
        <Text style={shared.headerEyebrow}>Meals</Text>
        <Text style={shared.headerTitle}>Groceries</Text>
        <Text style={shared.headerSubtitle}>
          For week of {formatWeekStart(plan.week_start_date)}
        </Text>
      </View>

      {loading && <ActivityIndicator size="small" color={colors.accent} />}
      {error && <Text style={shared.errorText}>{error}</Text>}

      {!loading && items.length === 0 && (
        <View style={shared.card}>
          <Text style={shared.emptyText}>
            {plan.status === "draft"
              ? "Groceries land here once the plan is approved."
              : "No items from this plan."}
          </Text>
        </View>
      )}

      {storeOrder.map((store) => {
        const storeItems = byStore.get(store)!;
        return (
          <View key={store}>
            <Text style={s.storeLabel}>{store}</Text>
            {storeItems.map((item) => (
              <Pressable
                key={item.id}
                style={[s.itemRow, item.is_purchased && s.itemPurchased]}
                onPress={() => togglePurchased(item)}
              >
                <View style={[s.checkbox, item.is_purchased && s.checkboxDone]}>
                  {item.is_purchased && <Text style={s.checkmark}>✓</Text>}
                </View>
                <View style={s.itemContent}>
                  <Text
                    style={
                      item.is_purchased ? s.itemTitleDone : s.itemTitle
                    }
                  >
                    {item.title}
                  </Text>
                  {(item.quantity != null || item.unit) && (
                    <Text style={s.itemMeta}>
                      {item.quantity ?? ""}
                      {item.unit ? ` ${item.unit}` : ""}
                    </Text>
                  )}
                  {item.linked_meal_ref && (
                    <Text style={s.linkMeta}>{item.linked_meal_ref}</Text>
                  )}
                </View>
              </Pressable>
            ))}
          </View>
        );
      })}
    </ScrollView>
  );
}

const s = StyleSheet.create({
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
  checkboxDone: {
    backgroundColor: colors.positive,
    borderColor: colors.positive,
  },
  checkmark: { color: "#fff", fontSize: 13, fontWeight: "700" },
  itemContent: { flex: 1 },
  itemTitle: {
    color: colors.textPrimary,
    fontSize: 15,
    fontWeight: "500",
  },
  itemTitleDone: {
    color: colors.textMuted,
    fontSize: 15,
    textDecorationLine: "line-through",
  },
  itemMeta: {
    color: colors.textMuted,
    fontSize: 12,
    marginTop: 2,
  },
  linkMeta: {
    color: colors.accent,
    fontSize: 11,
    marginTop: 2,
    fontWeight: "600",
  },
});
