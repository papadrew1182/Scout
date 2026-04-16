/**
 * useHasPermission — per-key permission gate hook.
 *
 * Fetches the current actor's effective permissions from
 * GET /admin/permissions/me once on mount (one fetch per session,
 * cached in a module-level ref so re-renders are free).
 *
 * Returns true iff the actor holds the given permission key.
 * Returns false while loading or on error — UIs should treat
 * unknown permission state as "not granted" for safety.
 *
 * Usage:
 *   const canRunPayout = useHasPermission("allowance.run_payout");
 *   if (!canRunPayout) return null; // or render nothing
 */

import { useEffect, useRef, useState } from "react";
import { fetchMyPermissions } from "./api";

// Module-level cache so multiple calls to useHasPermission() in the same
// session share a single fetch. Invalidated on sign-out via clearPermissionsCache().
let _cachedPermissions: Record<string, boolean> | null = null;
let _fetchPromise: Promise<Record<string, boolean>> | null = null;

/** Call this on logout to force a re-fetch on the next session. */
export function clearPermissionsCache() {
  _cachedPermissions = null;
  _fetchPromise = null;
}

function loadPermissions(): Promise<Record<string, boolean>> {
  if (_cachedPermissions !== null) {
    return Promise.resolve(_cachedPermissions);
  }
  if (_fetchPromise !== null) {
    return _fetchPromise;
  }
  _fetchPromise = fetchMyPermissions().then((perms) => {
    _cachedPermissions = perms;
    _fetchPromise = null;
    return perms;
  }).catch((err) => {
    _fetchPromise = null;
    throw err;
  });
  return _fetchPromise;
}

/**
 * Returns true iff the current actor holds the given permission key.
 * Fetches permissions lazily on first call; subsequent calls use the cache.
 */
export function useHasPermission(key: string): boolean {
  const [hasPermission, setHasPermission] = useState<boolean>(() => {
    // Synchronous return from cache if already loaded
    return _cachedPermissions !== null ? Boolean(_cachedPermissions[key]) : false;
  });
  const keyRef = useRef(key);
  keyRef.current = key;

  useEffect(() => {
    // If already cached, sync the state (handles the case where the hook
    // mounts after the cache is populated but useState initializer ran first)
    if (_cachedPermissions !== null) {
      setHasPermission(Boolean(_cachedPermissions[keyRef.current]));
      return;
    }
    let cancelled = false;
    loadPermissions()
      .then((perms) => {
        if (!cancelled) {
          setHasPermission(Boolean(perms[keyRef.current]));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHasPermission(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return hasPermission;
}
