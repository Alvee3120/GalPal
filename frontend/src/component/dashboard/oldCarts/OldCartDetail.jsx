"use client";

import Link from "next/link";
import { FiArrowLeft } from "react-icons/fi";
import formatPrice from "@/lib/formatPrice";
import { formatOrderDateTime, formatRelativeTime } from "@/lib/orderStatus";
import { useStaffHref } from "@/lib/staffPaths";
import ProductImage from "@/component/shared/ProductImage";

// A variant's options, e.g. "Size: 30ml · Shade: Rose".
const variantLabel = (variant) => (variant?.attribute_values ?? []).map((v) => `${v.attribute}: ${v.value}`).join(" · ");

// One customer's current cart (Admin + CCE, read-only): every item with its own "added" time and age — an old item
// stays old even if newer ones were added — the current price and the CURRENT stock (stock can change after an item
// is added; an out-of-stock item is shown, never removed). All from GET /admin/orders/old-carts/<id>/.
export default function OldCartDetail({ data, currencySymbol }) {
  const to = useStaffHref();
  const { cart, items, subtotal } = data;
  const money = (v) => formatPrice(v, currencySymbol);

  return (
    <div className="flex flex-col gap-6">
      <Link href={to("/dashboard/CCE/old-carts")} className="showcase-muted inline-flex w-fit items-center gap-1.5 text-sm hover:text-current">
        <FiArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back to Old Carts
      </Link>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
        <section className="dashboard-card rounded-2xl p-5 sm:p-6">
          <h1 className="custom-font text-2xl">Cart Items</h1>
          <ul className="mt-4 flex flex-col divide-y">
            {items.map((item) => {
              const stock = item.available_quantity === null ? "Not tracked" : item.available_quantity;
              return (
                <li key={item.id} className="flex gap-4 py-4 first:pt-0 last:pb-0">
                  <div className="relative h-20 w-20 shrink-0 overflow-hidden rounded-xl bg-white">
                    <ProductImage src={item.product.feature_image} alt={item.product.name} tight />
                  </div>
                  <div className="flex min-w-0 flex-1 flex-col gap-1 text-sm">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <p className="font-medium">{item.product.name}</p>
                      <span className="font-semibold">{money(item.line_total)}</span>
                    </div>
                    {variantLabel(item.variant) && <p className="showcase-muted text-xs">{variantLabel(item.variant)}</p>}
                    <p className="showcase-muted text-xs">
                      Qty {item.quantity} × {money(item.unit_price)} (current price)
                    </p>
                    <p className="text-xs">
                      Added {formatOrderDateTime(item.added_at)} · <span className="font-medium">{formatRelativeTime(item.added_at)}</span>
                      {item.is_old && (
                        <span className="product-status-badge ml-2 rounded-full px-2 py-0.5 text-[11px] font-medium" data-status="draft">
                          Older than 6 hours
                        </span>
                      )}
                    </p>
                    <p className="text-xs">
                      Current stock: <span className="font-medium">{stock}</span> ·{" "}
                      <span className="product-status-badge rounded-full px-2 py-0.5 text-[11px] font-medium" data-status={item.in_stock ? "active" : "archived"}>
                        {item.in_stock ? "In Stock" : "Out of Stock"}
                      </span>
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>

        <aside className="order-summary flex flex-col gap-4 rounded-2xl p-5 sm:p-6 lg:sticky lg:top-24">
          <h2 className="custom-font text-lg">Customer</h2>
          <dl className="flex flex-col gap-2 text-sm">
            <div className="flex justify-between gap-3">
              <dt>Name</dt>
              <dd className="text-right font-medium">{cart.customer.name}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt>Phone</dt>
              <dd className="text-right font-medium">
                <a href={`tel:${cart.customer.phone}`} className="hover:underline">
                  {cart.customer.phone}
                </a>
              </dd>
            </div>
            {cart.customer.email && (
              <div className="flex justify-between gap-3">
                <dt>Email</dt>
                <dd className="break-all text-right font-medium">{cart.customer.email}</dd>
              </div>
            )}
          </dl>
          <dl className="flex flex-col gap-2 border-t pt-4 text-sm">
            <div className="flex justify-between gap-3">
              <dt>Products</dt>
              <dd className="font-medium">{cart.line_count} ({cart.quantity} units)</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt>Oldest item</dt>
              <dd className="text-right font-medium">{formatRelativeTime(cart.oldest_item_at)}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt>Last updated</dt>
              <dd className="text-right font-medium">{formatOrderDateTime(cart.last_activity_at)}</dd>
            </div>
            <div className="flex justify-between gap-3 border-t pt-3 text-base">
              <dt className="font-semibold">Cart Total</dt>
              <dd className="font-semibold">{money(subtotal)}</dd>
            </div>
          </dl>
          <p className="showcase-muted text-xs">Out-of-stock items aren&apos;t included in the total.</p>
        </aside>
      </div>
    </div>
  );
}
