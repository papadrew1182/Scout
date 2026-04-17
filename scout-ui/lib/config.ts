/**
 * Scout frontend configuration.
 *
 * Identity and family are derived from the auth session (see lib/auth.tsx).
 * API_BASE_URL is set via EXPO_PUBLIC_API_URL env var at build time,
 * falling back to localhost for local dev.
 *
 * Note: `process.env.EXPO_PUBLIC_API_URL` must be accessed as a literal
 * member expression so Metro can inline it at build time. Avoid optional
 * chaining or destructuring here.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchFamilyConfig, fetchMemberConfig, putFamilyConfig, putMemberConfig } from "./api";

// @ts-ignore - Expo injects process.env at build time
const envApiUrl: string | undefined = process.env.EXPO_PUBLIC_API_URL;
// @ts-ignore - Expo injects process.env at build time
const envE2E: string | undefined = process.env.EXPO_PUBLIC_SCOUT_E2E;

export const API_BASE_URL: string = envApiUrl || "http://localhost:8000";

export const DEV_MODE = !envApiUrl;

/**
 * E2E-only test hooks gate. Enables routes like `/__boom` that force a
 * render crash so the global ErrorBoundary can be verified. Set
 * `EXPO_PUBLIC_SCOUT_E2E=true` in the expo export env for smoke runs.
 * Never set in production builds — the route is a no-op otherwise.
 */
export const E2E_TEST_HOOKS = envE2E === "true";

// ---------------------------------------------------------------------------
// useFamilyConfig — read + write a single family_config key
// ---------------------------------------------------------------------------

export interface UseFamilyConfigResult<T> {
  value: T;
  setValue: (v: T) => Promise<void>;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * Hook that reads and writes a family_config key via the admin config API.
 *
 * On mount, fetches GET /admin/config/family and picks the row matching `key`.
 * If the key is absent the hook returns `defaultValue`.
 *
 * `setValue` performs an optimistic update: the local state is set immediately,
 * the PUT is fired, and on error the previous value is restored.
 *
 * `refresh` forces a re-fetch from the server.
 *
 * Requires the actor to hold admin.view_config (to fetch) and
 * admin.manage_config (to set). Permission errors surface as `error`.
 */
export function useFamilyConfig<T = unknown>(
  key: string,
  defaultValue: T,
): UseFamilyConfigResult<T> {
  const [value, setValueState] = useState<T>(defaultValue);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const refreshCounterRef = useRef<number>(0);

  const doFetch = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchFamilyConfig()
      .then((rows) => {
        const row = rows.find((r) => r.key === key);
        setValueState(row ? (row.value as T) : defaultValue);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load config");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    doFetch();
  }, [doFetch, refreshCounterRef.current]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = useCallback(() => {
    refreshCounterRef.current += 1;
    doFetch();
  }, [doFetch]);

  const setValue = useCallback(
    async (newValue: T): Promise<void> => {
      const previous = value;
      // Optimistic update
      setValueState(newValue);
      setError(null);
      try {
        await putFamilyConfig(key, newValue);
      } catch (err: unknown) {
        // Revert on failure
        setValueState(previous);
        setError(err instanceof Error ? err.message : "Failed to save config");
        throw err;
      }
    },
    [key, value],
  );

  return { value, setValue, loading, error, refresh };
}

// ---------------------------------------------------------------------------
// useMemberConfig — read + write a single member_config key
// ---------------------------------------------------------------------------

export interface UseMemberConfigResult<T> {
  value: T;
  setValue: (v: T) => Promise<void>;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * Hook that reads and writes a member_config key via the admin config API.
 *
 * On mount (or when memberId changes), fetches
 * GET /admin/config/member/{memberId} and picks the row matching `key`.
 * If the key is absent the hook returns `defaultValue`.
 * If `memberId` is null/undefined the hook stays in loading=false with
 * defaultValue and no fetch is made.
 *
 * `setValue` performs an optimistic update: the local state is set immediately,
 * the PUT is fired, and on error the previous value is restored.
 *
 * `refresh` forces a re-fetch from the server.
 */
export function useMemberConfig<T = unknown>(
  memberId: string | null | undefined,
  key: string,
  defaultValue: T,
): UseMemberConfigResult<T> {
  const [value, setValueState] = useState<T>(defaultValue);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const refreshCounterRef = useRef<number>(0);

  const doFetch = useCallback(() => {
    if (!memberId) {
      setLoading(false);
      setValueState(defaultValue);
      return;
    }
    setLoading(true);
    setError(null);
    fetchMemberConfig(memberId)
      .then((rows) => {
        const row = rows.find((r) => r.key === key);
        setValueState(row ? (row.value as T) : defaultValue);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load config");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [memberId, key]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    doFetch();
  }, [doFetch, refreshCounterRef.current]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = useCallback(() => {
    refreshCounterRef.current += 1;
    doFetch();
  }, [doFetch]);

  const setValue = useCallback(
    async (newValue: T): Promise<void> => {
      if (!memberId) throw new Error("memberId is required to set config");
      const previous = value;
      // Optimistic update
      setValueState(newValue);
      setError(null);
      try {
        await putMemberConfig(memberId, key, newValue);
      } catch (err: unknown) {
        // Revert on failure
        setValueState(previous);
        setError(err instanceof Error ? err.message : "Failed to save config");
        throw err;
      }
    },
    [memberId, key, value],
  );

  return { value, setValue, loading, error, refresh };
}
