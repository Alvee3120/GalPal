"use client";

import { useEffect, useRef, useState } from "react";
import { GoCheck, GoPlus } from "react-icons/go";
import { useCart } from "@/component/cart/CartProvider";
import { notify } from "@/lib/notify";
import { getStockCap, quantityInCart, remainingToAdd } from "@/lib/stockLimit";

const ADDED_MS = 1800;

// "Add to Cart" for any product card (never rendered for a variable product — that gets "Select Options" instead,
// see ProductCardAction — so `product` here is always simple, and its OWN stock/manage_stock is the cap). Calls
// the shared cart, then opens the shared drawer. A successful add shows no toast: the cart drawer opening and the
// button briefly changing ("Added ✓" / a check icon) are the confirmation. Failures are still announced by a toast
// (raised in the cart, or the guard below for the "already have every unit in the cart" case that guard catches
// before ever calling the API).
//   default  full-width "Add to Cart" pill
//   compact  round icon-only "+" button for the compact product card (e.g. under a shoppable video)
export default function AddToCartButton({ product, compact = false }) {
  const { addItem, openCart, items } = useCart();
  const [status, setStatus] = useState("idle"); // idle | adding | added
  const timer = useRef(null);
  const buttonRef = useRef(null);

  useEffect(() => () => clearTimeout(timer.current), []);

  const outOfStock = product.in_stock === false;
  const cap = getStockCap(product);
  const inCart = quantityInCart(items, product.id);
  const remaining = remainingToAdd(cap, inCart);
  const maxedOut = !outOfStock && remaining <= 0;

  async function handleAdd() {
    if (status === "adding") return;
    if (maxedOut) {
      notify.error(cap === 1 ? "Only 1 item is available in stock." : `Only ${cap} items are available in stock.`);
      return;
    }
    setStatus("adding");
    const result = await addItem(product.id, 1, { productSlug: product.slug });
    if (!result.ok) {
      setStatus("idle"); // the error toast was already shown by the cart
      return;
    }
    setStatus("added");
    openCart(buttonRef.current);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setStatus("idle"), ADDED_MS);
  }

  const ariaLabel = outOfStock ? `${product.name} is out of stock` : maxedOut ? `${product.name}: maximum quantity already in cart` : `Add ${product.name} to cart`;

  if (compact) {
    return (
      <div className="shrink-0">
        <button
          ref={buttonRef}
          type="button"
          onClick={handleAdd}
          disabled={outOfStock || maxedOut || status === "adding"}
          aria-label={ariaLabel}
          title={outOfStock ? "Sold out" : maxedOut ? "Maximum quantity in cart" : "Add to cart"}
          className="auth-btn auth-btn--primary flex h-10 w-10 items-center justify-center rounded-full transition-transform duration-200 active:scale-[0.94] motion-reduce:transition-none motion-reduce:active:scale-100"
        >
          {status === "added" ? <GoCheck className="h-5 w-5" aria-hidden="true" /> : <GoPlus className="h-5 w-5" aria-hidden="true" />}
        </button>
        <span className="sr-only" aria-live="polite">
          {status === "added" ? `${product.name} added to cart` : ""}
        </span>
      </div>
    );
  }

  const label = outOfStock
    ? "Out of stock"
    : maxedOut
      ? "Max in Cart"
      : status === "adding"
        ? "Adding..."
        : status === "added"
          ? "Added ✓"
          : "Add to Cart";

  return (
    <div className="mt-3 sm:mt-4">
      <button
        ref={buttonRef}
        type="button"
        onClick={handleAdd}
        disabled={outOfStock || maxedOut || status === "adding"}
        aria-label={ariaLabel}
        className="auth-btn auth-btn--primary w-full rounded-full px-4 py-2.5 text-sm font-medium transition-transform duration-200 active:scale-[0.98] motion-reduce:transition-none motion-reduce:active:scale-100"
      >
        <span aria-live="polite">{label}</span>
      </button>
    </div>
  );
}
