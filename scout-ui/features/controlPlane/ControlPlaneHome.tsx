/**
 * ControlPlaneHome — control-plane starter surface.
 *
 * Composes three sub-panels:
 *   - SyncStatusPanel       (counts from /api/control-plane/summary)
 *   - PublicationStatusPanel (calendar + reward buckets from summary)
 *   - ConnectorHealthPanel  (per-connector rows from /api/connectors
 *                            + /api/connectors/health)
 *
 * Every endpoint is real and DB-backed since Session 2 block 3 (commit
 * 3a3bf31). If /api/control-plane/summary errors at runtime,
 * ControlPlaneHome still renders the ConnectorHealthPanel from
 * /api/connectors + /api/connectors/health because those are
 * independent slices.
 *
 * No mutations. The charter explicitly forbids inventing reconnect /
 * approval / retry endpoints in this block.
 */

import { Pressable, StyleSheet, Text, View } from "react-native";

import { useControlPlaneSummary } from "../hooks";
import { classifySlice } from "../lib/availability";
import { ModeTag } from "../app/ModeTag";
import { colors } from "../../lib/styles";
import { ConnectorHealthPanel } from "./ConnectorHealthPanel";
import { SyncStatusPanel } from "./SyncStatusPanel";
import { PublicationStatusPanel } from "./PublicationStatusPanel";

export function ControlPlaneHome() {
  const summary = useControlPlaneSummary();

  // The summary slice can still error at runtime (network, auth, etc.).
  // We DO NOT block the rest of the page on it — the connector panel
  // reads independent endpoints.
  const view = classifySlice(
    { status: summary.status, error: summary.error, data: summary.data },
    "control_plane_summary",
  );
  const summaryUnavailable = view.kind === "error";

  return (
    <View>
      <Text style={styles.eyebrow}>Control plane</Text>
      <Text style={styles.title}>Connectors, sync, publication</Text>
      <ModeTag />
      <Text style={styles.subtle}>
        How Scout is talking to the outside world. No actions here yet —
        this is a read-only operating surface.
      </Text>

      {view.kind === "error" && (
        <View
          style={[styles.banner, styles.bannerErr]}
          accessible
          accessibilityLiveRegion="polite"
        >
          <Text style={styles.bannerTitle}>{view.title}</Text>
          <Text style={styles.bannerBody}>{view.body}</Text>
          <Pressable
            style={styles.retry}
            onPress={summary.refresh}
            accessibilityRole="button"
            accessibilityLabel="Retry loading control plane summary"
            hitSlop={10}
          >
            <Text style={styles.retryText}>Try again</Text>
          </Pressable>
        </View>
      )}

      <SectionLabel>Sync status</SectionLabel>
      <SyncStatusPanel
        connectors={summary.data?.connectors ?? null}
        syncJobs={summary.data?.sync_jobs ?? null}
        unavailable={summaryUnavailable}
      />

      <SectionLabel>Publication</SectionLabel>
      <PublicationStatusPanel
        calendarExports={summary.data?.calendar_exports ?? null}
        rewards={summary.data?.rewards ?? null}
        unavailable={summaryUnavailable}
      />

      <SectionLabel>Connector health</SectionLabel>
      <ConnectorHealthPanel />

      <Text style={styles.footnote}>
        Scout owns the operating model. Greenlight is payout-facing only.
        Hearth is display only. None of those are interactive from here.
      </Text>
    </View>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <Text style={styles.section}>{children}</Text>;
}

const styles = StyleSheet.create({
  eyebrow: {
    color: colors.accent,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1.6,
    textTransform: "uppercase",
  },
  title: {
    color: colors.textPrimary,
    fontSize: 30,
    fontWeight: "800",
    marginTop: 4,
    letterSpacing: -0.6,
  },
  subtle: {
    color: colors.textMuted,
    fontSize: 13,
    marginTop: 4,
    marginBottom: 16,
    lineHeight: 18,
  },
  section: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: "800",
    textTransform: "uppercase",
    letterSpacing: 1.4,
    marginTop: 22,
    marginBottom: 8,
  },
  banner: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 14,
    marginBottom: 4,
    borderLeftWidth: 3,
    borderLeftColor: colors.cardBorder,
  },
  bannerWarn: {
    backgroundColor: colors.warningBg,
    borderLeftColor: colors.warning,
  },
  bannerErr: {
    backgroundColor: colors.negativeBg,
    borderLeftColor: colors.negative,
  },
  bannerTitle: { color: colors.textPrimary, fontSize: 13, fontWeight: "800" },
  bannerBody: {
    color: colors.textSecondary,
    fontSize: 12,
    marginTop: 4,
    lineHeight: 16,
  },
  retry: {
    backgroundColor: colors.accent,
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 8,
    alignSelf: "flex-start",
    marginTop: 10,
  },
  retryText: {
    color: colors.buttonPrimaryText,
    fontWeight: "700",
    fontSize: 12,
  },
  footnote: {
    color: colors.textPlaceholder,
    fontSize: 11,
    marginTop: 24,
    textAlign: "center",
    paddingHorizontal: 16,
    lineHeight: 16,
    fontStyle: "italic",
  },
});
