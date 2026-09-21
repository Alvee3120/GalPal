"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { FiTrash2 } from "react-icons/fi";
import formatPrice from "@/lib/formatPrice";
import { variantLabel } from "@/lib/cartItem";
import ProductImage from "@/component/shared/ProductImage";
import { useCart } from "./CartProvider";

// Route the drawer's buttons go to. The Navbar already linked its cart icon to /cart.
const CART_ROUTE = "/cart";
const CHECKOUT_ROUTE = "/checkout";
const SHOP_ROUTE = "/shop";

const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

const icon = (d, className = "h-4 w-4") => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={d} />
  </svg>
);

function CartLine({ item, symbol, busy, onQuantity, onRemove, onNavigate }) {
  const { product, variant, quantity, unit_price, line_total, is_available, available_quantity } = item;
  const label = variantLabel(variant);
  const atMax = typeof available_quantity === "number" && quantity >= available_quantity;

  return (
    <li className="cart-line flex gap-3 py-4 sm:gap-4">
      <Link href={`/products/${product.slug}`} onClick={onNavigate} className="cart-thumb relative h-20 w-20 shrink-0 overflow-hidden sm:h-24 sm:w-24" tabIndex={-1} aria-hidden="true">
        <ProductImage src={product.feature_image} alt="" />
      </Link>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <Link href={`/products/${product.slug}`} onClick={onNavigate} className="cart-link line-clamp-2 text-sm font-medium leading-snug">
              {product.name}
            </Link>
            {label && <p className="showcase-muted mt-0.5 text-xs">{label}</p>}
            <p className="showcase-muted mt-0.5 text-xs">{formatPrice(unit_price, symbol)}</p>
          </div>
          <p className="shrink-0 text-sm font-semibold">{formatPrice(line_total, symbol)}</p>
        </div>

        {!is_available && <p className="auth-error mt-1 text-xs">No longer available</p>}

        <div className="mt-auto flex items-center justify-between gap-3 pt-2">
          <div className="cart-qty inline-flex items-center rounded-full">
            <button
              type="button"
              onClick={() => onQuantity(item.id, quantity - 1)}
              disabled={busy || quantity <= 1}
              aria-label={`Decrease quantity of ${product.name}`}
              className="cart-qty__btn flex h-8 w-8 items-center justify-center rounded-full"
            >
              {icon("M5 12h14")}
            </button>
            <span className="min-w-6 text-center text-sm tabular-nums" aria-live="polite" aria-label={`Quantity ${quantity}`}>
              {quantity}
            </span>
            <button
              type="button"
              onClick={() => onQuantity(item.id, quantity + 1)}
              disabled={busy || atMax}
              aria-label={`Increase quantity of ${product.name}`}
              className="cart-qty__btn flex h-8 w-8 items-center justify-center rounded-full"
            >
              {icon("M12 5v14M5 12h14")}
            </button>
          </div>
          <button
            type="button"
            onClick={() => onRemove(item.id)}
            disabled={busy}
            aria-label={`Remove ${product.name} from cart`}
            title="Remove"
            className="cart-remove-btn flex h-9 w-9 items-center justify-center rounded-full"
          >
            <FiTrash2 className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>
    </li>
  );
}

// The ONE cart drawer. It is mounted once in the root layout and opened through useCart().openCart(),
// so product cards, the navbar, and any future "add to cart" button all share it.
export default function CartDrawer() {
  const { items, itemCount, subtotal, currencySymbol, isOpen, pendingIds, closeCart, setQuantity, removeItem } = useCart();
  const panelRef = useRef(null);
  const closeRef = useRef(null);
  const isEmpty = items.length === 0;

  // Escape closes, Tab stays inside the drawer, the page behind does not scroll.
  useEffect(() => {
    if (!isOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();

    const onKeyDown = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        closeCart();
      } else if (e.key === "Tab") {
        const nodes = [...(panelRef.current?.querySelectorAll(FOCUSABLE) ?? [])].filter((n) => n.offsetParent !== null);
        if (nodes.length === 0) return;
        const first = nodes[0];
        const last = nodes[nodes.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [isOpen, closeCart]);

  const leave = () => closeCart(false); // navigating away: do not pull focus back to the opener

  return (
    <div className="cart-drawer fixed inset-0 z-[70]" data-open={isOpen} inert={!isOpen}>
      <div className="cart-drawer__backdrop absolute inset-0" onClick={() => closeCart()} aria-hidden="true" />

      <aside
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="cart-drawer-title"
        className="cart-drawer__panel absolute right-0 top-0 flex h-dvh w-full max-w-full flex-col sm:w-[26rem]"
      >
        <header className="cart-divider flex items-center justify-between gap-4 px-5 py-4 sm:px-6">
          <h2 id="cart-drawer-title" className="custom-font text-2xl leading-none">
            Your Cart
            {itemCount > 0 && <span className="showcase-muted ml-2 text-sm">({itemCount})</span>}
          </h2>
          <button ref={closeRef} type="button" onClick={() => closeCart()} aria-label="Close cart" className="cart-close flex h-10 w-10 items-center justify-center rounded-full">
            {icon("M6 6l12 12M18 6 6 18", "h-5 w-5")}
          </button>
        </header>

        {isEmpty ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 px-8 text-center">
            <span className="cart-empty-mark flex h-20 w-20 items-center justify-center rounded-full">
              {icon("M3 4h2l2.4 11h10.2L20 7H6M9 19.5h.01M17 19.5h.01", "h-8 w-8")}
            </span>
            <h3 className="custom-font text-2xl">Your cart is empty</h3>
            <p className="showcase-muted text-sm">Discover something you&apos;ll love.</p>
            <Link href={SHOP_ROUTE} onClick={leave} className="auth-btn auth-btn--primary mt-3 rounded-full px-8 py-3 text-sm font-medium">
              Continue Shopping
            </Link>
          </div>
        ) : (
          <>
            {/* Only this list scrolls; the summary below stays put */}
            <ul className="cart-list min-h-0 flex-1 overflow-y-auto px-5 sm:px-6">
              {items.map((item) => (
                <CartLine
                  key={item.id}
                  item={item}
                  symbol={currencySymbol}
                  busy={pendingIds.has(item.id)}
                  onQuantity={setQuantity}
                  onRemove={removeItem}
                  onNavigate={leave}
                />
              ))}
            </ul>

            <footer className="cart-divider cart-footer shrink-0 px-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-4 sm:px-6">
              <div className="flex items-baseline justify-between">
                <span className="text-sm">Subtotal</span>
                <span className="text-lg font-semibold">{formatPrice(subtotal, currencySymbol)}</span>
              </div>
              <p className="showcase-muted mt-1 text-xs">Shipping and taxes are calculated at checkout.</p>
              <div className="mt-4 flex flex-col gap-2.5">
                <Link href={CART_ROUTE} onClick={leave} className="auth-btn auth-btn--outline rounded-full px-6 py-3 text-center text-sm font-medium">
                  View Cart
                </Link>
                <Link href={CHECKOUT_ROUTE} onClick={leave} className="auth-btn auth-btn--primary rounded-full px-6 py-3 text-center text-sm font-medium">
                  Checkout
                </Link>
              </div>
            </footer>
          </>
        )}
      </aside>
    </div>
  );
}
