import { splitStoreDateTime } from "@/lib/productAdmin";

// The Admin dashboard's ONE global date range. Dates are plain "YYYY-MM-DD" calendar days in the store's time zone
// (Asia/Dhaka — the zone the backend reads date_from/date_to in, inclusive), and the range lives in the URL
// (?range=this_month, or ?range=custom&from=…&to=…) so a refresh or a shared link keeps it. Weeks start on Saturday,
// the working week in Bangladesh.
const WEEK_START = 6; // Saturday (0 = Sunday)

// "YYYY-MM-DD" -> "Sep 23, 2026" from the calendar date alone (no time zone shift). Kept here, not imported from the
// date picker, because this module is also used by Server Components and the picker is a Client Component.
export function formatCalendarDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { day: "numeric", month: "short", year: "numeric" });
}

export const todayIso = () => splitStoreDateTime(new Date().toISOString()).date;

function shift(iso, days) {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
const weekday = (iso) => new Date(`${iso}T00:00:00Z`).getUTCDay();
const startOfWeek = (iso) => shift(iso, -((weekday(iso) - WEEK_START + 7) % 7));
const endOfMonth = (iso) => {
  const d = new Date(`${iso.slice(0, 8)}01T00:00:00Z`);
  d.setUTCMonth(d.getUTCMonth() + 1, 0);
  return d.toISOString().slice(0, 10);
};
const monthsBack = (iso, n) => {
  const d = new Date(`${iso.slice(0, 8)}01T00:00:00Z`);
  d.setUTCMonth(d.getUTCMonth() - n);
  return d.toISOString().slice(0, 10);
};

export const RANGE_PRESETS = [
  { key: "today", label: "Today", range: (t) => ({ start: t, end: t }) },
  { key: "yesterday", label: "Yesterday", range: (t) => ({ start: shift(t, -1), end: shift(t, -1) }) },
  { key: "this_week", label: "This Week", range: (t) => ({ start: startOfWeek(t), end: t }) },
  { key: "last_week", label: "Last Week", range: (t) => ({ start: shift(startOfWeek(t), -7), end: shift(startOfWeek(t), -1) }) },
  { key: "this_month", label: "This Month", range: (t) => ({ start: `${t.slice(0, 8)}01`, end: t }) },
  { key: "last_month", label: "Last Month", range: (t) => ({ start: monthsBack(t, 1), end: endOfMonth(monthsBack(t, 1)) }) },
  { key: "this_year", label: "This Year", range: (t) => ({ start: `${t.slice(0, 4)}-01-01`, end: t }) },
  { key: "last_year", label: "Last Year", range: (t) => ({ start: `${Number(t.slice(0, 4)) - 1}-01-01`, end: `${Number(t.slice(0, 4)) - 1}-12-31` }) },
];
export const DEFAULT_PRESET = "this_month";
const ISO = /^\d{4}-\d{2}-\d{2}$/;

// { preset, start, end } from URL search params (a plain object or URLSearchParams); falls back to the default.
export function rangeFromParams(params) {
  const get = (k) => (typeof params?.get === "function" ? params.get(k) : params?.[k]) ?? null;
  const key = get("range");
  const from = get("from");
  const to = get("to");
  if (key === "custom" && ISO.test(from ?? "") && ISO.test(to ?? "") && from <= to) return { preset: "custom", start: from, end: to };
  const preset = RANGE_PRESETS.find((p) => p.key === key) ?? RANGE_PRESETS.find((p) => p.key === DEFAULT_PRESET);
  return { preset: preset.key, ...preset.range(todayIso()) };
}

export function rangeToQuery(range) {
  return range.preset === "custom" ? `range=custom&from=${range.start}&to=${range.end}` : `range=${range.preset}`;
}

export function rangeLabel(range) {
  if (!range) return "";
  return range.start === range.end ? formatCalendarDate(range.start) : `${formatCalendarDate(range.start)} – ${formatCalendarDate(range.end)}`;
}
