/**
 * Parent Action Inbox — shows pending action items from children.
 * Deep-links into relevant review screens.
 */

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useRouter } from "expo-router";

import { fetchActionItems } from "../lib/api";
import { colors, shared } from "../lib/styles";

interface ActionItem {
  id: string;
  action_type: string;
  title: string;
  detail: string | null;
  entity_type: string | null;
  entity_id: string | null;
  status: string;
  created_at: string;
  created_by: string;
}

function actionTypeLabel(type: string): string {
  switch (type) {
    case "grocery_review": return "Grocery";
    case "purchase_request": return "Request";
    case "meal_plan_review": return "Meal Plan";
    default: return "Action";
  }
}

function actionTypeColor(type: string): string {
  switch (type) {
    case "grocery_review": return colors.positive;
    case "purchase_request": return colors.warning;
    case "meal_plan_review": return colors.accent;
    default: return colors.textMuted;
  }
}

export function ActionInbox() {
  const router = useRouter();
  const [items, setItems] = useState<ActionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchActionItems();
      setItems(data);
    } catch (e: any) {
      setError(e.message ?? "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleTap = (item: ActionItem) => {
    if (item.entity_type === "grocery_item" || item.entity_type === "purchase_request") {
      router.push("/grocery");
    } else if (item.entity_type === "weekly_meal_plan") {
      router.push("/meals/this-week");
    }
  };

  if (loading) {
    return (
      <View style={styles.container}>
        <Text style={shared.sectionTitle}>Action Inbox</Text>
        <ActivityIndicator size="small" color={colors.accent} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.container}>
        <Text style={shared.sectionTitle}>Action Inbox</Text>
        <View style={shared.card}>
          <Text style={shared.errorText}>{error}</Text>
          <Pressable style={[shared.buttonSmall, { marginTop: 8 }]} onPress={load}>
            <Text style={shared.buttonSmallText}>Retry</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  if (items.length === 0) {
    return (
      <View style={styles.container}>
        <Text style={shared.sectionTitle}>Action Inbox</Text>
        <View style={shared.card}>
          <Text style={shared.emptyText}>No pending items</Text>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={shared.sectionTitle}>
        Action Inbox ({items.length})
      </Text>
      {items.map((item) => (
        <Pressable key={item.id} style={styles.itemCard} onPress={() => handleTap(item)}>
          <View style={styles.itemRow}>
            <View style={[styles.typeBadge, { backgroundColor: actionTypeColor(item.action_type) + "22" }]}>
              <Text style={[styles.typeBadgeText, { color: actionTypeColor(item.action_type) }]}>
                {actionTypeLabel(item.action_type)}
              </Text>
            </View>
            <Text style={styles.itemTitle} numberOfLines={1}>{item.title}</Text>
          </View>
          {item.detail && (
            <Text style={styles.itemDetail} numberOfLines={2}>{item.detail}</Text>
          )}
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginTop: 8 },
  itemCard: {
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderLeftWidth: 3,
    borderLeftColor: colors.warning,
    padding: 14,
    marginBottom: 8,
  },
  itemRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  typeBadge: {
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  typeBadgeText: {
    fontSize: 10,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  itemTitle: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: "500",
    flex: 1,
  },
  itemDetail: {
    color: colors.textMuted,
    fontSize: 12,
    marginTop: 4,
  },
});
