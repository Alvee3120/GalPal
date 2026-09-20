"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

const EMPTY_CART = { items: [], item_count: 0, subtotal: "0.00" };

// Calls the /api/cart proxy. Throws an Error carrying the API's message and field `details`.
async function cartApi(path, options = {}) {
  let res;
  try {
    res = await fetch(`/api/cart${path}`, {
      ...options,
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    });
  } catch {
    throw Object.assign(new Error("We couldn't reach the cart. Please try again."), { details: null });
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = data?.error;
    throw Object.assign(new Error(err?.message ?? "Something went wrong. Please try again."), { details: err?.details ?? null });
  }
  return data;
}

// Local recompute used for instant (optimistic) quantity/remove updates; the server's cart replaces it right after.
function withItems(cart, items) {
  const cents = (v) => Math.round(Number(v) * 100);
  return {
    ...cart,
    items,
    item_count: items.reduce((sum, i) => sum + i.quantity, 0),
    subtotal: (items.reduce((sum, i) => sum + cents(i.line_total), 0) / 100).toFixed(2),
  };
}

const CartContext = createContext(null);

// ONE source of truth for the cart (backed by the backend cart API) and for the drawer's open state.
export function CartProvider({ children, currencySymbol = "" }) {
  const [cart, setCart] = useState(EMPTY_CART);
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState("");
  const [pendingIds, setPendingIds] = useState(() => new Set());
  const triggerRef = useRef(null); // element that opened the drawer, focused again on close
  const mutated = useRef(false); // a mutation started: ignore a slower initial load

  // Restore the cart on first load (guest token / login are carried by cookies through the proxy).
  useEffect(() => {
    cartApi("/")
      .then((data) => {
        if (!mutated.current) setCart(data);
      })
      .catch(() => {});
  }, []);

  // `trigger` is the element to refocus on close (a button that was disabled while adding has lost focus by then).
  const openCart = useCallback((trigger) => {
    triggerRef.current = trigger instanceof HTMLElement ? trigger : document.activeElement;
    setIsOpen(true);
  }, []);

  const closeCart = useCallback((restoreFocus = true) => {
    setIsOpen(false);
    if (restoreFocus) triggerRef.current?.focus?.();
  }, []);

  const setPending = (id, on) =>
    setPendingIds((prev) => {
      const next = new Set(prev);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });

  // Adds `quantity` more of a product (the backend increases an existing line instead of duplicating it).
  // Returns { ok: true } or { ok: false, message, needsVariant }.
  const addItem = useCallback(async (productId, quantity = 1) => {
    mutated.current = true;
    setError("");
    try {
      const data = await cartApi("/items/", { method: "POST", body: JSON.stringify({ product_id: productId, quantity }) });
      setCart(data);
      return { ok: true };
    } catch (err) {
      const needsVariant = Boolean(err.details?.variant_id);
      const message = needsVariant
        ? "Please choose an option first."
        : err.details?.product_id?.[0] ?? err.details?.quantity?.[0] ?? err.message;
      return { ok: false, message, needsVariant };
    }
  }, []);

  const setQuantity = useCallback(
    async (itemId, quantity) => {
      if (quantity < 1) return;
      mutated.current = true;
      setError("");
      const before = cart;
      setCart((c) =>
        withItems(
          c,
          c.items.map((i) =>
            i.id === itemId ? { ...i, quantity, line_total: (Math.round(Number(i.unit_price) * 100) * quantity / 100).toFixed(2) } : i,
          ),
        ),
      );
      setPending(itemId, true);
      try {
        setCart(await cartApi(`/items/${itemId}/`, { method: "PATCH", body: JSON.stringify({ quantity }) }));
      } catch (err) {
        setCart(before);
        setError(err.details?.quantity?.[0] ?? err.message);
      } finally {
        setPending(itemId, false);
      }
    },
    [cart],
  );

  const removeItem = useCallback(
    async (itemId) => {
      mutated.current = true;
      setError("");
      const before = cart;
      setCart((c) => withItems(c, c.items.filter((i) => i.id !== itemId)));
      setPending(itemId, true);
      try {
        setCart(await cartApi(`/items/${itemId}/`, { method: "DELETE" }));
      } catch (err) {
        setCart(before);
        setError(err.message);
      } finally {
        setPending(itemId, false);
      }
    },
    [cart],
  );

  const value = useMemo(
    () => ({
      items: cart.items,
      itemCount: cart.item_count,
      subtotal: cart.subtotal,
      currencySymbol,
      isOpen,
      error,
      pendingIds,
      openCart,
      closeCart,
      addItem,
      setQuantity,
      removeItem,
    }),
    [cart, currencySymbol, isOpen, error, pendingIds, openCart, closeCart, addItem, setQuantity, removeItem],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used inside <CartProvider>");
  return ctx;
}
