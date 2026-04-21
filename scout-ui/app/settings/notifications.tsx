import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { colors, fonts, shared } from "../../lib/styles";
import { useHasPermission } from "../../lib/permissions";
import {
  revokePushDevice,
  useFamilyPushDeliveries,
  useMyPushDeliveries,
  usePushRegistration,
  useRegisteredDevices,
  useSendTestPush,
} from "../../lib/push";
import { fetchMembers } from "../../lib/api";
import type { FamilyMember } from "../../lib/types";

function StatusDot({ ok, warn }: { ok?: boolean; warn?: boolean }) {
  const color = ok ? colors.green : warn ? colors.amber : colors.red;
  return <View style={[styles.dot, { backgroundColor: color }]} />;
}

function formatTs(ts: string | null): string {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

export default function NotificationSettings() {
  const canSendToMember = useHasPermission("push.send_to_member");
  const canViewFamilyLog = useHasPermission("push.view_delivery_log");

  const registration = usePushRegistration({ enabled: true });
  const { devices, loading: devicesLoading, reload: reloadDevices } = useRegisteredDevices();
  const { deliveries: myDeliveries, loading: myLoading, reload: reloadMy } = useMyPushDeliveries(20);

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>Notifications</Text>

      {/* Permission status */}
      <View style={shared.card}>
        <Text style={shared.cardTitle}>Permission status</Text>
        <PermissionStatusView state={registration} />
      </View>

      {/* Registered devices */}
      <View style={shared.card}>
        <View style={styles.headerRow}>
          <Text style={shared.cardTitle}>Registered devices</Text>
          <Pressable onPress={reloadDevices} accessibilityRole="button">
            <Text style={styles.linkText}>Refresh</Text>
          </Pressable>
        </View>
        {devicesLoading ? (
          <ActivityIndicator color={colors.purple} />
        ) : devices.length === 0 ? (
          <Text style={styles.muted}>No devices registered yet.</Text>
        ) : (
          devices.map((d) => (
            <View key={d.id} style={styles.deviceRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.deviceLabel}>
                  {d.device_label ?? "Unnamed device"} · {d.platform}
                </Text>
                <Text style={styles.muted}>
                  Last registered {formatTs(d.last_registered_at)} ·{" "}
                  {d.is_active ? "active" : "inactive"}
                </Text>
              </View>
              {d.is_active && (
                <Pressable
                  style={styles.btnSecondary}
                  onPress={async () => {
                    try {
                      await revokePushDevice(d.id);
                      await reloadDevices();
                    } catch {
                      /* ignore */
                    }
                  }}
                  accessibilityRole="button"
                  accessibilityLabel={`Revoke ${d.device_label ?? "device"}`}
                >
                  <Text style={styles.btnSecondaryText}>Revoke</Text>
                </Pressable>
              )}
            </View>
          ))
        )}
      </View>

      {/* My delivery log */}
      <View style={shared.card}>
        <View style={styles.headerRow}>
          <Text style={shared.cardTitle}>My recent notifications</Text>
          <Pressable onPress={reloadMy} accessibilityRole="button">
            <Text style={styles.linkText}>Refresh</Text>
          </Pressable>
        </View>
        {myLoading ? (
          <ActivityIndicator color={colors.purple} />
        ) : myDeliveries.length === 0 ? (
          <Text style={styles.muted}>Nothing yet.</Text>
        ) : (
          myDeliveries.map((d) => (
            <View key={d.id} style={styles.deliveryRow}>
              <StatusDot
                ok={d.status === "provider_handoff_ok"}
                warn={d.status === "provider_accepted" || d.status === "queued"}
              />
              <View style={{ flex: 1 }}>
                <Text style={styles.deliveryTitle}>{d.title}</Text>
                <Text style={styles.muted}>
                  {d.status} · {formatTs(d.sent_at ?? d.created_at)}
                </Text>
              </View>
            </View>
          ))
        )}
      </View>

      {/* Test push — admin / parent_peer only */}
      {canSendToMember && <TestPushCard />}

      {/* Family-wide delivery log — admin / parent_peer only */}
      {canViewFamilyLog && <FamilyDeliveryLog />}
    </ScrollView>
  );
}

function PermissionStatusView({ state }: { state: ReturnType<typeof usePushRegistration> }) {
  if (state.status === "unsupported") {
    const msg =
      state.reason === "web"
        ? "Push notifications are not supported in the web build. Install the Scout iOS app to receive notifications."
        : "This looks like a simulator. Install the Scout app on a physical device to receive push notifications.";
    return <Text style={styles.muted}>{msg}</Text>;
  }
  if (state.status === "idle" || state.status === "registering") {
    return <ActivityIndicator color={colors.purple} />;
  }
  if (state.status === "denied") {
    return (
      <View>
        <Text style={styles.errorText}>Notifications are blocked.</Text>
        <Text style={styles.muted}>
          Open iOS Settings → Notifications → Scout to allow notifications.
        </Text>
      </View>
    );
  }
  if (state.status === "error") {
    return <Text style={styles.errorText}>Registration error: {state.error}</Text>;
  }
  return (
    <View>
      <Text style={styles.successText}>Registered and ready.</Text>
      <Text style={styles.muted}>Token · …{state.token.slice(-8)}</Text>
    </View>
  );
}

function TestPushCard() {
  const { send, sending, error, lastResult } = useSendTestPush();
  const [members, setMembers] = useState<FamilyMember[]>([]);
  const [targetId, setTargetId] = useState<string>("");
  const [title, setTitle] = useState("Scout test");
  const [body, setBody] = useState("Hello from Scout");

  useEffect(() => {
    fetchMembers()
      .then((m) => {
        setMembers(m);
        if (m.length > 0 && !targetId) setTargetId(m[0].id);
      })
      .catch(() => {
        /* ignore */
      });
  }, []);

  return (
    <View style={shared.card}>
      <Text style={shared.cardTitle}>Send a test push</Text>
      <Text style={styles.muted}>Visible only to family admins.</Text>

      <View style={styles.memberRow}>
        {members.map((m) => (
          <Pressable
            key={m.id}
            onPress={() => setTargetId(m.id)}
            style={[styles.memberChip, targetId === m.id && styles.memberChipSelected]}
            accessibilityRole="button"
            accessibilityLabel={`Target ${m.first_name}`}
          >
            <Text
              style={[
                styles.memberChipText,
                targetId === m.id && styles.memberChipTextSelected,
              ]}
            >
              {m.first_name}
            </Text>
          </Pressable>
        ))}
      </View>

      <TextInput
        style={styles.input}
        value={title}
        onChangeText={setTitle}
        placeholder="Title"
        placeholderTextColor={colors.muted}
      />
      <TextInput
        style={styles.input}
        value={body}
        onChangeText={setBody}
        placeholder="Body"
        placeholderTextColor={colors.muted}
      />

      <Pressable
        style={styles.btnPrimary}
        onPress={() => {
          if (!targetId || !title || !body) return;
          send({ target_family_member_id: targetId, title, body }).catch(() => {
            /* error shown below */
          });
        }}
        disabled={sending || !targetId}
        accessibilityRole="button"
        accessibilityLabel="Send test push"
      >
        <Text style={styles.btnPrimaryText}>{sending ? "Sending…" : "Send test push"}</Text>
      </Pressable>

      {error && <Text style={styles.errorText}>{error}</Text>}
      {lastResult && (
        <Text style={styles.successText}>
          Sent. Accepted {lastResult.accepted_count} · errors {lastResult.error_count}.
        </Text>
      )}
    </View>
  );
}

function FamilyDeliveryLog() {
  const { deliveries, loading, reload } = useFamilyPushDeliveries(50);
  return (
    <View style={shared.card}>
      <View style={styles.headerRow}>
        <Text style={shared.cardTitle}>Family delivery log</Text>
        <Pressable onPress={reload} accessibilityRole="button">
          <Text style={styles.linkText}>Refresh</Text>
        </Pressable>
      </View>
      {loading ? (
        <ActivityIndicator color={colors.purple} />
      ) : deliveries.length === 0 ? (
        <Text style={styles.muted}>No recent deliveries.</Text>
      ) : (
        deliveries.map((d) => (
          <View key={d.id} style={styles.deliveryRow}>
            <StatusDot
              ok={d.status === "provider_handoff_ok"}
              warn={d.status === "provider_accepted" || d.status === "queued"}
            />
            <View style={{ flex: 1 }}>
              <Text style={styles.deliveryTitle}>{d.title}</Text>
              <Text style={styles.muted}>
                {d.trigger_source} · {d.status} · {formatTs(d.created_at)}
              </Text>
              {d.error_message && <Text style={styles.errorText}>{d.error_message}</Text>}
            </View>
          </View>
        ))
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 12, paddingBottom: 48 },
  h1: { fontSize: 22, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
  },
  linkText: { color: colors.purple, fontFamily: fonts.body, fontSize: 12 },
  muted: { color: colors.muted, fontFamily: fonts.body, fontSize: 12 },
  successText: { color: colors.green, fontFamily: fonts.body, fontSize: 12 },
  errorText: { color: colors.red, fontFamily: fonts.body, fontSize: 12 },

  deviceRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: 10,
  },
  deviceLabel: { fontFamily: fonts.body, fontSize: 13, color: colors.text, fontWeight: "500" },

  deliveryRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: 10,
  },
  deliveryTitle: { fontFamily: fonts.body, fontSize: 13, color: colors.text, fontWeight: "500" },

  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginTop: 5,
  },

  memberRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginBottom: 8 },
  memberChip: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 14,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  memberChipSelected: {
    backgroundColor: colors.purple,
    borderColor: colors.purple,
  },
  memberChipText: { color: colors.text, fontSize: 12, fontFamily: fonts.body },
  memberChipTextSelected: { color: "#FFFFFF" },

  input: {
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 9,
    fontSize: 12,
    color: colors.text,
    marginBottom: 8,
    fontFamily: fonts.body,
  },
  btnPrimary: {
    backgroundColor: colors.purple,
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: "center",
  },
  btnPrimaryText: { color: "#FFFFFF", fontSize: 12, fontWeight: "500", fontFamily: fonts.body },

  btnSecondary: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.bg,
  },
  btnSecondaryText: { color: colors.text, fontSize: 12, fontFamily: fonts.body },
});
