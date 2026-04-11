/** Today's date as YYYY-MM-DD string. */
export function todayStr(): string {
  return new Date().toISOString().split("T")[0];
}

/** Monday of the current week as YYYY-MM-DD. */
export function weekStartStr(): string {
  const d = new Date();
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  const mon = new Date(d.setDate(diff));
  return mon.toISOString().split("T")[0];
}

/** Friday of the current week as YYYY-MM-DD. */
export function weekEndStr(): string {
  const ws = new Date(weekStartStr());
  ws.setDate(ws.getDate() + 4);
  return ws.toISOString().split("T")[0];
}

/** Format an event start time for display. */
export function formatEventTime(iso: string, allDay: boolean): string {
  const d = new Date(iso);
  if (allDay) {
    return d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
  }
  return d.toLocaleString([], {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** Format a time-only display for same-day events. */
export function formatTimeOnly(iso: string, allDay: boolean): string {
  if (allDay) return "all day";
  return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

/** Format a due_at timestamp for display. Returns null if input is null. */
export function formatDueAt(iso: string | null): string | null {
  if (!iso) return null;
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** Format a date-only string (YYYY-MM-DD) for display. */
export function formatDueDate(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString([], {
    month: "short",
    day: "numeric",
  });
}

/** Map a raw source string to a display label. Returns null for 'scout' (native, no badge needed). */
export function sourceLabel(source: string): string | null {
  switch (source) {
    case "google_cal": return "Google";
    case "ical": return "iCal";
    case "ynab": return "YNAB";
    case "apple_health": return "Apple Health";
    case "nike_run_club": return "NRC";
    default: return null; // 'scout' and unknown → no badge
  }
}
