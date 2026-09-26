"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import formatPrice from "@/lib/formatPrice";
import CouponBox from "./CouponBox";


const CHECKOUT_ROUTE = "/checkout";

// Order Summary card: voucher code, the Sub Total/Total breakdown, a shipping note (the backend's own cart
// response explicitly defers shipping/tax to checkout — same copy the cart drawer already uses) and Checkout.
export default function OrderSummary({ subtotal, discount, coupon, couponBusy, currencySymbol, onApplyCoupon, onRemoveCoupon, itemCount, hasAvailableItems = true }) {
  const [zones, setZones] = useState(null);
  useEffect(() => {
    let cancelled = false;
    fetch("/api/shipping/zones", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => !cancelled && setZones(Array.isArray(data) ? data : null))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  const checkoutDisabled = itemCount === 0 || !hasAvailableItems;
  const grandTotal = Number(subtotal) - Number(discount);
  const hasDiscount = Number(discount) > 0;

  return (
    <aside className="order-summary rounded-2xl p-5 sm:p-6">
      <h2 className="custom-font text-xl">Order Summary</h2>

      <div className="mt-4">
        <CouponBox id="cart-voucher" coupon={coupon} busy={couponBusy} onApply={onApplyCoupon} onRemove={onRemoveCoupon} />
      </div>

      <dl className="mt-5 flex flex-col gap-2 border-t pt-4 text-sm">
        <div className="flex items-center justify-between">
          <dt>Sub Total</dt>
          <dd className="font-medium">{formatPrice(subtotal, currencySymbol)}</dd>
        </div>
        {hasDiscount && (
          <div className="flex items-center justify-between">
            <dt>Discount</dt>
            <dd className="font-medium">-{formatPrice(discount, currencySymbol)}</dd>
          </div>
        )}
      </dl>

      <div className="mt-4 flex items-baseline justify-between border-t pt-4">
        <span className="text-base font-semibold">Total</span>
        <span className="text-xl font-semibold">{formatPrice(grandTotal, currencySymbol)}</span>
      </div>

      {zones?.length > 0 && (
        // The Admin-configured delivery zones (GET /shipping/zones/ via /api/shipping), in their display order.
        <dl className="delivery-rates mt-4 flex flex-col gap-1.5 rounded-xl px-4 py-3 text-sm">
          {zones.map((zone) => (
            <div key={zone.slug} className="flex items-center justify-between gap-3">
              <dt>{zone.name}</dt>
              <dd>{Number(zone.charge) === 0 ? "Free" : formatPrice(zone.charge, currencySymbol)}</dd>
            </div>
          ))}
        </dl>
      )}

      <p className="showcase-muted mt-3 text-xs">Shipping and taxes are calculated at checkout.</p>

      {itemCount > 0 && !hasAvailableItems && (
        <p className="auth-error mt-3 text-xs font-medium">All items in your cart are currently out of stock.</p>
      )}

      <Link
        href={CHECKOUT_ROUTE}
        aria-disabled={checkoutDisabled}
        className={`auth-btn auth-btn--primary mt-5 block w-full rounded-full py-3 text-center text-sm font-medium ${checkoutDisabled ? "pointer-events-none opacity-50" : ""}`}
      >
        Checkout Now
      </Link>
    </aside>
  );
}
