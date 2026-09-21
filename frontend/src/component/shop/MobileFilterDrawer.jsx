"use client";

import { useEffect, useRef, useState } from "react";
import { FiSliders, FiX } from "react-icons/fi";
import ShopFilters from "./ShopFilters";

const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"]), input';

// Below lg the filter sidebar becomes a toggle button + a right-side drawer holding the same <ShopFilters>.
export default function MobileFilterDrawer({ activeCount, ...filterProps }) {
  const [open, setOpen] = useState(false);
  const panelRef = useRef(null);
  const closeRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    const onKeyDown = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
      } else if (e.key === "Tab") {
        const nodes = [...(panelRef.current?.querySelectorAll(FOCUSABLE) ?? [])];
        if (!nodes.length) return;
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
  }, [open]);

  return (
    <div className="lg:hidden">
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        className="shop-filter-toggle inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium"
      >
        <FiSliders className="h-4 w-4" aria-hidden="true" />
        Filter Options
        {activeCount > 0 && <span className="shop-filter-toggle__count flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-xs">{activeCount}</span>}
      </button>

      {/* Same slide-in-from-right drawer look as the cart (shared CSS: .shop-drawer* rides along with .cart-drawer*
          in globals.css), but its own class names — a shared class name with the real cart drawer would make the
          two indistinguishable to anything that queries by class (including this file's own tests). */}
      <div className="shop-drawer fixed inset-0 z-[70]" data-open={open} inert={!open}>
        <div className="shop-drawer__backdrop absolute inset-0" onClick={() => setOpen(false)} aria-hidden="true" />
        <aside
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          aria-label="Filter Options"
          className="shop-drawer__panel absolute right-0 top-0 flex h-dvh w-full max-w-sm flex-col overflow-y-auto p-5"
        >
          <div className="mb-5 flex items-center justify-between">
            <h2 className="custom-font text-xl">Filter Options</h2>
            <button ref={closeRef} type="button" onClick={() => setOpen(false)} aria-label="Close filters" className="cart-close flex h-9 w-9 items-center justify-center rounded-full">
              <FiX className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
          <ShopFilters {...filterProps} />
        </aside>
      </div>
    </div>
  );
}
