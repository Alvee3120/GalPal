"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useCart } from "@/component/cart/CartProvider";

const ADDED_MS = 1800;

// "Add to Cart" for any product card. Calls the shared cart, then opens the shared drawer.
export default function AddToCartButton({ product }) {
  const { addItem, openCart } = useCart();
  const [status, setStatus] = useState("idle"); // idle | adding | added
  const [problem, setProblem] = useState(null); // { message, needsVariant }
  const timer = useRef(null);
  const buttonRef = useRef(null);

  useEffect(() => () => clearTimeout(timer.current), []);

  const outOfStock = product.in_stock === false;

  async function handleAdd() {
    if (status === "adding") return;
    setProblem(null);
    setStatus("adding");
    const result = await addItem(product.id, 1);
    if (!result.ok) {
      setStatus("idle");
      setProblem(result);
      return;
    }
    setStatus("added");
    openCart(buttonRef.current);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setStatus("idle"), ADDED_MS);
  }

  const label = outOfStock ? "Out of stock" : status === "adding" ? "Adding..." : status === "added" ? "Added ✓" : "Add to Cart";

  return (
    <div className="mt-3 sm:mt-4">
      <button
        ref={buttonRef}
        type="button"
        onClick={handleAdd}
        disabled={outOfStock || status === "adding"}
        aria-label={outOfStock ? `${product.name} is out of stock` : `Add ${product.name} to cart`}
        className="auth-btn auth-btn--primary w-full rounded-full px-4 py-2.5 text-sm font-medium transition-transform duration-200 active:scale-[0.98] motion-reduce:transition-none motion-reduce:active:scale-100"
      >
        <span aria-live="polite">{label}</span>
      </button>
      {problem && (
        <p role="alert" className="auth-error mt-2 text-xs leading-snug">
          {problem.message}{" "}
          {problem.needsVariant && (
            <Link href={`/products/${product.slug}`} className="auth-link font-medium">
              Choose options
            </Link>
          )}
        </p>
      )}
    </div>
  );
}
