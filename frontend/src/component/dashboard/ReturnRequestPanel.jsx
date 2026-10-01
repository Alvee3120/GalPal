"use client";

import { useEffect, useState } from "react";
import { notify } from "@/lib/notify";
import { messageFor } from "@/lib/apiError";
import { formatOrderDateTime } from "@/lib/orderStatus";

const REASONS = [
  { value: "damaged", label: "Damaged" },
  { value: "wrong_item", label: "Wrong item" },
  { value: "defective", label: "Defective / not working" },
  { value: "expired", label: "Expired" },
  { value: "other", label: "Other" },
];
const REASON_LABEL = Object.fromEntries(REASONS.map((r) => [r.value, r.label]));
const STATUS_LABEL = { requested: "Requested", approved: "Approved", rejected: "Rejected", received: "Item received", refunded: "Refunded / replaced" };
const OPEN = ["requested", "approved", "received"];

// Return / refund request on the customer's own order (Module 14, apps.care). Shown for a delivered order, or when a
// request exists. The backend enforces the real rules: own delivered order, within the return window, one open
// request at a time — this panel just shows its answer.
export default function ReturnRequestPanel({ order }) {
  const [requests, setRequests] = useState(null);
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("damaged");
  const [details, setDetails] = useState("");
  const [sending, setSending] = useState(false);
  const delivered = order.status === "delivered";

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/orders/${encodeURIComponent(order.number)}/return-request`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => !cancelled && setRequests(Array.isArray(data) ? data : []))
      .catch(() => !cancelled && setRequests([]));
    return () => {
      cancelled = true;
    };
  }, [order.number]);

  if (requests === null || (!delivered && requests.length === 0)) return null;
  const hasOpen = requests.some((r) => OPEN.includes(r.status));

  async function submit(e) {
    e.preventDefault();
    if (!details.trim()) return notify.error("Please tell us what's wrong with the order.");
    setSending(true);
    try {
      const res = await fetch(`/api/orders/${encodeURIComponent(order.number)}/return-request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason, details }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) return notify.error(messageFor({ status: res.status, details: data?.error?.details }, "Unable to send your request. Please contact us."));
      setRequests((list) => [data, ...list]);
      setOpen(false);
      setDetails("");
      notify.success("Return request sent. We'll get back to you soon.");
    } catch {
      notify.error("Unable to send your request. Please contact us.");
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="dashboard-card rounded-2xl p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="custom-font text-lg">Returns</h2>
        {delivered && !hasOpen && !open && (
          <button type="button" onClick={() => setOpen(true)} className="auth-btn auth-btn--outline rounded-full px-4 py-2 text-sm font-medium">
            Request a Return
          </button>
        )}
      </div>

      {open && (
        <form onSubmit={submit} className="mt-4 grid gap-3">
          <p className="showcase-muted text-xs">
            For a wrong, damaged, defective or expired item, within the return window after delivery. See our Return &amp; Cancellation Policy.
          </p>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium">Reason</span>
            <select value={reason} onChange={(e) => setReason(e.target.value)} className="checkout-input rounded-lg px-3 py-2.5 text-sm">
              {REASONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium">What&apos;s wrong?</span>
            <textarea value={details} onChange={(e) => setDetails(e.target.value)} rows={3} maxLength={2000} className="checkout-input rounded-lg px-3 py-2.5 text-sm" />
          </label>
          <div className="flex flex-wrap gap-2">
            <button type="submit" disabled={sending} className="auth-btn auth-btn--primary rounded-full px-5 py-2 text-sm font-medium">
              {sending ? "Sending…" : "Send Request"}
            </button>
            <button type="button" onClick={() => setOpen(false)} disabled={sending} className="auth-btn auth-btn--outline rounded-full px-5 py-2 text-sm font-medium">
              Cancel
            </button>
          </div>
        </form>
      )}

      {requests.length > 0 ? (
        <ul className="mt-4 flex flex-col gap-3">
          {requests.map((r) => (
            <li key={r.id} className="rounded-xl border p-3 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium">{REASON_LABEL[r.reason] ?? r.reason}</span>
                <span className="product-card__chip rounded-full px-2.5 py-0.5 text-xs font-medium">{STATUS_LABEL[r.status] ?? r.status}</span>
              </div>
              <p className="showcase-muted mt-1 text-xs">{formatOrderDateTime(r.created_at)}</p>
              <p className="mt-2">{r.details}</p>
              {r.admin_note && (
                <p className="mt-2 text-xs">
                  <span className="font-medium">GalPal:</span> {r.admin_note}
                </p>
              )}
            </li>
          ))}
        </ul>
      ) : (
        !open && <p className="showcase-muted mt-2 text-sm">Something wrong with your order? You can request a return here.</p>
      )}
    </section>
  );
}
