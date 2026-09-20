"use client";

import { useEffect, useState } from "react";
import ProductCard from "@/component/shared/ProductCard";

// ONE fixed-size product container under a video. Which product it shows (`index`) is decided by the parent, which
// rotates it on a timer; this component only draws it. The container never changes size: the outgoing product slides
// up and out while the next slides up and in, both inside the same clipped box, so nothing around it moves.
// Small dots (only when the video has several products) let the visitor pick one; the row is always reserved so
// videos with one product and videos with many stay the same height.
export default function ProductSlot({ products, index, currencySymbol, onHover, onInteract, onSelect }) {
  // keep the previous product around just long enough to animate it out (derived during render)
  const [view, setView] = useState({ cur: index, prev: null });
  if (view.cur !== index) setView({ cur: index, prev: view.cur });

  useEffect(() => {
    if (view.prev === null) return;
    const timer = setTimeout(() => setView((v) => ({ ...v, prev: null })), 650);
    return () => clearTimeout(timer);
  }, [view.prev, view.cur]);

  const many = products.length > 1;
  const transitioning = view.prev !== null;

  return (
    <div>
      <div
        className="vc-slot relative overflow-hidden"
        onPointerEnter={(e) => e.pointerType === "mouse" && onHover(true)}
        onPointerLeave={(e) => e.pointerType === "mouse" && onHover(false)}
        onFocus={(e) => e.target.matches(":focus-visible") && onHover(true)}
        onBlur={() => onHover(false)}
        onPointerDown={onInteract}
        onTouchStart={onInteract}
      >
        {transitioning && (
          <div key={`out-${view.prev}`} className="vc-slot__layer vc-slot__layer--out absolute inset-0" aria-hidden="true" inert>
            <ProductCard product={products[view.prev]} currencySymbol={currencySymbol} variant="compact" className="h-full w-full" />
          </div>
        )}
        <div key={`in-${view.cur}`} className={`vc-slot__layer absolute inset-0 ${transitioning ? "vc-slot__layer--in" : ""}`}>
          <ProductCard product={products[view.cur]} currencySymbol={currencySymbol} variant="compact" className="h-full w-full" />
        </div>
      </div>

      <div className="vc-dots flex h-5 items-center justify-center" role={many ? "group" : undefined} aria-label={many ? "Products in this video" : undefined}>
        {many &&
          products.map((product, i) => (
            <button
              key={product.id}
              type="button"
              onClick={() => onSelect(i)}
              aria-label={`Show product ${i + 1} of ${products.length}: ${product.name}`}
              aria-current={i === view.cur}
              className="vc-dot-hit flex h-5 w-4 items-center justify-center"
            >
              <span className="vc-dot block rounded-full" />
            </button>
          ))}
      </div>
    </div>
  );
}
