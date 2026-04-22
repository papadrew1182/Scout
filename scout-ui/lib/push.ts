/**
 * Push notifications — API layer + React hooks.
 *
 * Registration runs on native only. On web and simulator the hook
 * short-circuits with an informative state so the settings screen can
 * render a non-error banner.
 *
 * All network calls respect the same auth headers as the rest of the
 * app (token is set by AuthProvider via setApiToken).
 */

import { useCallback, useEffect, useState } from "react";
import { Platform } from "react-native";
import Constants from "expo-constants";
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { router } from "expo-router";

import { API_BASE_URL } from "./config";
import { authHeaders } from "./api";

// Module-level so the handler is registered before any notification
// can arrive — expo-notifications keeps the last-set handler and will
// consult it synchronously on delivery. Without this, iOS suppresses
// visual display while the app is in the foreground (Apple default).
//
// `shouldShowAlert` is the legacy SDK ≤52 name; `shouldShowBanner` +
// `shouldShowList` are the SDK 52+ split. Both are safe to set — the
// SDK reads whichever it recognizes and ignores the other.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

export type PushPermissionStatus =
  | "undetermined"
  | "granted"
  | "denied"
  | "unsupported"
  | "simulator";

export type RegistrationState =
  | { status: "idle" }
  | { status: "unsupported"; reason: string }
  | { status: "denied" }
  | { status: "registering" }
  | { status: "registered"; deviceId: string; token: string }
  | { status: "error"; error: string };

export interface PushDevice {
  id: string;
  family_member_id: string;
  device_label: string | null;
  platform: string;
  app_version: string | null;
  is_active: boolean;
  last_registered_at: string;
  last_successful_delivery_at: string | null;
}

export interface PushDelivery {
  id: string;
  notification_group_id: string;
  family_member_id: string;
  push_device_id: string;
  category: string;
  title: string;
  body: string;
  data: Record<string, unknown>;
  trigger_source: string;
  status: "queued" | "provider_accepted" | "provider_handoff_ok" | "provider_error";
  provider_ticket_id: string | null;
  error_message: string | null;
  sent_at: string | null;
  provider_handoff_at: string | null;
  tapped_at: string | null;
  created_at: string;
}

export interface TestSendResult {
  notification_group_id: string;
  delivery_ids: string[];
  accepted_count: number;
  error_count: number;
}

// ---------------------------------------------------------------------------
// API wrappers
// ---------------------------------------------------------------------------

async function jsonOr<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${text}`.trim());
  }
  return (await res.json()) as T;
}

export async function registerPushDevice(input: {
  expo_push_token: string;
  platform: "ios" | "android" | "web";
  device_label?: string | null;
  app_version?: string | null;
}): Promise<PushDevice> {
  const res = await fetch(`${API_BASE_URL}/api/push/devices`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(input),
  });
  return jsonOr<PushDevice>(res);
}

export async function listMyDevices(): Promise<PushDevice[]> {
  const res = await fetch(`${API_BASE_URL}/api/push/devices/me`, { headers: authHeaders() });
  return jsonOr<PushDevice[]>(res);
}

export async function revokePushDevice(deviceId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/push/devices/${deviceId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`${res.status}`);
}

export async function listMyDeliveries(limit = 50): Promise<PushDelivery[]> {
  const res = await fetch(`${API_BASE_URL}/api/push/deliveries/me?limit=${limit}`, {
    headers: authHeaders(),
  });
  return jsonOr<PushDelivery[]>(res);
}

export async function listFamilyDeliveries(limit = 50): Promise<PushDelivery[]> {
  const res = await fetch(`${API_BASE_URL}/api/push/deliveries?limit=${limit}`, {
    headers: authHeaders(),
  });
  return jsonOr<PushDelivery[]>(res);
}

export async function recordTap(deliveryId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/push/deliveries/${deliveryId}/tap`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok && res.status !== 204) throw new Error(`${res.status}`);
}

export async function sendTestPush(input: {
  target_family_member_id: string;
  title: string;
  body: string;
  category?: string;
  data?: Record<string, unknown>;
}): Promise<TestSendResult> {
  const res = await fetch(`${API_BASE_URL}/api/push/test-send`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(input),
  });
  return jsonOr<TestSendResult>(res);
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useRegisteredDevices() {
  const [devices, setDevices] = useState<PushDevice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setDevices(await listMyDevices());
      setError(null);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load devices");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  return { devices, loading, error, reload };
}

export function useMyPushDeliveries(limit = 50) {
  const [deliveries, setDeliveries] = useState<PushDelivery[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setDeliveries(await listMyDeliveries(limit));
      setError(null);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load deliveries");
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { deliveries, loading, error, reload };
}

export function useFamilyPushDeliveries(limit = 50) {
  const [deliveries, setDeliveries] = useState<PushDelivery[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setDeliveries(await listFamilyDeliveries(limit));
      setError(null);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load family deliveries");
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    reload();
  }, [reload]);

  return { deliveries, loading, error, reload };
}

export function useSendTestPush() {
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<TestSendResult | null>(null);

  const send = useCallback(
    async (input: {
      target_family_member_id: string;
      title: string;
      body: string;
      category?: string;
    }) => {
      setSending(true);
      setError(null);
      try {
        const r = await sendTestPush(input);
        setLastResult(r);
        return r;
      } catch (e: any) {
        setError(e?.message ?? "Send failed");
        throw e;
      } finally {
        setSending(false);
      }
    },
    [],
  );

  return { send, sending, error, lastResult };
}

/**
 * Request permission, register the Expo push token with the backend,
 * and handle tap-to-open routing.
 *
 * Native platforms only — web / simulator short-circuit with a
 * non-error state the settings screen can render.
 */
export function usePushRegistration(opts: { enabled: boolean }) {
  const [state, setState] = useState<RegistrationState>({ status: "idle" });

  useEffect(() => {
    if (!opts.enabled) return;
    if (Platform.OS === "web") {
      setState({ status: "unsupported", reason: "web" });
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        if (!Device.isDevice) {
          if (!cancelled) setState({ status: "unsupported", reason: "simulator" });
          return;
        }

        const existing = await Notifications.getPermissionsAsync();
        let finalStatus = existing.status;
        if (finalStatus !== "granted") {
          const asked = await Notifications.requestPermissionsAsync();
          finalStatus = asked.status;
        }
        if (finalStatus !== "granted") {
          if (!cancelled) setState({ status: "denied" });
          return;
        }

        if (!cancelled) setState({ status: "registering" });

        const projectId =
          (Constants.expoConfig as any)?.extra?.eas?.projectId ||
          (Constants as any).easConfig?.projectId;

        const tokenResponse = projectId
          ? await Notifications.getExpoPushTokenAsync({ projectId })
          : await Notifications.getExpoPushTokenAsync();

        const device = await registerPushDevice({
          expo_push_token: tokenResponse.data,
          platform: Platform.OS === "ios" ? "ios" : "android",
          device_label: Device.deviceName ?? null,
          app_version: Constants.expoConfig?.version ?? null,
        });

        if (!cancelled) {
          setState({ status: "registered", deviceId: device.id, token: tokenResponse.data });
        }

        // Handle tap-to-open when the app is launched from a
        // notification. Records the tap + deep-links to route_hint.
        const lastResponse = await Notifications.getLastNotificationResponseAsync();
        if (lastResponse) handleTapResponse(lastResponse);

        const sub = Notifications.addNotificationResponseReceivedListener(handleTapResponse);
        return () => {
          sub.remove();
        };
      } catch (e: any) {
        if (!cancelled) {
          setState({ status: "error", error: e?.message ?? "Registration failed" });
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [opts.enabled]);

  return state;
}

function handleTapResponse(response: any) {
  const data = response?.notification?.request?.content?.data ?? {};
  const deliveryId = data.scout_delivery_id;
  const routeHint = data.route_hint;
  if (deliveryId && typeof deliveryId === "string") {
    recordTap(deliveryId).catch(() => {
      // tap logging is best-effort
    });
  }
  if (routeHint && typeof routeHint === "string") {
    try {
      router.push(routeHint as any);
    } catch {
      // ignore — route_hint may not match any registered route
    }
  }
}
