"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { notify } from "@/lib/notify";
import { messageFor } from "@/lib/apiError";

const EMPTY_CART = { items: [], item_count: 0, subtotal: "0.00", discount: "0.00", coupon: null, total: "0.00" };

// Calls the /api/cart proxy. On failure throws an Error carrying `status` (0 = network) and the API's
// field `details`; callers turn that into a friendly toast via messageFor(), never by showing err.message.
async function cartApi(path, options = {}) {
  let res;
  try {
    res = await fetch(`/api/cart${path}`, {
      ...options,
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    });
  } catch {
    throw Object.assign(new Error("network"), { status: 0, details: null });
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw Object.assign(new Error("request failed"), { status: res.status, details: data?.error?.details ?? null });
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
// All cart feedback goes through the global toast (notify).
export function CartProvider({ children, currencySymbol = "" }) {
  const router = useRouter();
  const [cart, setCart] = useState(EMPTY_CART);
  const [isOpen, setIsOpen] = useState(false);
  const [pendingIds, setPendingIds] = useState(() => new Set());
  const [couponBusy, setCouponBusy] = useState(false);
  // True only until the initial cart fetch settles. The drawer never needs this (it opens well after that
  // fetch has finished); the Cart page reads it to avoid flashing "Your cart is empty" before real data arrives.
  const [loading, setLoading] = useState(true);
  const triggerRef = useRef(null); // element that opened the drawer, focused again on close
  const mutated = useRef(false); // a mutation started: ignore a slower initial load

  // Restore the cart on first load (guest token / login are carried by cookies through the proxy).
  useEffect(() => {
    cartApi("/")
      .then((data) => {
        if (!mutated.current) setCart(data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
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
  // `variantId` is required for a product that has variants (the backend rejects a variant-less add for one).
  // `productSlug` lets the "choose options" toast link to the product page. Success has no toast (the drawer opens and the
  // button confirms it); failures are always toasted. Returns { ok }.
  const addItem = useCallback(
    async (productId, quantity = 1, { productSlug, variantId } = {}) => {
      mutated.current = true;
      try {
        const body = { product_id: productId, quantity };
        if (variantId) body.variant_id = variantId;
        setCart(await cartApi("/items/", { method: "POST", body: JSON.stringify(body) }));
        return { ok: true };
      } catch (err) {
        if (err.details?.variant_id) {
          notify.error("Please choose an option first.", {
            action: productSlug ? { label: "Choose options", onClick: () => router.push(`/products/${productSlug}`) } : undefined,
          });
        } else {
          notify.error(messageFor(err, "Unable to add product to cart."));
        }
        return { ok: false };
      }
    },
    [router],
  );

  const setQuantity = useCallback(
    async (itemId, quantity) => {
      if (quantity < 1) return;
      mutated.current = true;
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
        notify.error(messageFor(err, "Unable to update quantity."));
      } finally {
        setPending(itemId, false);
      }
    },
    [cart],
  );

  const removeItem = useCallback(
    async (itemId) => {
      mutated.current = true;
      const before = cart;
      setCart((c) => withItems(c, c.items.filter((i) => i.id !== itemId)));
      setPending(itemId, true);
      try {
        setCart(await cartApi(`/items/${itemId}/`, { method: "DELETE" })); // no success toast: the line disappearing is the feedback
      } catch (err) {
        setCart(before);
        notify.error(messageFor(err, "Unable to remove product from cart."));
      } finally {
        setPending(itemId, false);
      }
    },
    [cart],
  );

  // Applies a coupon code (the backend validates it against the cart's current contents) or, with no code,
  // removes whichever coupon is applied. Success shows a toast: unlike add/remove-item, nothing else on the
  // page (no drawer opening, no line disappearing) confirms it happened.
  const applyCoupon = useCallback(async (code) => {
    setCouponBusy(true);
    try {
      const data = await cartApi("/coupon/", { method: "POST", body: JSON.stringify({ code }) });
      setCart(data);
      notify.success("Coupon applied successfully.");
      return { ok: true };
    } catch (err) {
      notify.error(messageFor(err, "That coupon code isn't valid."));
      return { ok: false };
    } finally {
      setCouponBusy(false);
    }
  }, []);

  const removeCoupon = useCallback(async () => {
    setCouponBusy(true);
    try {
      setCart(await cartApi("/coupon/", { method: "DELETE" }));
      notify.success("Coupon removed.");
    } catch (err) {
      notify.error(messageFor(err, "Unable to remove the coupon."));
    } finally {
      setCouponBusy(false);
    }
  }, []);

  // Re-reads the cart from the server (e.g. to pick up a change made in another tab). Returns { ok }.
  const refreshCart = useCallback(async () => {
    try {
      setCart(await cartApi("/"));
      return { ok: true };
    } catch (err) {
      notify.error(messageFor(err, "Unable to refresh your cart."));
      return { ok: false };
    }
  }, []);

  const value = useMemo(
    () => ({
      items: cart.items,
      itemCount: cart.item_count,
      subtotal: cart.subtotal,
      discount: cart.discount,
      coupon: cart.coupon,
      total: cart.total,
      couponBusy,
      loading,
      currencySymbol,
      isOpen,
      pendingIds,
      openCart,
      closeCart,
      addItem,
      setQuantity,
      removeItem,
      applyCoupon,
      removeCoupon,
      refreshCart,
    }),
    [cart, couponBusy, loading, currencySymbol, isOpen, pendingIds, openCart, closeCart, addItem, setQuantity, removeItem, applyCoupon, removeCoupon, refreshCart],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used inside <CartProvider>");
  return ctx;
}
