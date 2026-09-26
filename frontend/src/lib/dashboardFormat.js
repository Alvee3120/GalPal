import formatPrice from "@/lib/formatPrice";

// Shared by the staff dashboards. From 10,000 up: "10k", "10.34k" (at most 2 decimals, trailing zeros dropped); from a
// million: "1.04M". Below 10,000 the full amount is short enough ("9,850").
const trim2 = (n) => String(Number(n.toFixed(2)));

export function compactMoney(value, symbol) {
  const n = Number(value) || 0;
  if (Math.abs(n) >= 1_000_000) return `${symbol}${trim2(n / 1_000_000)}M`;
  if (Math.abs(n) >= 10_000) return `${symbol}${trim2(n / 1_000)}k`;
  return formatPrice(n, symbol);
}

export function compactNumber(value) {
  const n = Number(value) || 0;
  if (Math.abs(n) >= 1_000_000) return `${trim2(n / 1_000_000)}M`;
  if (Math.abs(n) >= 10_000) return `${trim2(n / 1_000)}k`;
  return n.toLocaleString("en-US");
}

// The time-series grouping the backend chose (apps.orders.analytics.granularity_for), as a word for subtitles.
export const GRANULARITY_WORD = { hour: "hour", day: "day", week: "week", month: "month" };
