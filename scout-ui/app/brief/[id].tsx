/**
 * Detail view for a Parent Action Inbox item with long-form detail
 * text — e.g., the scheduled morning brief. Renders the full content
 * with a "Mark done" control.
 *
 * URL: /brief/{action_item_id}
 */

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";

import { fetchActionItem, resolveActionItem } from "../../lib/api";
import { shared, colors } from "../../lib/styles";

interface ActionItemDetail {
  id: string;
  family_id: string;
  action_type: string;
  title: string;
  detail: string | null;
  entity_type: string | null;
  entity_id: string | null;
  status: string;
  created_at: string | null;
}

export default function BriefDetailPage() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [item, setItem] = useState<ActionItemDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchActionItem(String(id));
      setItem(data);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const markDone = async () => {
    if (!item) return;
    setBusy(true);
    try {
      await resolveActionItem(item.id);
      router.back();
    } catch (e: any) {
      setError(e?.message ?? "Failed to resolve");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <View style={shared.pageCenter}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  if (error || !item) {
    return (
      <View style={shared.pageCenter}>
        <Text style={shared.errorLarge}>{error ?? "Not found"}</Text>
        <Pressable style={[shared.button, { marginTop: 16 }]} onPress={() => router.back()}>
          <Text style={shared.buttonText}>Back</Text>
        </Pressable>
      </View>
    );
  }

  const created = item.created_at
    ? new Date(item.created_at).toLocaleString([], {
        weekday: "long",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      })
    : "";

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={shared.pageContent}>
      <View style={shared.headerBlock}>
        <Pressable onPress={() => router.back()} style={s.backBtn}>
          <Text style={s.backText}>← Back</Text>
        </Pressable>
        <Text style={shared.headerEyebrow}>
          {labelForType(item.action_type)}
        </Text>
        <Text style={shared.headerTitle}>{item.title}</Text>
        {created && <Text style={shared.headerSubtitle}>{created}</Text>}
      </View>

      <View style={shared.card}>
        <Text style={s.briefBody} selectable>
          {item.detail || "(no content)"}
        </Text>
      </View>

      {item.status === "pending" && (
        <Pressable
          style={[shared.button, { marginTop: 16 }]}
          onPress={markDone}
          disabled={busy}
        >
          <Text style={shared.buttonText}>
            {busy ? "Saving…" : "Mark as read"}
          </Text>
        </Pressable>
      )}
    </ScrollView>
  );
}

function labelForType(t: string): string {
  switch (t) {
    case "daily_brief":
      return "Morning brief";
    case "weekly_retro":
      return "Weekly retro";
    case "moderation_digest":
      return "Safety digest";
    case "moderation_alert":
      return "Scout Safety";
    default:
      return "Action item";
  }
}

const s = StyleSheet.create({
  backBtn: {
    paddingVertical: 4,
    marginBottom: 8,
  },
  backText: {
    color: colors.accent,
    fontSize: 14,
    fontWeight: "600",
  },
  briefBody: {
    color: colors.textPrimary,
    fontSize: 15,
    lineHeight: 22,
  },
});
