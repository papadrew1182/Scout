/**
 * /admin/scout-ai — Scout AI settings admin screen
 *
 * Section 1: Capability toggles (reads/writes scout_ai.toggles config)
 * Section 2: Usage caps (stub)
 * Section 3: Moderation log (stub)
 *
 * Permission: scout_ai.manage_toggles
 */

import { useCallback } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { Redirect } from "expo-router";

import { shared, colors, fonts, radii } from "../../../lib/styles";
import { useHasPermission } from "../../../lib/permissions";
import { useFamilyConfig } from "../../../lib/config";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ScoutAIToggles {
  allow_general_chat: boolean;
  allow_homework_help: boolean;
  proactive_suggestions: boolean;
  push_notifications: boolean;
}

const DEFAULT_AI_TOGGLES: ScoutAIToggles = {
  allow_general_chat: true,
  allow_homework_help: true,
  proactive_suggestions: true,
  push_notifications: true,
};

const TOGGLE_LABELS: Array<{
  key: keyof ScoutAIToggles;
  label: string;
  sub: string;
}> = [
  {
    key: "allow_general_chat",
    label: "Allow general chat",
    sub: "Q&A, creative writing, coding help",
  },
  {
    key: "allow_homework_help",
    label: "Homework help (kids)",
    sub: "Socratic tutoring — guides, doesn't give answers",
  },
  {
    key: "proactive_suggestions",
    label: "Proactive suggestions",
    sub: "Scout surfaces ideas without being asked",
  },
  {
    key: "push_notifications",
    label: "Push notifications",
    sub: "Chore reminders, meal alerts, family updates",
  },
];

// ---------------------------------------------------------------------------
// Main screen
// ---------------------------------------------------------------------------

export default function ScoutAIAdmin() {
  const canManage = useHasPermission("scout_ai.manage_toggles");

  const {
    value: toggles,
    setValue: setToggles,
    loading,
    error,
  } = useFamilyConfig<ScoutAIToggles>("scout_ai.toggles", DEFAULT_AI_TOGGLES);

  const handleToggle = useCallback(
    (key: keyof ScoutAIToggles, val: boolean) => {
      setToggles({ ...toggles, [key]: val });
    },
    [toggles, setToggles],
  );

  if (!canManage) {
    return <Redirect href="/admin" />;
  }

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Scout AI</Text>
      <Text style={styles.subtitle}>
        Control what Scout AI can do for your family. Changes take effect immediately.
      </Text>

      {/* ------------------------------------------------------------------ */}
      {/* Section 1: Capability toggles                                       */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Capability toggles</Text>
        </View>

        {loading ? (
          <ActivityIndicator size="small" color={colors.purple} style={{ marginVertical: 12 }} />
        ) : error ? (
          <Text style={styles.errorText}>{error}</Text>
        ) : (
          TOGGLE_LABELS.map((t, idx) => {
            const on = Boolean(toggles[t.key]);
            return (
              <View
                key={t.key}
                style={[
                  styles.toggleRow,
                  idx === TOGGLE_LABELS.length - 1 && styles.toggleRowLast,
                ]}
              >
                <View style={{ flex: 1 }}>
                  <Text style={styles.toggleLabel}>{t.label}</Text>
                  <Text style={styles.toggleSub}>{t.sub}</Text>
                </View>
                <Switch
                  value={on}
                  onValueChange={(val) => handleToggle(t.key, val)}
                  trackColor={{ true: colors.purple, false: colors.border }}
                  thumbColor={colors.card}
                  accessibilityRole="switch"
                  accessibilityState={{ checked: on }}
                  accessibilityLabel={t.label}
                />
              </View>
            );
          })
        )}
      </View>

      {/* ------------------------------------------------------------------ */}
      {/* Section 2: Usage caps stub                                          */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Usage caps</Text>
        </View>
        <Text style={styles.stubText}>
          Coming soon — monthly AI token cap, per-kid session limits.
        </Text>
      </View>

      {/* ------------------------------------------------------------------ */}
      {/* Section 3: Moderation log stub                                      */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Moderation log</Text>
        </View>
        <Text style={styles.stubText}>
          Coming soon — recent flags, overrides, audit trail.
        </Text>
      </View>
    </ScrollView>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  content: { padding: 20, paddingBottom: 48, gap: 14 },
  h1: {
    fontSize: 20,
    fontWeight: "600",
    color: colors.text,
    fontFamily: fonts.body,
  },
  subtitle: {
    fontSize: 13,
    color: colors.muted,
    fontFamily: fonts.body,
    lineHeight: 19,
    marginTop: -4,
  },
  errorText: {
    fontSize: 13,
    color: colors.redText,
    fontFamily: fonts.body,
    marginVertical: 8,
  },
  toggleRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  toggleRowLast: {
    borderBottomWidth: 0,
  },
  toggleLabel: {
    fontSize: 13,
    fontWeight: "500",
    color: colors.text,
    fontFamily: fonts.body,
  },
  toggleSub: {
    fontSize: 11,
    color: colors.muted,
    marginTop: 2,
    fontFamily: fonts.body,
    lineHeight: 16,
  },
  stubText: {
    fontSize: 13,
    color: colors.muted,
    fontFamily: fonts.body,
    lineHeight: 19,
  },
});
