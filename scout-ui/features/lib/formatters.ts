/**
 * Tiny formatting helpers for the Session 3 surfaces.
 * Kept dependency-free so they run identically in tests and in RN-Web.
 */

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  let h = d.getHours();
  const m = d.getMinutes();
  const ampm = h >= 12 ? "PM" : "AM";
  h = h % 12 || 12;
  return `${h}:${m.toString().padStart(2, "0")} ${ampm}`;
}

export function formatRelativeDue(iso: string | null | undefined): string {
  if (!iso) return "";
  const due = new Date(iso).getTime();
  const now = Date.now();
  const diff = due - now;
  const min = Math.round(diff / 60_000);
  if (min === 0) return "now";
  if (min > 0 && min < 60) return `in ${min} min`;
  if (min < 0 && min > -60) return `${-min} min late`;
  const hours = Math.round(min / 60);
  if (hours > 0 && hours < 12) return `in ${hours}h`;
  if (hours < 0 && hours > -12) return `${-hours}h late`;
  return formatTime(iso);
}

export function formatCents(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const dollars = Math.floor(abs / 100);
  const remainder = abs % 100;
  return `${sign}$${dollars}.${remainder.toString().padStart(2, "0")}`;
}

export function pluralize(count: number, one: string, many: string): string {
  return count === 1 ? `${count} ${one}` : `${count} ${many}`;
}
