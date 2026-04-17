/**
 * /admin/integrations — Integration management admin screen
 *
 * Section 1: Connections (reads/writes integrations.connections config)
 * Section 2: Integration logs (stub)
 *
 * Permission: admin.manage_config
 */

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Redirect } from "expo-router";

import { shared, colors, fonts, radii } from "../../../lib/styles";
import { useHasPermission } from "../../../lib/permissions";
import { fetchConnectorAccounts, patchConnectorStatus } from "../../../lib/api";
import type { ConnectorAccountItem } from "../../../lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ConnectionStatus = "connected" | "needs_reauth" | "not_connected";
type ConnectionCategory = "calendar" | "finance" | "device" | "health" | string;

interface Connection {
  id: string;
  name: string;
  status: ConnectionStatus;
  category: ConnectionCategory;
}

const STATUS_META: Record<
  ConnectionStatus,
  { dot: string; label: string; bg: string; fg: string }
> = {
  connected: {
    dot: colors.green,
    label: "Connected",
    bg: colors.greenBg,
    fg: colors.greenText,
  },
  needs_reauth: {
    dot: colors.amber,
    label: "Needs reauth",
    bg: colors.amberBg,
    fg: colors.amberText,
  },
  not_connected: {
    dot: colors.muted,
    label: "Not connected",
    bg: "#F3F4F6",
    fg: "#6B7280",
  },
};

const CATEGORY_LABELS: Record<string, string> = {
  calendar: "Calendar",
  finance: "Finance",
  device: "Device",
  health: "Health",
};

// ---------------------------------------------------------------------------
// Connection row component
// ---------------------------------------------------------------------------

function ConnectionRow({
  connection,
  onAction,
  actionBusy,
}: {
  connection: Connection;
  onAction: (id: string, newStatus: ConnectionStatus) => void;
  actionBusy: string | null;
}) {
  const meta = STATUS_META[connection.status] ?? STATUS_META.not_connected;
  const isBusy = actionBusy === connection.id;

  return (
    <View style={connStyles.row}>
      <View style={[connStyles.statusDot, { backgroundColor: meta.dot }]} />
      <View style={connStyles.info}>
        <Text style={connStyles.name}>{connection.name}</Text>
        <Text style={connStyles.category}>
          {CATEGORY_LABELS[connection.category] ?? connection.category}
        </Text>
      </View>
      <View style={[connStyles.statusBadge, { backgroundColor: meta.bg }]}>
        <Text style={[connStyles.statusBadgeText, { color: meta.fg }]}>
          {meta.label}
        </Text>
      </View>
      <View style={connStyles.actions}>
        {isBusy ? (
          <ActivityIndicator size="small" color={colors.purple} />
        ) : connection.status === "connected" ? (
          <Pressable
            style={connStyles.btnDanger}
            onPress={() => onAction(connection.id, "not_connected")}
            accessibilityRole="button"
            accessibilityLabel={`Disconnect ${connection.name}`}
          >
            <Text style={connStyles.btnDangerText}>Disconnect</Text>
          </Pressable>
        ) : connection.status === "needs_reauth" ? (
          <Pressable
            style={connStyles.btnPrimary}
            onPress={() => onAction(connection.id, "connected")}
            accessibilityRole="button"
            accessibilityLabel={`Reconnect ${connection.name}`}
          >
            <Text style={connStyles.btnPrimaryText}>Reconnect</Text>
          </Pressable>
        ) : (
          <Pressable
            style={connStyles.btnPrimary}
            onPress={() => onAction(connection.id, "connected")}
            accessibilityRole="button"
            accessibilityLabel={`Connect ${connection.name}`}
          >
            <Text style={connStyles.btnPrimaryText}>Connect</Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Add integration form
// ---------------------------------------------------------------------------

function AddIntegrationForm({
  onAdd,
}: {
  onAdd: (connection: Connection) => void;
}) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [open, setOpen] = useState(false);

  const handleAdd = () => {
    if (!name.trim()) return;
    const id = name.toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "");
    onAdd({
      id,
      name: name.trim(),
      status: "not_connected",
      category: category.trim() || "other",
    });
    setName("");
    setCategory("");
    setOpen(false);
  };

  if (!open) {
    return (
      <Pressable
        style={addStyles.trigger}
        onPress={() => setOpen(true)}
        accessibilityRole="button"
        accessibilityLabel="Add integration"
      >
        <Text style={addStyles.triggerText}>+ Add integration</Text>
      </Pressable>
    );
  }

  return (
    <View style={addStyles.form}>
      <Text style={addStyles.formTitle}>Add integration</Text>
      <Text style={addStyles.label}>Name</Text>
      <TextInput
        style={addStyles.input as any}
        value={name}
        onChangeText={setName}
        placeholder="e.g. Spotify"
        placeholderTextColor={colors.muted}
        autoFocus
      />
      <Text style={addStyles.label}>Category</Text>
      <TextInput
        style={addStyles.input as any}
        value={category}
        onChangeText={setCategory}
        placeholder="e.g. health, finance, calendar"
        placeholderTextColor={colors.muted}
        autoCapitalize="none"
      />
      <View style={addStyles.btnRow}>
        <Pressable
          style={[addStyles.btn, addStyles.btnCancel]}
          onPress={() => { setOpen(false); setName(""); setCategory(""); }}
        >
          <Text style={addStyles.btnCancelText}>Cancel</Text>
        </Pressable>
        <Pressable
          style={[addStyles.btn, addStyles.btnSave, !name.trim() && addStyles.btnDisabled]}
          onPress={handleAdd}
          disabled={!name.trim()}
        >
          <Text style={addStyles.btnSaveText}>Add</Text>
        </Pressable>
      </View>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Main screen
// ---------------------------------------------------------------------------

/** Map a canonical ConnectorAccountItem to the local Connection view shape. */
function accountToConnection(account: ConnectorAccountItem): Connection {
  // Map canonical status vocabulary to ConnectionStatus for the UI
  const statusMap: Record<string, ConnectionStatus> = {
    connected: "connected",
    error: "needs_reauth",
    disconnected: "not_connected",
    stale: "needs_reauth",
    syncing: "connected",
    configured: "not_connected",
    disabled: "not_connected",
    decision_gated: "not_connected",
  };
  return {
    id: account.id,                         // use UUID as id for patch calls
    name: account.account_label ?? account.label,
    status: statusMap[account.status] ?? "not_connected",
    category: _categoryFromKey(account.connector_key),
  };
}

function _categoryFromKey(key: string): string {
  if (key === "google_calendar") return "calendar";
  if (key === "ynab" || key === "greenlight") return "finance";
  if (key === "apple_health" || key === "nike_run_club") return "health";
  if (key === "hearth_display") return "device";
  return "other";
}

/** Map ConnectionStatus used by the UI action to the canonical status string. */
function uiStatusToCanonical(status: ConnectionStatus): string {
  if (status === "connected") return "connected";
  if (status === "needs_reauth") return "error";
  return "disconnected";
}

export default function IntegrationsAdmin() {
  const canManage = useHasPermission("admin.manage_config");

  const [accounts, setAccounts] = useState<ConnectorAccountItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchConnectorAccounts()
      .then(setAccounts)
      .catch((e: any) => setError(e?.message ?? "Failed to load connections"))
      .finally(() => setLoading(false));
  }, []);

  const connections: Connection[] = accounts.map(accountToConnection);

  const handleAction = useCallback(
    (id: string, newStatus: ConnectionStatus) => {
      setActionBusy(id);
      setActionError(null);
      patchConnectorStatus(id, uiStatusToCanonical(newStatus))
        .then((updated) => {
          setAccounts((prev) =>
            prev.map((a) => (a.id === id ? updated : a))
          );
          setActionBusy(null);
        })
        .catch((e: any) => {
          setActionBusy(null);
          setActionError(e?.message ?? "Update failed");
        });
    },
    [],
  );

  // "Add integration" now points at the canonical connector registry.
  // For demo-readiness we keep the form but note that unknown connector_keys
  // are not in the registry and will be silently skipped by migration 038.
  const handleAdd = useCallback((_connection: Connection) => {
    // No-op in canonical mode: the connector registry is seeded by migration 022.
    // Future: could open an OAuth flow or a decision-gated request.
  }, []);

  if (!canManage) {
    return <Redirect href="/admin" />;
  }

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Integrations</Text>
      <Text style={styles.subtitle}>
        Manage connected services and third-party integrations for your family.
      </Text>

      {/* ------------------------------------------------------------------ */}
      {/* Section 1: Connections                                              */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Connections</Text>
        </View>

        {loading ? (
          <ActivityIndicator size="small" color={colors.purple} style={{ marginVertical: 12 }} />
        ) : error ? (
          <Text style={styles.errorText}>{error}</Text>
        ) : connections.length === 0 ? (
          <Text style={styles.empty}>No integrations configured yet.</Text>
        ) : (
          connections.map((conn, idx) => (
            <View key={conn.id}>
              {idx > 0 && <View style={styles.divider} />}
              <ConnectionRow
                connection={conn}
                onAction={handleAction}
                actionBusy={actionBusy}
              />
            </View>
          ))
        )}

        {actionError && (
          <Text style={styles.errorText}>{actionError}</Text>
        )}

        {!loading && (
          <View style={styles.addContainer}>
            <AddIntegrationForm onAdd={handleAdd} />
          </View>
        )}
      </View>

      {/* ------------------------------------------------------------------ */}
      {/* Section 2: Integration logs stub                                    */}
      {/* ------------------------------------------------------------------ */}
      <View style={shared.card}>
        <View style={shared.cardTitleRow}>
          <Text style={shared.cardTitle}>Integration logs</Text>
        </View>
        <Text style={styles.stubText}>
          Coming soon — recent sync events, errors, last-successful-sync per integration.
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
    marginTop: 8,
  },
  empty: {
    fontSize: 13,
    color: colors.muted,
    fontFamily: fonts.body,
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
  },
  addContainer: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  stubText: {
    fontSize: 13,
    color: colors.muted,
    fontFamily: fonts.body,
    lineHeight: 19,
  },
});

const connStyles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 10,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    flexShrink: 0,
  },
  info: {
    flex: 1,
  },
  name: {
    fontSize: 13,
    fontWeight: "500",
    color: colors.text,
    fontFamily: fonts.body,
  },
  category: {
    fontSize: 11,
    color: colors.muted,
    fontFamily: fonts.body,
    marginTop: 1,
  },
  statusBadge: {
    borderRadius: radii.md,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  statusBadgeText: {
    fontSize: 10,
    fontWeight: "700",
    fontFamily: fonts.body,
  },
  actions: {
    minWidth: 80,
    alignItems: "flex-end",
  },
  btnPrimary: {
    backgroundColor: colors.purple,
    borderRadius: radii.md,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  btnPrimaryText: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "600",
    fontFamily: fonts.body,
  },
  btnDanger: {
    backgroundColor: colors.redBg,
    borderRadius: radii.md,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: colors.red,
  },
  btnDangerText: {
    color: colors.redText,
    fontSize: 11,
    fontWeight: "600",
    fontFamily: fonts.body,
  },
});

const addStyles = StyleSheet.create({
  trigger: {
    paddingVertical: 6,
  },
  triggerText: {
    fontSize: 13,
    color: colors.purple,
    fontWeight: "500",
    fontFamily: fonts.body,
  },
  form: {
    gap: 8,
  },
  formTitle: {
    fontSize: 12,
    fontWeight: "600",
    color: colors.text,
    fontFamily: fonts.body,
    textTransform: "uppercase",
    letterSpacing: 0.4,
    marginBottom: 4,
  },
  label: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.muted,
    fontFamily: fonts.body,
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 13,
    color: colors.text,
    fontFamily: fonts.body,
    backgroundColor: colors.bg,
    outlineWidth: 0,
  } as any,
  btnRow: {
    flexDirection: "row",
    gap: 8,
    marginTop: 4,
  },
  btn: {
    borderRadius: radii.md,
    paddingVertical: 8,
    paddingHorizontal: 16,
    alignItems: "center",
  },
  btnCancel: {
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.card,
  },
  btnCancelText: {
    fontSize: 12,
    color: colors.muted,
    fontFamily: fonts.body,
    fontWeight: "500",
  },
  btnSave: {
    backgroundColor: colors.purple,
  },
  btnSaveText: {
    fontSize: 12,
    color: "#FFFFFF",
    fontFamily: fonts.body,
    fontWeight: "600",
  },
  btnDisabled: {
    backgroundColor: colors.border,
  },
});
