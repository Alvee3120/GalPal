"use client";

import { useState } from "react";
import Link from "next/link";
import { FiRefreshCw } from "react-icons/fi";
import { useCart } from "./CartProvider";
import CartItemsTable from "./CartItemsTable";
import OrderSummary from "./OrderSummary";

const SHOP_ROUTE = "/shop";

function Skeleton() {
  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="cart-table-card rounded-2xl p-5 sm:p-6">
        {Array.from({ length: 3 }, (_, i) => (
          <div key={i} className="flex items-center gap-4 py-4">
            <div className="product-skeleton__line h-20 w-20 shrink-0 animate-pulse rounded-xl" />
            <div className="flex-1">
              <div className="product-skeleton__line h-4 w-1/2 animate-pulse rounded-full" />
              <div className="product-skeleton__line mt-2 h-4 w-1/4 animate-pulse rounded-full" />
            </div>
          </div>
        ))}
      </div>
      <div className="order-summary rounded-2xl p-5 sm:p-6">
        <div className="product-skeleton__line h-6 w-2/3 animate-pulse rounded-full" />
        <div className="product-skeleton__line mt-6 h-10 w-full animate-pulse rounded-full" />
        <div className="product-skeleton__line mt-6 h-32 w-full animate-pulse rounded-2xl" />
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="shop-empty flex flex-col items-center gap-3 rounded-2xl px-6 py-16 text-center">
      <p className="custom-font text-2xl">Your cart is empty</p>
      <p className="showcase-muted text-sm">Discover something you&apos;ll love.</p>
      <Link href={SHOP_ROUTE} className="auth-btn auth-btn--primary mt-2 rounded-full px-8 py-3 text-sm font-medium">
        Continue Shopping
      </Link>
    </div>
  );
}

// The full /cart page. Reuses the SAME cart state/API as the drawer (useCart()) — nothing here maintains its
// own copy of the cart; adding or removing a line here is reflected in the navbar badge and the drawer too.
export default function CartPageContent() {
  const {
    items,
    itemCount,
    subtotal,
    discount,
    coupon,
    couponBusy,
    currencySymbol,
    loading,
    pendingIds,
    setQuantity,
    removeItem,
    applyCoupon,
    removeCoupon,
    refreshCart,
  } = useCart();
  const [refreshing, setRefreshing] = useState(false);

  async function handleUpdateCart() {
    setRefreshing(true);
    await refreshCart();
    setRefreshing(false);
  }

  if (loading) return <Skeleton />;
  if (items.length === 0) return <EmptyState />;

  return (
    <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="min-w-0">
        <div className="cart-table-card rounded-2xl p-5 sm:p-6">
          <CartItemsTable items={items} currencySymbol={currencySymbol} pendingIds={pendingIds} onQuantity={setQuantity} onRemove={removeItem} />
        </div>

        {/* Every quantity/remove change above is already live (same as the drawer); this re-reads the cart
            from the server, useful if it changed elsewhere (another tab/device) since the page loaded. */}
        <button
          type="button"
          onClick={handleUpdateCart}
          disabled={refreshing}
          className="auth-btn auth-btn--outline mt-5 inline-flex items-center gap-2 rounded-full px-6 py-2.5 text-sm font-medium"
        >
          <FiRefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} aria-hidden="true" />
          Update Cart
        </button>
      </div>

      <OrderSummary
        subtotal={subtotal}
        discount={discount}
        coupon={coupon}
        couponBusy={couponBusy}
        currencySymbol={currencySymbol}
        itemCount={itemCount}
        onApplyCoupon={applyCoupon}
        onRemoveCoupon={removeCoupon}
      />
    </div>
  );
}
