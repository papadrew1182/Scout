/**
 * BlockCard — one routine block (Morning / After School / Evening / etc.)
 *
 * Aligned to the canonical HouseholdBlock shape from canonical.py. The
 * block carries `label`, `due_at`, `status`, `member_family_member_ids`,
 * and `occurrences[]`. Owner avatars are stubbed from the member id
 * list since the canonical contract does not echo back full names per
 * member at the block level — full names are available on the
 * occurrence rows themselves.
 */

import { StyleSheet, Text, View } from "react-native";

import { HouseholdBlock, TaskOccurrence } from "../lib/contracts";
import { useFamilyContext } from "../hooks";
import { formatRelativeDue, formatTime } from "../lib/formatters";
import { colors } from "../../lib/styles";
import { ChoreList } from "./ChoreList";

interface Props {
  block: HouseholdBlock;
}

export function BlockCard({ block }: Props) {
  const family = useFamilyContext();
  // Resolve the kid names referenced by the block. Adults and kids are
  // both modeled, but block.member_family_member_ids in practice holds
  // child IDs. We look them up against family_context.kids and fall
  // back to whatever owner_name is on the first occurrence.
  const memberNames = resolveMemberNames(block, family.data?.kids);

  return (
    <View style={[styles.card, statusCardStyle(block.status)]}>
      <View style={styles.headerRow}>
        <View style={styles.titleCol}>
          <Text style={styles.title}>{block.label}</Text>
          <Text style={styles.due}>
            {block.due_at ? `Due ${formatTime(block.due_at)}` : "No deadline"}
            {block.due_at && block.status !== "done"
              ? ` · ${formatRelativeDue(block.due_at)}`
              : ""}
          </Text>
        </View>
        <StatusPill status={block.status} />
      </View>

      {memberNames.length > 0 && (
        <View style={styles.peopleRow}>
          {memberNames.map((m) => (
            <View key={m} style={styles.avatar}>
              <Text style={styles.avatarText}>{m[0]}</Text>
            </View>
          ))}
          <Text style={styles.peopleLabel}>{memberNames.join(" · ")}</Text>
        </View>
      )}

      {block.note && <Text style={styles.note}>{block.note}</Text>}

      <ChoreList occurrences={block.occurrences} />
    </View>
  );
}

function resolveMemberNames(
  block: HouseholdBlock,
  kids: { family_member_id: string; name: string }[] | undefined,
): string[] {
  if (kids && kids.length) {
    const map = new Map(kids.map((k) => [k.family_member_id, k.name]));
    const mapped = block.member_family_member_ids
      .map((id) => map.get(id))
      .filter((n): n is string => !!n);
    if (mapped.length) return mapped;
  }
  // Fallback: pull unique owner names off the occurrences themselves.
  const seen = new Set<string>();
  const out: string[] = [];
  for (const o of block.occurrences) {
    const n = o.owner_name;
    if (n && !seen.has(n)) {
      seen.add(n);
      out.push(n);
    }
  }
  return out;
}

function StatusPill({ status }: { status: HouseholdBlock["status"] }) {
  return (
    <View style={[styles.pill, pillStyle(status)]}>
      <Text style={[styles.pillText, pillTextStyle(status)]}>
        {labelForStatus(status)}
      </Text>
    </View>
  );
}

function labelForStatus(s: HouseholdBlock["status"]): string {
  switch (s) {
    case "active":
      return "Active now";
    case "due_soon":
      return "Due soon";
    case "late":
      return "Late";
    case "done":
      return "Done";
    case "blocked":
      return "Blocked";
    case "upcoming":
    default:
      return "Upcoming";
  }
}

function statusCardStyle(s: HouseholdBlock["status"]) {
  switch (s) {
    case "late":
    case "blocked":
      return { borderLeftColor: colors.negative };
    case "due_soon":
      return { borderLeftColor: colors.warning };
    case "active":
      return { borderLeftColor: colors.accent };
    case "done":
      return { borderLeftColor: colors.positive, opacity: 0.85 };
    default:
      return { borderLeftColor: colors.cardBorder };
  }
}

function pillStyle(s: HouseholdBlock["status"]) {
  switch (s) {
    case "late":
    case "blocked":
      return { backgroundColor: colors.negativeBg };
    case "due_soon":
      return { backgroundColor: colors.warningBg };
    case "active":
      return { backgroundColor: colors.accentBg };
    case "done":
      return { backgroundColor: colors.positiveBg };
    default:
      return { backgroundColor: colors.surfaceMuted };
  }
}

function pillTextStyle(s: HouseholdBlock["status"]) {
  switch (s) {
    case "late":
    case "blocked":
      return { color: "#C0392B" };
    case "due_soon":
      return { color: "#A2660C" };
    case "active":
      return { color: colors.accent };
    case "done":
      return { color: "#00866B" };
    default:
      return { color: colors.textSecondary };
  }
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderLeftWidth: 4,
    borderLeftColor: colors.cardBorder,
    padding: 16,
    marginBottom: 14,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  titleCol: { flexShrink: 1, paddingRight: 10 },
  title: {
    color: colors.textPrimary,
    fontSize: 17,
    fontWeight: "700",
    letterSpacing: -0.2,
  },
  due: {
    color: colors.textMuted,
    fontSize: 12,
    marginTop: 3,
    fontWeight: "600",
  },
  pill: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },
  pillText: {
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 0.6,
    textTransform: "uppercase",
  },
  peopleRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 12,
    marginBottom: 4,
    flexWrap: "wrap",
  },
  avatar: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.accentBg,
    alignItems: "center",
    justifyContent: "center",
    marginRight: -4,
    borderWidth: 1.5,
    borderColor: colors.card,
  },
  avatarText: { color: colors.accent, fontSize: 10, fontWeight: "800" },
  peopleLabel: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: "600",
    marginLeft: 8,
  },
  note: {
    color: colors.textSecondary,
    fontSize: 12,
    fontStyle: "italic",
    marginTop: 8,
  },
});
