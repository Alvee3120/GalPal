"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FiShoppingBag } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { messageFor } from "@/lib/apiError";
import formatPrice from "@/lib/formatPrice";
import { ORDER_STATUS_FLOW, PAYMENT_METHOD_LABEL, STATUS_LABEL, TERMINAL_OFF_FLOW, formatRelativeTime } from "@/lib/orderStatus";

// The compact horizontal progress bar on each order card. Built from `order.status` alone (the list endpoint
// doesn't carry per-status timestamps — that's what the order detail page's own history-based timeline is for),
// so it only ever marks steps up to and including the current one, never claims a time for them.
function OrderCardSteps({ status }) {
  const offFlow = TERMINAL_OFF_FLOW.includes(status);
  const steps = offFlow ? ["pending", status] : ORDER_STATUS_FLOW;
  const currentIndex = steps.indexOf(status);

  return (
    <ol className="flex items-start">
      {steps.map((step, index) => {
        const done = index <= currentIndex;
        return (
          <li key={step} className="flex flex-1 flex-col items-center last:flex-none">
            <p className={`mb-2 text-center text-xs ${index === currentIndex ? "font-semibold" : "showcase-muted"}`}>
              {step === "pending" ? "Order Placed" : (STATUS_LABEL[step] ?? step)}
            </p>
            <div className="flex w-full items-center">
              <span className={`order-card-step__dot flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${done ? "order-card-step__dot--done" : ""}`} />
              {index < steps.length - 1 && <span className={`order-card-step__line h-0.5 flex-1 ${index < currentIndex ? "order-card-step__line--done" : ""}`} />}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

// "My Orders": the customer's own orders from the EXISTING MyOrderViewSet (GET /orders/, via the /api/orders
// proxy), with a real Cancel action (POST /orders/<number>/cancel/) shown only when the backend's own
// `can_cancel` flag on that order says so — never inferred client-side from the status alone.
export default function OrdersList({ initialOrders, currencySymbol }) {
  const router = useRouter();
  const [orders, setOrders] = useState(initialOrders);
  const [cancellingNumber, setCancellingNumber] = useState(null);

  async function cancelOrder(number) {
    if (cancellingNumber) return;
    setCancellingNumber(number);
    try {
      const res = await fetch(`/api/orders/${encodeURIComponent(number)}/cancel`, { method: "POST", cache: "no-store" });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        notify.error(messageFor({ status: res.status, details: data?.error?.details }, "Unable to cancel this order. Please try again."));
        return;
      }
      setOrders((list) => list.map((o) => (o.number === number ? { ...o, status: data.status, can_cancel: data.can_cancel } : o)));
      notify.success("Order cancelled.");
      router.refresh();
    } catch {
      notify.error("Unable to cancel this order. Please try again.");
    } finally {
      setCancellingNumber(null);
    }
  }

  if (orders.length === 0) {
    return (
      <div className="dashboard-card flex flex-col items-center gap-2 rounded-2xl px-6 py-14 text-center">
        <p className="custom-font text-xl">No orders yet</p>
        <p className="showcase-muted text-sm">Your placed orders will show up here.</p>
      </div>
    );
  }

  return (
    <ul className="flex flex-col gap-3">
      {orders.map((order) => (
        <li key={order.number} className="dashboard-card rounded-2xl p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="dashboard-card__icon flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl">
                <FiShoppingBag className="h-5 w-5" aria-hidden="true" />
              </span>
              <div>
                <p className="text-sm font-semibold">Order no #{order.number}</p>
                <p className="showcase-muted text-sm">{formatPrice(order.grand_total, currencySymbol)}</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <Link href={`/dashboard/customer/orders/${order.number}`} className="auth-btn auth-btn--primary rounded-full px-5 py-2 text-xs font-medium">
                Order Details
              </Link>
              {order.can_cancel && (
                <button
                  type="button"
                  onClick={() => cancelOrder(order.number)}
                  disabled={cancellingNumber === order.number}
                  className="auth-error text-xs font-medium disabled:opacity-60"
                >
                  {cancellingNumber === order.number ? "Cancelling..." : "Cancel Order"}
                </button>
              )}
            </div>
          </div>

          <div className="mt-4">
            <OrderCardSteps status={order.status} />
          </div>

          <p className="showcase-muted mt-3 text-xs">
            {order.item_count} {order.item_count === 1 ? "Item" : "Items"} &bull; {PAYMENT_METHOD_LABEL[order.payment_method] ?? order.payment_method} &bull; Ordered{" "}
            {formatRelativeTime(order.created_at)}
          </p>
        </li>
      ))}
    </ul>
  );
}
