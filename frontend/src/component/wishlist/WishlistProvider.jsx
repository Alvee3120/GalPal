"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { notify } from "@/lib/notify";

const WishlistContext = createContext(null);

// The logged-in customer's saved product ids, shared by every heart button. Loaded once from /api/wishlist (a guest
// gets 401 and simply has an empty, read-only wishlist). Toggling saves/removes through the backend — it never
// touches the cart or stock.
export function WishlistProvider({ children }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ids, setIds] = useState(() => new Set());
  const [signedIn, setSignedIn] = useState(null); // null = not known yet
  const [pending, setPending] = useState(() => new Set());

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/wishlist", { cache: "no-store" });
      if (res.status === 401) {
        setSignedIn(false);
        setIds(new Set());
        return;
      }
      const data = await res.json().catch(() => null);
      if (res.ok && data) {
        setSignedIn(true);
        setIds(new Set(data.product_ids));
      }
    } catch {
      // the hearts just stay empty; nothing else depends on this
    }
  }, []);

  useEffect(() => {
    load(); // eslint-disable-line react-hooks/set-state-in-effect -- syncing with the server once per page load
  }, [load, pathname]);

  const toggle = useCallback(
    async (productId, name) => {
      if (signedIn === false) {
        notify.error("Please log in to save products to your wishlist.");
        router.push("/login");
        return;
      }
      if (pending.has(productId)) return;
      const saved = ids.has(productId);
      setPending((s) => new Set(s).add(productId));
      setIds((s) => {
        const next = new Set(s);
        if (saved) next.delete(productId);
        else next.add(productId);
        return next;
      });
      try {
        const res = saved
          ? await fetch(`/api/wishlist/${productId}`, { method: "DELETE", cache: "no-store" })
          : await fetch("/api/wishlist", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ product_id: productId }),
              cache: "no-store",
            });
        const data = await res.json().catch(() => null);
        if (res.status === 401) {
          setSignedIn(false);
          setIds(new Set());
          notify.error("Please log in to save products to your wishlist.");
          router.push("/login");
          return;
        }
        if (!res.ok || !data) throw new Error();
        setIds(new Set(data.product_ids));
        notify.success(saved ? "Removed from your wishlist." : `${name ? `${name} saved` : "Saved"} to your wishlist.`);
      } catch {
        setIds((s) => {
          const next = new Set(s);
          if (saved) next.add(productId);
          else next.delete(productId);
          return next;
        });
        notify.error("Unable to update your wishlist. Please try again.");
      } finally {
        setPending((s) => {
          const next = new Set(s);
          next.delete(productId);
          return next;
        });
      }
    },
    [ids, pending, router, signedIn],
  );

  const value = useMemo(() => ({ ids, signedIn, toggle, isPending: (id) => pending.has(id) }), [ids, signedIn, toggle, pending]);
  return <WishlistContext.Provider value={value}>{children}</WishlistContext.Provider>;
}

export function useWishlist() {
  return useContext(WishlistContext);
}
