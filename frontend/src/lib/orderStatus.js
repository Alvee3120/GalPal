// The real status values from the backend (apps.orders.models.OrderStatus / PaymentStatus) — shared by the
// orders list and the order detail page so neither invents its own labels or drifts from the other.
export const ORDER_STATUS_FLOW = ["pending", "confirmed", "processing", "shipped", "delivered"];

// Statuses that fall off the normal flow entirely, shown as "Order Placed -> <status>" instead of a 5-step bar.
export const TERMINAL_OFF_FLOW = ["cancelled", "failed", "returned"];

export const STATUS_LABEL = {
  pending: "Pending",
  confirmed: "Confirmed",
  processing: "Processing",
  shipped: "Shipped",
  delivered: "Delivered",
  cancelled: "Cancelled",
  returned: "Returned",
  failed: "Failed",
};

export const PAYMENT_STATUS_LABEL = {
  unpaid: "Unpaid",
  paid: "Paid",
  partially_paid: "Partially Paid",
  refunded: "Refunded",
  failed: "Failed",
};

// apps.orders.models.PaymentMethod only ever has these two values (see checkout's payment_method field).
export const PAYMENT_METHOD_LABEL = {
  cod: "Cash on Delivery",
  online: "Online Payment",
};

// apps.orders.models.OrderSource — storefront checkout is always "website"; staff pick the rest on a manual order.
export const ORDER_SOURCE_LABEL = {
  website: "Website",
  facebook: "Facebook",
  instagram: "Instagram",
  tiktok: "TikTok",
  whatsapp: "WhatsApp",
  messenger: "Messenger",
  call: "Phone call",
  other: "Other",
};

export function formatOrderDate(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function formatOrderDateTime(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
}

const RELATIVE_UNITS = [
  ["year", 31536000],
  ["month", 2592000],
  ["week", 604800],
  ["day", 86400],
  ["hour", 3600],
  ["minute", 60],
];

// "Ordered 2 mins ago" style relative time for the orders list card. Falls back to the absolute date once it's
// no longer recent enough for "ago" phrasing to be useful (matches formatOrderDate's own formatting so the two
// never disagree on how a date looks).
export function formatRelativeTime(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const seconds = Math.round((Date.now() - d.getTime()) / 1000);
  if (seconds < 60) return "just now";
  for (const [unit, secondsInUnit] of RELATIVE_UNITS) {
    const value = Math.floor(seconds / secondsInUnit);
    if (value >= 1) return `${value} ${unit}${value > 1 ? "s" : ""} ago`;
  }
  return formatOrderDate(iso);
}
