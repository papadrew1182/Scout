/**
 * BlockCard — one routine block (Morning / After School / Evening / Power 60 / etc.)
 *
 * Renders a status pill, due-time badge, owner avatars, an optional
 * note ("ODD day → Townes"), and an inline ChoreList of the block's
 * task occurrences.
 *
 * Quiet-enforcement principle from family_chore_system.md: the card
 * shows status; it does not nag. The single inline reminder copy is
 * left to the parent, not the UI.
 */

import { StyleSheet, Text, View } from "react-native";

import { BlockStatus, RoutineBlock } from "../lib/contracts";
import { formatRelativeDue, formatTime } from "../lib/formatters";
import { colors } from "../../lib/styles";
import { ChoreList } from "./ChoreList";

interface Props {
  block: RoutineBlock;
}

export function BlockCard({ block }: Props) {
  return (
    <View style={[styles.card, statusCardStyle(block.status)]}>
      <View style={styles.headerRow}>
        <View style={styles.titleCol}>
          <Text style={styles.title}>{block.title}</Text>
          <Text style={styles.due}>
            Due {formatTime(block.due_at)}
            {block.status !== "done" ? ` · ${formatRelativeDue(block.due_at)}` : ""}
          </Text>
        </View>
        <StatusPill status={block.status} />
      </View>

      {block.members.length > 0 && (
        <View style={styles.peopleRow}>
          {block.members.map((m) => (
            <View key={m.member_id} style={styles.avatar}>
              <Text style={styles.avatarText}>{m.first_name[0]}</Text>
            </View>
          ))}
          <Text style={styles.peopleLabel}>
            {block.members.map((m) => m.first_name).join(" · ")}
          </Text>
        </View>
      )}

      {block.note && <Text style={styles.note}>{block.note}</Text>}

      {block.blocked_reason && (
        <View style={styles.blockedRow}>
          <Text style={styles.blockedLabel}>Blocked:</Text>
          <Text style={styles.blockedText}>{block.blocked_reason}</Text>
        </View>
      )}

      <ChoreList occurrences={block.occurrences} />
    </View>
  );
}

function StatusPill({ status }: { status: BlockStatus }) {
  const label = labelForStatus(status);
  return (
    <View style={[styles.pill, pillStyle(status)]}>
      <Text style={[styles.pillText, pillTextStyle(status)]}>{label}</Text>
    </View>
  );
}

function labelForStatus(s: BlockStatus): string {
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

function statusCardStyle(s: BlockStatus) {
  switch (s) {
    case "late":
      return { borderLeftColor: colors.negative };
    case "due_soon":
      return { borderLeftColor: colors.warning };
    case "active":
      return { borderLeftColor: colors.accent };
    case "done":
      return { borderLeftColor: colors.positive, opacity: 0.85 };
    case "blocked":
      return { borderLeftColor: colors.negative };
    default:
      return { borderLeftColor: colors.cardBorder };
  }
}

function pillStyle(s: BlockStatus) {
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

function pillTextStyle(s: BlockStatus) {
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
  blockedRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 8,
    backgroundColor: colors.negativeBg,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  blockedLabel: {
    color: "#C0392B",
    fontSize: 11,
    fontWeight: "800",
    marginRight: 6,
    textTransform: "uppercase",
  },
  blockedText: { color: "#C0392B", fontSize: 12, flexShrink: 1 },
});
