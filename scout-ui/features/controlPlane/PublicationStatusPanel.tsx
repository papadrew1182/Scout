/**
 * PublicationStatusPanel — calendar export + reward approval surface.
 *
 * Reads the `calendar_exports` and `rewards` buckets from
 * /api/control-plane/summary. Renders two tiles:
 *
 *   1. Calendar exports: pending count + failed count. If failed > 0
 *      the tile flips to negative tone — these are anchor blocks that
 *      didn't reach Google Calendar (and therefore won't reach Hearth).
 *   2. Reward approval: pending_approval_count. This is read-only
 *      because the charter does not ship an approval mutation in this
 *      block. Parent-tier sees a hint; non-parents see a plain count.
 */

import { StyleSheet, Text, View } from "react-native";

import {
  ControlPlaneCalendarExportsBucket,
  ControlPlaneRewardsBucket,
} from "../lib/contracts";
import { useIsParent } from "../hooks";
import { colors } from "../../lib/styles";

interface Props {
  calendarExports: ControlPlaneCalendarExportsBucket | null;
  rewards: ControlPlaneRewardsBucket | null;
  unavailable: boolean;
}

export function PublicationStatusPanel({
  calendarExports,
  rewards,
  unavailable,
}: Props) {
  const isParent = useIsParent();

  if (unavailable) {
    return (
      <View style={[styles.panel, styles.unavailable]}>
        <Text style={styles.unavailableText}>
          Summary feed unavailable — counts will appear once
          /api/control-plane/summary ships.
        </Text>
      </View>
    );
  }

  const failedExports = calendarExports?.failed_count ?? 0;
  const pendingExports = calendarExports?.pending_count ?? 0;
  const pendingApprovals = rewards?.pending_approval_count ?? 0;

  return (
    <View style={styles.row}>
      <View
        style={[
          styles.tile,
          failedExports > 0 && styles.tileError,
          failedExports === 0 && pendingExports > 0 && styles.tileWarn,
        ]}
      >
        <Text style={styles.tileLabel}>Calendar exports</Text>
        <View style={styles.tileNumbers}>
          <View style={styles.tileNumberCell}>
            <Text style={styles.tileNumber}>{pendingExports}</Text>
            <Text style={styles.tileNumberLabel}>pending</Text>
          </View>
          <View style={styles.tileNumberCell}>
            <Text
              style={[
                styles.tileNumber,
                failedExports > 0 && { color: colors.negative },
              ]}
            >
              {failedExports}
            </Text>
            <Text style={styles.tileNumberLabel}>failed</Text>
          </View>
        </View>
      </View>

      <View
        style={[styles.tile, pendingApprovals > 0 && styles.tileWarn]}
      >
        <Text style={styles.tileLabel}>Reward approvals</Text>
        <View style={styles.tileNumbers}>
          <View style={styles.tileNumberCell}>
            <Text
              style={[
                styles.tileNumber,
                pendingApprovals > 0 && { color: colors.warning },
              ]}
            >
              {pendingApprovals}
            </Text>
            <Text style={styles.tileNumberLabel}>pending</Text>
          </View>
        </View>
        {isParent && pendingApprovals > 0 && (
          <Text style={styles.parentHint}>Open Rewards to review.</Text>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  panel: {
    backgroundColor: colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 14,
  },
  unavailable: { backgroundColor: colors.surfaceMuted },
  unavailableText: {
    color: colors.textMuted,
    fontSize: 12,
    textAlign: "center",
    paddingVertical: 6,
  },
  row: {
    flexDirection: "row",
    gap: 10,
  },
  tile: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 12,
  },
  tileWarn: { backgroundColor: colors.warningBg, borderColor: colors.warning },
  tileError: { backgroundColor: colors.negativeBg, borderColor: colors.negative },
  tileLabel: {
    color: colors.textSecondary,
    fontSize: 10,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 0.8,
    marginBottom: 8,
  },
  tileNumbers: {
    flexDirection: "row",
    gap: 14,
  },
  tileNumberCell: { alignItems: "flex-start" },
  tileNumber: {
    color: colors.textPrimary,
    fontSize: 24,
    fontWeight: "800",
    fontVariant: ["tabular-nums"] as any,
  },
  tileNumberLabel: {
    color: colors.textMuted,
    fontSize: 10,
    fontWeight: "700",
    textTransform: "uppercase",
    letterSpacing: 0.6,
  },
  parentHint: {
    color: colors.textSecondary,
    fontSize: 11,
    marginTop: 8,
    fontWeight: "600",
  },
});
