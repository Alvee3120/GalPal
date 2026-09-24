"use client";

import { useEffect, useRef } from "react";
import { FiX } from "react-icons/fi";

const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"]), input:not([disabled]), select:not([disabled])';

// A generic titled dialog for content richer than a Yes/Cancel prompt (e.g. the Add Product picker), reusing the
// same .stock-modal* mechanics/classes already established by NotifyMeModal/ConfirmDialog (backdrop, Escape,
// focus trap, body-scroll lock) instead of a third pattern.
export default function Modal({ open, title, onClose, children, wide = false }) {
  const panelRef = useRef(null);
  const closeRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const raf = requestAnimationFrame(() => closeRef.current?.focus());
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

  return (
    <div className="stock-modal fixed inset-0 z-90" data-open={open} inert={!open}>
      <div className="stock-modal__backdrop absolute inset-0" aria-hidden="true" />
      <div className="fixed inset-0 flex items-center justify-center p-4" onClick={(e) => e.target === e.currentTarget && onClose()}>
        <div
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
          className={`stock-modal__panel relative flex max-h-[85dvh] w-full flex-col rounded-(--radius-card) p-5 sm:p-6 ${wide ? "max-w-lg" : "max-w-sm"}`}
        >
          <div className="mb-4 flex items-center justify-between gap-4">
            <h2 id="modal-title" className="custom-font text-xl">
              {title}
            </h2>
            <button ref={closeRef} type="button" onClick={onClose} aria-label="Close" className="cart-close flex h-9 w-9 items-center justify-center rounded-full">
              <FiX className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden">{children}</div>
        </div>
      </div>
    </div>
  );
}
