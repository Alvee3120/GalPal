"use client";

import { useState } from "react";
import { FiCheck, FiX } from "react-icons/fi";

// The coupon code box, shared by the cart summary and checkout. It applies the code to the CART (POST /cart/coupon/ via
// CartProvider.applyCoupon), where the backend checks it against the cart; checkout then recalculates and re-checks
// it again when the order is placed. Not a <form>, so it can sit inside checkout's form (Enter applies the code).
export default function CouponBox({ id, coupon, busy, onApply, onRemove }) {
  const [code, setCode] = useState("");

  function apply() {
    const trimmed = code.trim();
    if (!trimmed || busy) return;
    onApply(trimmed);
    setCode("");
  }

  return (
    <div>
      <div className="flex gap-2">
        <label htmlFor={id} className="sr-only">
          Coupon code
        </label>
        <input
          id={id}
          type="text"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              apply();
            }
          }}
          placeholder="Coupon code"
          autoComplete="off"
          disabled={busy}
          className="cart-voucher-input min-w-0 flex-1 rounded-full px-4 py-2 text-sm uppercase placeholder:normal-case"
        />
        <button type="button" onClick={apply} disabled={busy || !code.trim()} className="auth-btn auth-btn--primary shrink-0 rounded-full px-5 py-2 text-sm font-medium">
          {busy ? "Applying..." : "Apply"}
        </button>
      </div>

      {coupon && (
        <div className="cart-coupon-chip mt-3 flex items-center justify-between gap-2 rounded-full px-3 py-1.5 text-xs font-medium">
          <span className="flex items-center gap-1.5">
            <FiCheck className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            {coupon.code} applied
          </span>
          <button type="button" onClick={onRemove} disabled={busy} aria-label="Remove coupon" className="cart-coupon-chip__remove flex h-5 w-5 items-center justify-center rounded-full">
            <FiX className="h-3 w-3" aria-hidden="true" />
          </button>
        </div>
      )}
    </div>
  );
}
