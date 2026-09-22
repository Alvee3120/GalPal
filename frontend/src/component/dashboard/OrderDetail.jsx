"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FiCheck } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { messageFor } from "@/lib/apiError";
import formatPrice from "@/lib/formatPrice";
import ProductImage from "@/component/shared/ProductImage";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import {
  ORDER_STATUS_FLOW,
  PAYMENT_METHOD_LABEL,
  PAYMENT_STATUS_LABEL,
  STATUS_LABEL,
  TERMINAL_OFF_FLOW,
  formatOrderDate,
  formatOrderDateTime,
} from "@/lib/orderStatus";

// The status timeline (Part 3): the normal flow with a check on every step already reached, or — for
// cancelled/failed/returned, which fall off that flow entirely — just "Order Placed" then the terminal status,
// exactly like the brief's own "Order Placed -> Cancelled" example. Built from the order's real `history` (each
// entry already the backend's own status + timestamp), not guessed from the current status alone.
function StatusTimeline({ order }) {
  const offFlow = TERMINAL_OFF_FLOW.includes(order.status);
  const steps = offFlow ? ["pending", order.status] : ORDER_STATUS_FLOW;
  const reached = new Set(order.history.map((h) => h.status));
  const currentIndex = steps.indexOf(order.status);
  const timeFor = (status) => order.history.find((h) => h.status === status)?.created_at;

  return (
    <ol className="flex flex-col gap-0">
      {steps.map((status, index) => {
        const done = reached.has(status) && index <= currentIndex;
        return (
          <li key={status} className="flex gap-3">
            <div className="flex flex-col items-center">
              <span className={`order-timeline__dot flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${done ? "order-timeline__dot--done" : ""}`}>
                {done && <FiCheck className="h-3.5 w-3.5" aria-hidden="true" />}
              </span>
              {index < steps.length - 1 && <span className={`order-timeline__line w-px flex-1 ${done ? "order-timeline__line--done" : ""}`} />}
            </div>
            <div className="pb-6">
              <p className={`text-sm font-medium ${done ? "" : "showcase-muted"}`}>{status === "pending" ? "Order Placed" : (STATUS_LABEL[status] ?? status)}</p>
              {done && timeFor(status) && <p className="showcase-muted text-xs">{formatOrderDateTime(timeFor(status))}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

// Order Details (Part 2): everything the backend's own order-detail response carries — order info, customer
// contact, delivery address, items and their variant/discount, and the summary — nothing invented beyond it.
// Cancel (Part 14 + the Confirmed-lockout rule) only ever goes by the backend's own `can_cancel` flag, which
// already reflects apps.orders.services.CUSTOMER_CANCELLABLE = {pending} — never a client-side status check.
export default function OrderDetail({ initialOrder, currencySymbol }) {
  const router = useRouter();
  const [order, setOrder] = useState(initialOrder);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  async function confirmCancel() {
    if (cancelling) return;
    setCancelling(true);
    try {
      const res = await fetch(`/api/orders/${encodeURIComponent(order.number)}/cancel`, { method: "POST", cache: "no-store" });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        notify.error(messageFor({ status: res.status, details: data?.error?.details }, "Unable to cancel this order. Please try again."));
        return;
      }
      setOrder(data);
      setConfirmOpen(false);
      notify.success("Order cancelled successfully.");
      router.refresh();
    } catch {
      notify.error("Unable to cancel this order. Please try again.");
    } finally {
      setCancelling(false);
    }
  }

  const hasDiscount = Number(order.discount_amount) > 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="custom-font text-2xl sm:text-3xl">Order #{order.number}</h1>
          <p className="showcase-muted text-sm">{formatOrderDate(order.created_at)}</p>
        </div>
        <span className="product-card__chip rounded-full px-3 py-1 text-xs font-medium">{STATUS_LABEL[order.status] ?? order.status}</span>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
        <div className="flex flex-col gap-6">
          <section className="dashboard-card rounded-2xl p-5 sm:p-6">
            <h2 className="custom-font text-lg">Order Status</h2>
            <div className="mt-4">
              <StatusTimeline order={order} />
            </div>
          </section>

          <section className="dashboard-card rounded-2xl p-5 sm:p-6">
            <h2 className="custom-font text-lg">Items</h2>
            <ul className="checkout-lines mt-4 flex flex-col">
              {order.items.map((item) => (
                <li key={item.id} className="flex items-start gap-3 py-3 first:pt-0">
                  <div className="cart-thumb relative h-16 w-16 shrink-0 overflow-hidden">
                    <ProductImage src={item.image} alt="" tight />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium leading-snug">{item.product_name}</p>
                    {item.variant_label && <p className="showcase-muted mt-0.5 text-xs">{item.variant_label}</p>}
                    <p className="showcase-muted mt-0.5 text-xs">
                      {item.quantity} × {formatPrice(item.unit_price, currencySymbol)}
                      {Number(item.regular_price) > Number(item.unit_price) && (
                        <span className="ml-1.5 line-through">{formatPrice(item.regular_price, currencySymbol)}</span>
                      )}
                    </p>
                  </div>
                  <p className="shrink-0 text-sm font-medium">{formatPrice(item.line_total, currencySymbol)}</p>
                </li>
              ))}
            </ul>
          </section>

          <section className="dashboard-card rounded-2xl p-5 sm:p-6">
            <h2 className="custom-font text-lg">Customer &amp; Delivery</h2>
            <div className="mt-4 grid gap-6 sm:grid-cols-2">
              <div>
                <p className="showcase-muted text-xs font-medium uppercase tracking-wide">Customer</p>
                <p className="mt-1 text-sm">{order.customer_name}</p>
                <p className="showcase-muted text-sm">{order.phone}</p>
                {order.email && <p className="showcase-muted text-sm">{order.email}</p>}
              </div>
              <div>
                <p className="showcase-muted text-xs font-medium uppercase tracking-wide">Delivery Address</p>
                <p className="mt-1 text-sm">{order.address_line}</p>
                <p className="showcase-muted text-sm">
                  {order.area ? `${order.area}, ` : ""}
                  {order.district}
                </p>
              </div>
              {order.note && (
                <div className="sm:col-span-2">
                  <p className="showcase-muted text-xs font-medium uppercase tracking-wide">Order Note</p>
                  <p className="mt-1 text-sm">{order.note}</p>
                </div>
              )}
            </div>
          </section>
        </div>

        <aside className="order-summary flex flex-col gap-4 rounded-2xl p-5 sm:p-6 lg:sticky lg:top-24">
          <h2 className="custom-font text-lg">Summary</h2>
          <dl className="flex flex-col gap-2 text-sm">
            <div className="flex items-center justify-between">
              <dt>Payment Method</dt>
              <dd className="font-medium">{PAYMENT_METHOD_LABEL[order.payment_method] ?? order.payment_method}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt>Payment Status</dt>
              <dd className="font-medium">{PAYMENT_STATUS_LABEL[order.payment_status] ?? order.payment_status}</dd>
            </div>
            {(order.courier_name || order.tracking_id) && (
              <div className="flex items-center justify-between">
                <dt>Courier</dt>
                <dd className="font-medium">{[order.courier_name, order.tracking_id].filter(Boolean).join(" · ")}</dd>
              </div>
            )}
          </dl>

          <dl className="flex flex-col gap-2 border-t pt-4 text-sm">
            <div className="flex items-center justify-between">
              <dt>Subtotal</dt>
              <dd className="font-medium">{formatPrice(order.subtotal, currencySymbol)}</dd>
            </div>
            {hasDiscount && (
              <div className="flex items-center justify-between">
                <dt>Discount{order.coupon_code ? ` (${order.coupon_code})` : ""}</dt>
                <dd className="font-medium">-{formatPrice(order.discount_amount, currencySymbol)}</dd>
              </div>
            )}
            <div className="flex items-center justify-between">
              <dt>Delivery Charge</dt>
              <dd className="font-medium">{formatPrice(order.shipping_charge, currencySymbol)}</dd>
            </div>
            {Number(order.tax_amount) > 0 && (
              <div className="flex items-center justify-between">
                <dt>Tax</dt>
                <dd className="font-medium">{formatPrice(order.tax_amount, currencySymbol)}</dd>
              </div>
            )}
          </dl>

          <div className="flex items-baseline justify-between border-t pt-4">
            <span className="text-base font-semibold">Total</span>
            <span className="text-xl font-semibold">{formatPrice(order.grand_total, currencySymbol)}</span>
          </div>

          {order.can_cancel && (
            <button type="button" onClick={() => setConfirmOpen(true)} className="auth-btn auth-btn--outline rounded-full py-3 text-sm font-medium">
              Cancel Order
            </button>
          )}
        </aside>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Cancel Order?"
        description="Are you sure you want to cancel this order?"
        confirmLabel="Cancel Order"
        cancelLabel="Keep Order"
        busyLabel="Cancelling..."
        busy={cancelling}
        onConfirm={confirmCancel}
        onCancel={() => !cancelling && setConfirmOpen(false)}
      />
    </div>
  );
}
