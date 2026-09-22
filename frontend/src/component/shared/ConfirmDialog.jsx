"use client";

import { useEffect, useRef } from "react";

const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"]), input:not([disabled])';

// A generic Yes/Cancel confirmation, reusing the exact modal mechanics/styling already built for NotifyMeModal
// (component/shared/NotifyMeModal.jsx: the .stock-modal* classes — a centered backdrop+card, not stock-specific
// despite the name) instead of a second modal pattern. Used for "delete this address?", and reusable anywhere else
// a destructive action needs a confirmation.
export default function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  busyLabel = "Working...",
  busy = false,
  onConfirm,
  onCancel,
}) {
  const panelRef = useRef(null);
  const confirmRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const raf = requestAnimationFrame(() => confirmRef.current?.focus());
    const onKeyDown = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
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
  }, [open, onCancel]);

  return (
    <div className="stock-modal fixed inset-0 z-90" data-open={open} inert={!open}>
      <div className="stock-modal__backdrop absolute inset-0" aria-hidden="true" />
      <div className="fixed inset-0 flex items-center justify-center p-4" onClick={(e) => e.target === e.currentTarget && onCancel()}>
        <div
          ref={panelRef}
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="confirm-dialog-title"
          className="stock-modal__panel relative w-full max-w-sm rounded-(--radius-card) p-5 sm:p-6"
        >
          <h2 id="confirm-dialog-title" className="custom-font text-xl">
            {title}
          </h2>
          {description && <p className="showcase-muted mt-2 text-sm">{description}</p>}
          <div className="mt-5 flex justify-end gap-3">
            <button type="button" onClick={onCancel} disabled={busy} className="auth-btn auth-btn--outline rounded-full px-5 py-2 text-sm font-medium">
              {cancelLabel}
            </button>
            <button
              ref={confirmRef}
              type="button"
              onClick={onConfirm}
              disabled={busy}
              className="auth-btn confirm-dialog__danger rounded-full px-5 py-2 text-sm font-medium"
            >
              {busy ? busyLabel : confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
