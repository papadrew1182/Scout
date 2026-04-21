/**
 * Frontend crash reporter.
 *
 * Sprint 2 Backlog #3 — ErrorBoundary, unhandledrejection, and
 * window.onerror all funnel through here. Every captured error POSTs
 * to /api/client-errors, which emits a structured `client_error` log
 * line that Railway's log tail picks up (no external provider
 * needed).
 *
 * Design notes:
 *   - Fire-and-forget: never awaits and never throws. A broken
 *     reporter must not turn a render crash into a double crash.
 *   - Token-aware: if the user is signed in, the backend attaches
 *     family_id / member_id to the log line via the existing Actor
 *     resolution. Works anonymously too (logs with nulls).
 *   - Rate-limited: one in-flight POST at a time per error signature
 *     so a crash-looping page can't DoS the backend.
 */

import { API_BASE_URL } from "./config";

export type ErrorSource =
  | "error_boundary"
  | "unhandled_rejection"
  | "window_error"
  | "manual";

export interface ErrorReport {
  message: string;
  stack?: string;
  url?: string;
  userAgent?: string;
  source?: ErrorSource;
  release?: string;
}

const _inflight = new Set<string>();

function _signature(r: ErrorReport): string {
  // Coalesce on message + first line of stack so a rerender loop
  // dedupes. Exact match — we're protecting the wire, not diagnosing.
  const firstStackLine = (r.stack ?? "").split("\n", 1)[0];
  return `${r.source}:${r.message}:${firstStackLine}`;
}

function _getToken(): string | null {
  try {
    return typeof localStorage !== "undefined"
      ? localStorage.getItem("scout_session_token")
      : null;
  } catch {
    return null;
  }
}

/**
 * Submit an error to the backend. Returns immediately; the actual
 * POST happens in the background. Never throws.
 */
export function report(r: ErrorReport): void {
  const sig = _signature(r);
  if (_inflight.has(sig)) return;
  _inflight.add(sig);

  const token = _getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const body = JSON.stringify({
    message: r.message.slice(0, 500),
    stack: r.stack?.slice(0, 8000),
    url:
      r.url ??
      (typeof window !== "undefined" ? window.location?.href : undefined),
    user_agent:
      r.userAgent ??
      (typeof navigator !== "undefined" ? navigator.userAgent : undefined),
    source: r.source ?? "manual",
    release: r.release,
  });

  fetch(`${API_BASE_URL}/api/client-errors`, {
    method: "POST",
    headers,
    body,
    // keepalive lets the POST complete even if the tab is closing
    // right after a crash. Max 64KB body — ours are well under.
    keepalive: true,
  })
    .catch(() => {
      // Silently drop; the crash itself is more important than the report.
    })
    .finally(() => {
      _inflight.delete(sig);
    });
}

/**
 * Install global handlers for unhandled promise rejections and
 * window.onerror. Safe to call multiple times; subsequent calls are
 * no-ops.
 */
let _installed = false;
export function installGlobalHandlers(): void {
  if (_installed) return;
  if (typeof window === "undefined") return;
  _installed = true;

  window.addEventListener("unhandledrejection", (event) => {
    const reason: unknown = (event as PromiseRejectionEvent).reason;
    const message =
      reason instanceof Error
        ? reason.message
        : typeof reason === "string"
          ? reason
          : "Unhandled promise rejection";
    const stack = reason instanceof Error ? reason.stack : undefined;
    report({ message, stack, source: "unhandled_rejection" });
  });

  window.addEventListener("error", (event) => {
    const e = event as ErrorEvent;
    if (!e.error && !e.message) return;
    const message = e.message || "Window error";
    const stack = e.error instanceof Error ? e.error.stack : undefined;
    report({ message, stack, source: "window_error" });
  });
}
