"use client";

import { useState } from "react";
import { notify } from "@/lib/notify";
import { messageFor } from "@/lib/apiError";
import formatPrice from "@/lib/formatPrice";
import ProductImage from "@/component/shared/ProductImage";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import Modal from "@/component/shared/Modal";
import ProductSearchPicker from "./ProductSearchPicker";
import { ORDER_SOURCE_LABEL, PAYMENT_METHOD_LABEL, PAYMENT_STATUS_LABEL, STATUS_LABEL, formatOrderDateTime } from "@/lib/orderStatus";

// Transitions that release stock/coupon (apps.orders.services.STOCK_RELEASING) get a confirmation prompt first —
// everything else (confirm, processing, shipped, delivered) is a plain click.
const CONFIRM_FIRST = new Set(["cancelled", "failed", "returned"]);

const STATUS_TOAST = {
  confirmed: "Order confirmed successfully.",
  cancelled: "Order cancelled successfully.",
  processing: "Order marked as processing.",
  shipped: "Order marked as shipped.",
  delivered: "Order marked as delivered.",
  returned: "Order marked as returned.",
  failed: "Order marked as failed.",
};

// Order Management detail: everything the backend's own StaffOrderSerializer carries, plus the two actions this
// spec asks for — change status (via the EXISTING POST /admin/orders/<id>/status/, apps.orders.services.change_status)
// and add a product to a still-pending order (via the EXISTING PATCH /admin/orders/<id>/, which replaces the whole
// item list — apps.orders.services.update_order; it restores the old lines' stock and deducts the new lines' stock
// atomically, so there's no window where stock could be double-deducted or double-restored). Both stay entirely
// backend-authoritative: this component only ever renders whatever the backend's response says the order now is.
export default function CceOrderDetail({ initialOrder, currencySymbol }) {
  const [order, setOrder] = useState(initialOrder);
  const [pendingStatus, setPendingStatus] = useState(null); // status awaiting confirmation, or null
  const [changingStatus, setChangingStatus] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [addingProduct, setAddingProduct] = useState(false);

  async function applyStatus(status) {
    if (changingStatus) return;
    setChangingStatus(true);
    try {
      const res = await fetch(`/api/admin/orders/${order.id}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
        cache: "no-store",
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        notify.error(messageFor({ status: res.status, details: data?.error?.details }, "Unable to update order status."));
        return;
      }
      setOrder(data);
      setPendingStatus(null);
      notify.success(STATUS_TOAST[status] ?? `Order status updated to ${STATUS_LABEL[status] ?? status}.`);
    } catch {
      notify.error("Unable to update order status.");
    } finally {
      setChangingStatus(false);
    }
  }

  function handleStatusClick(status) {
    if (CONFIRM_FIRST.has(status)) setPendingStatus(status);
    else applyStatus(status);
  }

  async function handleAddProduct(row, quantity) {
    setAddingProduct(true);
    try {
      const items = order.items.map((item) => ({ product_id: item.product_id, variant_id: item.variant_id, quantity: item.quantity }));
      const existing = items.find((i) => i.product_id === row.product_id && i.variant_id === row.variant_id);
      if (existing) existing.quantity += quantity;
      else items.push({ product_id: row.product_id, variant_id: row.variant_id, quantity });

      const res = await fetch(`/api/admin/orders/${order.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items }),
        cache: "no-store",
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        notify.error(messageFor({ status: res.status, details: data?.error?.details }, "Unable to add this product to the order."));
        return;
      }
      setOrder(data);
      setPickerOpen(false);
      notify.success("Product added to order.");
    } catch {
      notify.error("Unable to add this product to the order.");
    } finally {
      setAddingProduct(false);
    }
  }

  const hasDiscount = Number(order.discount_amount) > 0;
  const addressLine = [order.address_line, order.area, order.district, order.division].filter(Boolean).join(", ");

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="custom-font text-2xl sm:text-3xl">Order #{order.number}</h1>
          <p className="showcase-muted text-sm">{formatOrderDateTime(order.created_at)}</p>
        </div>
        <span className="product-card__chip rounded-full px-3 py-1 text-xs font-medium">{STATUS_LABEL[order.status] ?? order.status}</span>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
        <div className="flex flex-col gap-6">
          <section className="dashboard-card rounded-2xl p-5 sm:p-6">
            <h2 className="custom-font text-lg">Customer &amp; Delivery</h2>
            <div className="mt-4 grid gap-6 sm:grid-cols-2">
              <div>
                <p className="showcase-muted text-xs font-medium uppercase tracking-wide">Customer</p>
                <p className="mt-1 text-sm">{order.customer_name}</p>
                <p className="showcase-muted text-sm">{order.phone}</p>
                {order.email && <p className="showcase-muted text-sm">{order.email}</p>}
                {order.customer ? (
                  <p className="showcase-muted mt-1 text-xs">Registered customer</p>
                ) : (
                  <p className="showcase-muted mt-1 text-xs">Guest</p>
                )}
              </div>
              <div>
                <p className="showcase-muted text-xs font-medium uppercase tracking-wide">Delivery Address</p>
                <p className="mt-1 text-sm">{addressLine || "—"}</p>
              </div>
              <div>
                <p className="showcase-muted text-xs font-medium uppercase tracking-wide">Source</p>
                <p className="mt-1 text-sm">
                  {ORDER_SOURCE_LABEL[order.source] ?? order.source}
                  {order.is_manual && order.created_by ? ` · taken by ${order.created_by.full_name}` : ""}
                </p>
              </div>
              {order.note && (
                <div>
                  <p className="showcase-muted text-xs font-medium uppercase tracking-wide">Note</p>
                  <p className="mt-1 text-sm">{order.note}</p>
                </div>
              )}
            </div>
          </section>

          <section className="dashboard-card rounded-2xl p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="custom-font text-lg">Items</h2>
              {order.editable && (
                <button type="button" onClick={() => setPickerOpen(true)} className="auth-btn auth-btn--outline rounded-full px-4 py-1.5 text-xs font-medium">
                  + Add Product
                </button>
              )}
            </div>
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
                      {item.quantity} &times; {formatPrice(item.unit_price, currencySymbol)}
                      {Number(item.regular_price) > Number(item.unit_price) && (
                        <span className="ml-1.5 line-through">{formatPrice(item.regular_price, currencySymbol)}</span>
                      )}
                    </p>
                  </div>
                  <p className="shrink-0 text-sm font-medium">{formatPrice(item.line_total, currencySymbol)}</p>
                </li>
              ))}
            </ul>
            {!order.editable && (
              <p className="showcase-muted mt-3 text-xs">Items can only be added while the order is still Pending.</p>
            )}
          </section>

          {order.history.length > 0 && (
            <section className="dashboard-card rounded-2xl p-5 sm:p-6">
              <h2 className="custom-font text-lg">History</h2>
              <ul className="mt-4 flex flex-col gap-3">
                {order.history.map((h) => (
                  <li key={h.id} className="text-sm">
                    <p>
                      {h.from_status ? `${STATUS_LABEL[h.from_status] ?? h.from_status} → ` : ""}
                      <span className="font-medium">{STATUS_LABEL[h.to_status] ?? h.to_status}</span>
                      {h.changed_by && <span className="showcase-muted"> &middot; {h.changed_by.full_name}</span>}
                    </p>
                    <p className="showcase-muted text-xs">{formatOrderDateTime(h.created_at)}</p>
                    {h.note && <p className="showcase-muted text-xs">{h.note}</p>}
                  </li>
                ))}
              </ul>
            </section>
          )}
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

          {order.allowed_transitions.length > 0 && (
            <div className="flex flex-col gap-2 border-t pt-4">
              <p className="text-sm font-medium">Change Status</p>
              <div className="flex flex-wrap gap-2">
                {order.allowed_transitions.map((status) => (
                  <button
                    key={status}
                    type="button"
                    onClick={() => handleStatusClick(status)}
                    disabled={changingStatus}
                    className={`rounded-full px-4 py-1.5 text-xs font-medium ${
                      CONFIRM_FIRST.has(status) ? "auth-error border border-current" : "auth-btn auth-btn--outline"
                    }`}
                  >
                    {STATUS_LABEL[status] ?? status}
                  </button>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>

      <ConfirmDialog
        open={pendingStatus !== null}
        title={`${STATUS_LABEL[pendingStatus] ?? pendingStatus} this order?`}
        description={`Are you sure you want to mark this order as ${STATUS_LABEL[pendingStatus] ?? pendingStatus}? This cannot be undone.`}
        confirmLabel={STATUS_LABEL[pendingStatus] ?? "Confirm"}
        cancelLabel="Keep Order"
        busyLabel="Updating..."
        busy={changingStatus}
        onConfirm={() => applyStatus(pendingStatus)}
        onCancel={() => !changingStatus && setPendingStatus(null)}
      />

      <Modal open={pickerOpen} title="Add Product" onClose={() => !addingProduct && setPickerOpen(false)} wide>
        <ProductSearchPicker currencySymbol={currencySymbol} onAdd={handleAddProduct} />
      </Modal>
    </div>
  );
}
