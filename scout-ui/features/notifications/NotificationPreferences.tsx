/**
 * NotificationPreferences — local-only starter.
 *
 * Respects the locked product boundary: this is a UI starter, not a
 * persistence layer. There is no save endpoint yet, so toggles flip
 * local state only and are clearly labeled as "local preview". Once a
 * real backend route lands, this component swaps to it.
 *
 * Initial defaults are read from familyContext.household_rules
 * (one_reminder_max) and the actor's role tier — surfaces are
 * capability-aware without hardcoding age.
 */

import { useEffect, useState } from "react";
import { StyleSheet, Switch, Text, View } from "react-native";

import { useFamilyContext, useIsParent, useMe } from "../hooks";
import { colors } from "../../lib/styles";

interface PrefsState {
  one_reminder_max: boolean;
  quiet_hours_enabled: boolean;
  daily_summary_enabled: boolean;
  parent_alerts_enabled: boolean;
}

const DEFAULT_PREFS: PrefsState = {
  one_reminder_max: true,
  quiet_hours_enabled: true,
  daily_summary_enabled: true,
  parent_alerts_enabled: true,
};

export function NotificationPreferences() {
  const family = useFamilyContext();
  const me = useMe();
  const isParent = useIsParent();
  const [prefs, setPrefs] = useState<PrefsState>(DEFAULT_PREFS);

  // Hydrate from household_rules.one_reminder_max if present.
  useEffect(() => {
    const rule = family.data?.household_rules?.one_reminder_max;
    if (typeof rule === "boolean") {
      setPrefs((p) => ({ ...p, one_reminder_max: rule }));
    }
  }, [family.data]);

  // Hide the parent-alerts row entirely from kid-tier viewers.
  // Quiet hours / daily summary stay visible for everyone since they
  // affect their own delivery.
  const showParentAlerts = isParent;

  const actorName = me.data?.user.full_name ?? "Signed-in user";
  const actorRole = me.data?.user.role_tier_key ?? "—";

  return (
    <View style={styles.card}>
      <Text style={styles.label}>Notification preferences</Text>
      <Text style={styles.helper}>
        Local preview. Saving lands later — toggles below don't yet
        round-trip to the backend.
      </Text>

      <PrefRow
        label="One reminder max per task"
        helper="Quiet enforcement — Scout sends a single reminder, then leaves it on the checklist."
        value={prefs.one_reminder_max}
        onChange={(v) => setPrefs((p) => ({ ...p, one_reminder_max: v }))}
      />
      <PrefRow
        label="Quiet hours"
        helper="Suppress all push notifications between 9:30 PM and 6:30 AM local."
        value={prefs.quiet_hours_enabled}
        onChange={(v) => setPrefs((p) => ({ ...p, quiet_hours_enabled: v }))}
      />
      <PrefRow
        label="Daily morning summary"
        helper="One push at 7:00 AM with what's due today."
        value={prefs.daily_summary_enabled}
        onChange={(v) => setPrefs((p) => ({ ...p, daily_summary_enabled: v }))}
      />
      {showParentAlerts && (
        <PrefRow
          label="Parent alerts"
          helper="Late-task pings + reward approval prompts. Parent-tier only."
          value={prefs.parent_alerts_enabled}
          onChange={(v) => setPrefs((p) => ({ ...p, parent_alerts_enabled: v }))}
        />
      )}

      <Text style={styles.actor}>
        Active as {actorName} · {actorRole.replace(/_/g, " ").toLowerCase()}
      </Text>
    </View>
  );
}

function PrefRow({
  label,
  helper,
  value,
  onChange,
}: {
  label: string;
  helper: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <View style={styles.row}>
      <View style={styles.rowText}>
        <Text style={styles.rowLabel} numberOfLines={2}>
          {label}
        </Text>
        <Text style={styles.rowHelper} numberOfLines={3}>
          {helper}
        </Text>
      </View>
      <Switch
        value={value}
        onValueChange={onChange}
        accessibilityLabel={label}
        accessibilityHint={helper}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 14,
    marginTop: 18,
  },
  label: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 1.4,
    marginBottom: 4,
  },
  helper: {
    color: colors.textMuted,
    fontSize: 12,
    fontStyle: "italic",
    marginBottom: 14,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  rowText: { flex: 1, paddingRight: 12 },
  rowLabel: { color: colors.textPrimary, fontSize: 13, fontWeight: "700" },
  rowHelper: { color: colors.textMuted, fontSize: 11, marginTop: 2 },
  actor: {
    color: colors.textPlaceholder,
    fontSize: 11,
    marginTop: 14,
    fontStyle: "italic",
    textAlign: "right",
  },
});
