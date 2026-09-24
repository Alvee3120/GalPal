"use client";

import { useState } from "react";
import Link from "next/link";
import { FiArrowLeft, FiMinus, FiPlus, FiTrash2 } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { messageFor } from "@/lib/apiError";
import formatPrice from "@/lib/formatPrice";
import ProductImage from "@/component/shared/ProductImage";
import Modal from "@/component/shared/Modal";
import ProductSearchPicker from "./ProductSearchPicker";
import OrderStatusDropdown from "./OrderStatusDropdown";
import { ORDER_SOURCE_LABEL, PAYMENT_METHOD_LABEL, PAYMENT_STATUS_LABEL, STATUS_LABEL, formatOrderDateTime } from "@/lib/orderStatus";

const toLine = (item) => ({ product_id: item.product_id, variant_id: item.variant_id, quantity: item.quantity });

// Order Management detail: everything the backend's own StaffOrderSerializer carries, plus the actions this spec
// asks for — change status (via OrderStatusDropdown, the SAME reusable control the Order Management list uses —
// POST /admin/orders/<id>/status/, apps.orders.services.change_status), and add/adjust/remove items on a still-
// pending order. All three item actions (add, change quantity, remove) go through the ONE EXISTING PATCH
// /admin/orders/<id>/ (apps.orders.services.update_order, which replaces the whole item list — it restores the
// old lines' stock and deducts the new lines' stock atomically, so there's no window where stock could be
// double-deducted or double-restored), just with a differently-built `items` array — no separate add/remove/
// quantity endpoints invented. Everything stays backend-authoritative: this component only ever renders whatever
// the backend's response says the order now is.
export default function CceOrderDetail({ initialOrder, currencySymbol }) {
  const [order, setOrder] = useState(initialOrder);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [mutatingItems, setMutatingItems] = useState(false);

  async function patchItems(items, successMessage) {
    if (mutatingItems) return false;
    setMutatingItems(true);
    try {
      const res = await fetch(`/api/admin/orders/${order.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items }),
        cache: "no-store",
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        notify.error(messageFor({ status: res.status, details: data?.error?.details }, "Unable to update order items."));
        return false;
      }
      setOrder(data);
      notify.success(successMessage);
      return true;
    } catch {
      notify.error("Unable to update order items.");
      return false;
    } finally {
      setMutatingItems(false);
    }
  }

  async function handleAddProduct(row, quantity) {
    const items = order.items.map(toLine);
    const existing = items.find((i) => i.product_id === row.product_id && i.variant_id === row.variant_id);
    if (existing) existing.quantity += quantity;
    else items.push({ product_id: row.product_id, variant_id: row.variant_id, quantity });
    if (await patchItems(items, "Product added to order.")) setPickerOpen(false);
  }

  function handleQuantityChange(itemId, delta) {
    const target = order.items.find((i) => i.id === itemId);
    if (!target || target.quantity + delta < 1) return;
    const items = order.items.map((item) => (item.id === itemId ? { ...toLine(item), quantity: item.quantity + delta } : toLine(item)));
    patchItems(items, "Order updated.");
  }

  function handleRemoveItem(itemId) {
    const items = order.items.filter((item) => item.id !== itemId).map(toLine);
    patchItems(items, "Product removed from order.");
  }

  const hasDiscount = Number(order.discount_amount) > 0;
  const addressLine = [order.address_line, order.area, order.district, order.division].filter(Boolean).join(", ");

  return (
    <div className="flex flex-col gap-6">
      <Link href="/dashboard/CCE/orders" className="showcase-muted inline-flex w-fit items-center gap-1.5 text-sm hover:text-current">
        <FiArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back to Order Management
      </Link>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="custom-font text-2xl sm:text-3xl">Order #{order.number}</h1>
          <p className="showcase-muted text-sm">{formatOrderDateTime(order.created_at)}</p>
        </div>
        <div className="w-44">
          <OrderStatusDropdown orderId={order.id} status={order.status} onChanged={setOrder} />
        </div>
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
              <h2 className="custom-font text-lg">Order Products</h2>
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
                    {order.editable ? (
                      <div className="mt-2 flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => handleQuantityChange(item.id, -1)}
                          disabled={mutatingItems || item.quantity <= 1}
                          aria-label={`Decrease quantity of ${item.product_name}`}
                          className="cart-qty__btn flex h-7 w-7 items-center justify-center rounded-full"
                        >
                          <FiMinus className="h-3 w-3" aria-hidden="true" />
                        </button>
                        <span className="w-7 text-center text-sm tabular-nums">{item.quantity}</span>
                        <button
                          type="button"
                          onClick={() => handleQuantityChange(item.id, 1)}
                          disabled={mutatingItems}
                          aria-label={`Increase quantity of ${item.product_name}`}
                          className="cart-qty__btn flex h-7 w-7 items-center justify-center rounded-full"
                        >
                          <FiPlus className="h-3 w-3" aria-hidden="true" />
                        </button>
                        <span className="showcase-muted ml-1 text-xs">&times; {formatPrice(item.unit_price, currencySymbol)}</span>
                      </div>
                    ) : (
                      <p className="showcase-muted mt-0.5 text-xs">
                        {item.quantity} &times; {formatPrice(item.unit_price, currencySymbol)}
                        {Number(item.regular_price) > Number(item.unit_price) && (
                          <span className="ml-1.5 line-through">{formatPrice(item.regular_price, currencySymbol)}</span>
                        )}
                      </p>
                    )}
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-2">
                    <p className="text-sm font-medium">{formatPrice(item.line_total, currencySymbol)}</p>
                    {order.editable && (
                      <button
                        type="button"
                        onClick={() => handleRemoveItem(item.id)}
                        disabled={mutatingItems || order.items.length <= 1}
                        aria-label={`Remove ${item.product_name}`}
                        title={order.items.length <= 1 ? "An order needs at least one item" : "Remove"}
                        className="auth-error disabled:opacity-40"
                      >
                        <FiTrash2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    )}
                  </div>
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
        </aside>
      </div>

      <Modal open={pickerOpen} title="Add Product" onClose={() => !mutatingItems && setPickerOpen(false)} wide>
        <ProductSearchPicker currencySymbol={currencySymbol} onAdd={handleAddProduct} />
      </Modal>
    </div>
  );
}
