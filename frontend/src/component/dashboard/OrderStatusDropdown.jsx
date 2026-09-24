"use client";

import { useEffect, useRef, useState } from "react";
import { FiCheck, FiChevronDown } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { messageFor } from "@/lib/apiError";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import { STATUS_LABEL } from "@/lib/orderStatus";

// Transitions that release stock/coupon (apps.orders.services.STOCK_RELEASING) get a confirmation prompt first.
const CONFIRM_FIRST = new Set(["cancelled", "failed", "returned"]);

// The CCE-facing status vocabulary this dropdown always offers, in order — matches the Order Management status
// filter's options exactly, so the two never present a different set of names. Every option is always shown
// (not narrowed to this order's own allowed_transitions): staff may move an order to any other status, and the
// backend's change_status is still the one place that validates it (e.g. refusing to reopen an order whose stock
// has since sold out) — the dropdown attempts, it never silently allows.
const ALL_STATUSES = ["confirmed", "processing", "shipped", "delivered", "cancelled", "returned"];

const STATUS_TOAST = {
  confirmed: "Order confirmed successfully.",
  cancelled: "Order cancelled successfully.",
  processing: "Order marked as processing.",
  shipped: "Order marked as shipped.",
  delivered: "Order marked as delivered.",
  returned: "Order marked as returned.",
  failed: "Order marked as failed.",
};

// The ONE order-status control, used on both Order Management rows and the Order Details page (rather than two
// separate implementations) — always offers the full ALL_STATUSES list (see above). It owns the
// whole update: calls the EXISTING POST /admin/orders/<id>/status/ (apps.orders.services.change_status, which is
// also where stock is deducted/restored — nothing here touches stock), shows a loading state, blocks duplicate
// submissions, and only ever reflects the backend's OWN response — a rejected transition leaves the dropdown
// showing the previous status untouched, never an optimistic guess.
export default function OrderStatusDropdown({ orderId, status, onChanged, className = "" }) {
  const [open, setOpen] = useState(false);
  const [pendingStatus, setPendingStatus] = useState(null);
  const [updating, setUpdating] = useState(false);
  const rootRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e) => {
      if (!rootRef.current?.contains(e.target)) setOpen(false);
    };
    const onKeyDown = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  async function applyStatus(next) {
    if (updating) return;
    setUpdating(true);
    try {
      const res = await fetch(`/api/admin/orders/${orderId}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: next }),
        cache: "no-store",
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        notify.error(messageFor({ status: res.status, details: data?.error?.details }, "Unable to update order status."));
        return;
      }
      onChanged(data);
      setPendingStatus(null);
      notify.success(STATUS_TOAST[next] ?? `Order status updated to ${STATUS_LABEL[next] ?? next}.`);
    } catch {
      notify.error("Unable to update order status.");
    } finally {
      setUpdating(false);
    }
  }

  function choose(next) {
    setOpen(false);
    if (next === status) return;
    if (CONFIRM_FIRST.has(next)) setPendingStatus(next);
    else applyStatus(next);
  }

  const options = [status, ...ALL_STATUSES.filter((s) => s !== status)];

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={updating}
        aria-haspopup="listbox"
        aria-expanded={open}
        data-status={status}
        className="checkout-input order-status order-status--button flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm disabled:opacity-70"
      >
        <span>{updating ? "Updating..." : (STATUS_LABEL[status] ?? status)}</span>
        <FiChevronDown className={`h-4 w-4 shrink-0 transition-transform duration-150 ${open ? "rotate-180" : ""}`} aria-hidden="true" />
      </button>

      <ul
        role="listbox"
        className={`shop-sort__menu absolute left-0 top-full z-50 mt-1.5 w-full min-w-max origin-top rounded-lg p-1 transition duration-150 ease-out motion-reduce:transition-none ${
          open ? "visible translate-y-0 scale-100 opacity-100" : "invisible -translate-y-1 scale-95 opacity-0"
        }`}
      >
        {options.map((opt) => (
          <li key={opt} role="presentation">
            <button
              type="button"
              role="option"
              aria-selected={opt === status}
              tabIndex={open ? 0 : -1}
              onClick={() => choose(opt)}
              className="shop-sort__item flex w-full items-center justify-between gap-3 rounded-md px-3 py-1.5 text-left text-sm"
            >
              <span className="flex items-center gap-2">
                <span data-status={opt} className="order-status order-status--dot h-2 w-2 shrink-0 rounded-full" aria-hidden="true" />
                {STATUS_LABEL[opt] ?? opt}
              </span>
              {opt === status && <FiCheck className="h-4 w-4 shrink-0" aria-hidden="true" />}
            </button>
          </li>
        ))}
      </ul>

      <ConfirmDialog
        open={pendingStatus !== null}
        title={`${STATUS_LABEL[pendingStatus] ?? pendingStatus} this order?`}
        description={`Are you sure you want to mark this order as ${STATUS_LABEL[pendingStatus] ?? pendingStatus}? Its stock will be put back.`}
        confirmLabel={STATUS_LABEL[pendingStatus] ?? "Confirm"}
        cancelLabel="Keep Order"
        busyLabel="Updating..."
        busy={updating}
        onConfirm={() => applyStatus(pendingStatus)}
        onCancel={() => !updating && setPendingStatus(null)}
      />
    </div>
  );
}
