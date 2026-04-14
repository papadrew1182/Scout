/**
 * Tier 5 F17 — Rich review card for weekly planner bundles.
 *
 * Renders a grouped, previewable summary of the proposed tasks,
 * events, and grocery items before the parent approves a single
 * atomic apply. Reuses the existing confirm_tool flow under the
 * hood: Approve calls back with the (possibly filtered) bundle and
 * `confirmed: true`; Cancel drops the pending card without writes.
 *
 * Per-group toggles let the parent drop a whole group of proposals
 * from the bundle if they don't want it. Finer-grained per-item
 * toggles were ruled out as too invasive for v1 — the generic
 * "revise by asking Scout to change it" path covers that.
 *
 * Falls back to a terse generic card if the pending confirmation
 * isn't a weekly plan bundle (other confirmation-required tools
 * like approve_weekly_meal_plan still use the original card UX).
 */

import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors } from "../lib/styles";
import type { AIPendingConfirmation } from "../lib/api";

interface Props {
  pending: AIPendingConfirmation;
  loading: boolean;
  onApprove: (args: Record<string, unknown>) => void;
  onCancel: () => void;
}

interface BundleTask {
  title?: string;
  assigned_to?: string;
  priority?: string;
  due_at?: string;
  description?: string;
}
interface BundleEvent {
  title?: string;
  starts_at?: string;
  ends_at?: string;
  location?: string;
}
interface BundleGrocery {
  title?: string;
  quantity?: number;
  unit?: string;
  category?: string;
  preferred_store?: string;
}

export function PlannerReviewCard({
  pending,
  loading,
  onApprove,
  onCancel,
}: Props) {
  const isPlannerBundle = pending.tool_name === "apply_weekly_plan_bundle";
  const args = pending.arguments as Record<string, unknown>;

  const tasks: BundleTask[] = Array.isArray(args?.tasks)
    ? (args.tasks as BundleTask[])
    : [];
  const events: BundleEvent[] = Array.isArray(args?.events)
    ? (args.events as BundleEvent[])
    : [];
  const groceryItems: BundleGrocery[] = Array.isArray(args?.grocery_items)
    ? (args.grocery_items as BundleGrocery[])
    : [];
  const summary = typeof args?.summary === "string" ? (args.summary as string) : "";

  // Default: all groups included. Toggling a group off filters
  // that group out of the submitted bundle on Approve.
  const [includeTasks, setIncludeTasks] = useState(tasks.length > 0);
  const [includeEvents, setIncludeEvents] = useState(events.length > 0);
  const [includeGrocery, setIncludeGrocery] = useState(groceryItems.length > 0);

  const nothingIncluded = useMemo(
    () =>
      (!includeTasks || tasks.length === 0) &&
      (!includeEvents || events.length === 0) &&
      (!includeGrocery || groceryItems.length === 0),
    [includeTasks, includeEvents, includeGrocery, tasks, events, groceryItems],
  );

  if (!isPlannerBundle) {
    // Generic fallback. Preserves existing confirm-card UX for
    // every other confirmation-required tool.
    return (
      <View style={styles.card}>
        <Text style={styles.title}>Confirm this action</Text>
        <Text style={styles.tool}>Tool: {pending.tool_name}</Text>
        <Text style={styles.body}>{pending.message}</Text>
        <View style={styles.row}>
          <Pressable
            style={styles.yes}
            onPress={() => onApprove(pending.arguments)}
            disabled={loading}
          >
            <Text style={styles.yesText}>Confirm</Text>
          </Pressable>
          <Pressable style={styles.no} onPress={onCancel} disabled={loading}>
            <Text style={styles.noText}>Cancel</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  const handleApprove = () => {
    onApprove({
      ...args,
      tasks: includeTasks ? tasks : [],
      events: includeEvents ? events : [],
      grocery_items: includeGrocery ? groceryItems : [],
      confirmed: true,
    });
  };

  return (
    <View style={styles.card}>
      <Text style={styles.title}>Review weekly plan</Text>
      {summary ? <Text style={styles.summary}>{summary}</Text> : null}

      <GroupBlock
        label="Tasks"
        count={tasks.length}
        included={includeTasks}
        onToggle={() => setIncludeTasks((v) => !v)}
        previews={tasks.slice(0, 4).map((t) => t.title || "(untitled)")}
      />
      <GroupBlock
        label="Events"
        count={events.length}
        included={includeEvents}
        onToggle={() => setIncludeEvents((v) => !v)}
        previews={events.slice(0, 4).map((e) => {
          const when = e.starts_at ? new Date(e.starts_at).toLocaleString([], {
            weekday: "short",
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
          }) : "";
          return `${e.title || "(untitled)"}${when ? ` · ${when}` : ""}`;
        })}
      />
      <GroupBlock
        label="Grocery"
        count={groceryItems.length}
        included={includeGrocery}
        onToggle={() => setIncludeGrocery((v) => !v)}
        previews={groceryItems.slice(0, 6).map((g) => {
          const qty = g.quantity ? ` × ${g.quantity}${g.unit ? ` ${g.unit}` : ""}` : "";
          return `${g.title || "(untitled)"}${qty}`;
        })}
      />

      <View style={styles.row}>
        <Pressable
          style={[styles.yes, (loading || nothingIncluded) && styles.yesDisabled]}
          onPress={handleApprove}
          disabled={loading || nothingIncluded}
        >
          <Text style={styles.yesText}>
            {loading ? "Applying…" : "Approve plan"}
          </Text>
        </Pressable>
        <Pressable style={styles.no} onPress={onCancel} disabled={loading}>
          <Text style={styles.noText}>Cancel</Text>
        </Pressable>
      </View>
      <Text style={styles.footnote}>
        Revise by asking Scout to change the plan. Nothing is written until you tap Approve.
      </Text>
    </View>
  );
}

function GroupBlock({
  label,
  count,
  included,
  onToggle,
  previews,
}: {
  label: string;
  count: number;
  included: boolean;
  onToggle: () => void;
  previews: string[];
}) {
  if (count === 0) return null;
  return (
    <View style={styles.group}>
      <Pressable onPress={onToggle} style={styles.groupHeader}>
        <View style={[styles.toggle, included && styles.toggleOn]}>
          {included && <Text style={styles.toggleCheck}>✓</Text>}
        </View>
        <Text style={styles.groupLabel}>
          {label} ({count})
        </Text>
      </Pressable>
      {included && (
        <View style={styles.previewBlock}>
          {previews.map((p, i) => (
            <Text key={i} style={styles.preview} numberOfLines={1}>
              · {p}
            </Text>
          ))}
          {count > previews.length && (
            <Text style={styles.preview}>
              … and {count - previews.length} more
            </Text>
          )}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    marginTop: 10,
    padding: 12,
    borderRadius: 12,
    backgroundColor: colors.surfaceMuted,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    gap: 8,
  },
  title: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: "700",
  },
  summary: {
    color: colors.textPrimary,
    fontSize: 13,
    lineHeight: 18,
  },
  tool: {
    color: colors.textMuted,
    fontSize: 11,
    fontFamily: "monospace",
  },
  body: {
    color: colors.textPrimary,
    fontSize: 13,
    lineHeight: 18,
  },
  group: {
    borderTopWidth: 1,
    borderTopColor: colors.cardBorder,
    paddingTop: 8,
    gap: 4,
  },
  groupHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  toggle: {
    width: 16,
    height: 16,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "transparent",
  },
  toggleOn: {
    backgroundColor: colors.accent,
  },
  toggleCheck: {
    color: colors.buttonPrimaryText,
    fontSize: 12,
    fontWeight: "700",
  },
  groupLabel: {
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: "600",
  },
  previewBlock: {
    paddingLeft: 24,
    gap: 2,
  },
  preview: {
    color: colors.textMuted,
    fontSize: 12,
  },
  row: {
    flexDirection: "row",
    gap: 8,
    marginTop: 6,
  },
  yes: {
    backgroundColor: colors.accent,
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 14,
  },
  yesDisabled: {
    backgroundColor: colors.buttonDisabledBg,
  },
  yesText: {
    color: colors.buttonPrimaryText,
    fontSize: 13,
    fontWeight: "700",
  },
  no: {
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 14,
  },
  noText: {
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: "600",
  },
  footnote: {
    color: colors.textMuted,
    fontSize: 11,
    fontStyle: "italic",
    marginTop: 4,
  },
});
