"use client";

import { useEffect, useRef, useState } from "react";
import { FiX } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { isValidBdPhone, normalizeBdPhone } from "@/lib/phone";
import { requestStockNotification } from "@/lib/notifyStock";

const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"]), input:not([disabled])';

// Premium "Notify Me" modal for GUEST visitors only (a logged-in user is subscribed directly, with
// no modal — see ProductCardAction/ProductDetailContent). Asks for a phone number and subscribes it
// to a back-in-stock alert for `productId` (optionally one specific `variantId`). No modal library
// existed in the codebase, so this one borrows the same open/close/focus-trap mechanics as
// MobileFilterDrawer.jsx.
export default function NotifyMeModal({ open, onClose, productId, productName, variantId }) {
  const [phone, setPhone] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const panelRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const raf = requestAnimationFrame(() => inputRef.current?.focus());
    const onKeyDown = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
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
      cancelAnimationFrame(raf);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting) return;
    if (!isValidBdPhone(phone)) {
      notify.error("Please enter a valid phone number.");
      return;
    }
    setSubmitting(true);
    const result = await requestStockNotification({ productId, variantId, phone: normalizeBdPhone(phone) });
    setSubmitting(false);
    if (result.ok) {
      notify.success("You'll be notified when this product is back in stock.");
      setPhone("");
      onClose();
      return;
    }
    notify.error(result.message);
  }

  return (
    <div className="stock-modal fixed inset-0 z-[80]" data-open={open} inert={!open}>
      <div className="stock-modal__backdrop absolute inset-0" aria-hidden="true" />
      <div className="fixed inset-0 flex items-center justify-center p-4" onClick={(e) => e.target === e.currentTarget && onClose()}>
        <div
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby="notify-me-title"
          className="stock-modal__panel relative w-full max-w-sm rounded-[var(--radius-card)] p-5 sm:p-6"
        >
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="cart-close absolute right-3 top-3 flex h-9 w-9 items-center justify-center rounded-full"
          >
            <FiX className="h-5 w-5" aria-hidden="true" />
          </button>

          <h2 id="notify-me-title" className="custom-font pr-8 text-xl">
            Notify Me
          </h2>
          <p className="showcase-muted mt-2 text-sm">Get notified when this product is back in stock.</p>
          {productName && <p className="mt-3 text-sm font-medium">{productName}</p>}

          <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-1.5">
            <label htmlFor="notify-me-phone" className="text-sm font-medium">
              Phone Number <span aria-hidden="true">*</span>
            </label>
            <input
              ref={inputRef}
              id="notify-me-phone"
              name="phone"
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              placeholder="Enter your phone number"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              disabled={submitting}
              className="auth-input w-full rounded-lg px-3 py-2.5 text-sm"
            />
            <button
              type="submit"
              disabled={submitting || !phone.trim()}
              className="auth-btn auth-btn--primary mt-4 w-full rounded-full py-3 text-sm font-medium"
            >
              {submitting ? "Submitting..." : "Notify Me"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
