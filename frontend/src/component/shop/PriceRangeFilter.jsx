"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { buildShopHref } from "@/lib/shopQuery";

const COMMIT_DELAY_MS = 450;

// Dual-thumb price slider. Both <input type="range"> sit on top of each other; only their thumbs are
// interactive (the track itself has pointer-events: none, see .shop-range in globals.css), which is the
// standard way to build an overlapping two-handle slider from two native inputs.
// Changes apply to the URL after a short pause, so the grid doesn't refetch on every pixel of drag.
// The parent gives this a `key` tied to the URL's price values, so an external change (a filter tag removed,
// Clear All) remounts it with a fresh initial state instead of syncing local state from props in an effect.
export default function PriceRangeFilter({ bounds, searchParams, currencySymbol }) {
  const router = useRouter();
  const min = bounds.min;
  const max = Math.max(bounds.max, bounds.min + 1);
  const [range, setRange] = useState([
    Number(searchParams.price_min ?? min),
    Number(searchParams.price_max ?? max),
  ]);
  const timer = useRef(null);

  useEffect(() => () => clearTimeout(timer.current), []);

  function commit(next) {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      const [lo, hi] = next;
      router.push(
        buildShopHref(searchParams, {
          price_min: lo > min ? lo : null,
          price_max: hi < max ? hi : null,
        }),
      );
    }, COMMIT_DELAY_MS);
  }

  function update(index, value) {
    setRange((prev) => {
      const next = [...prev];
      next[index] = value;
      if (next[0] > next[1]) next[index === 0 ? 1 : 0] = value; // keep min <= max
      commit(next);
      return next;
    });
  }

  const pct = (v) => ((v - min) / (max - min)) * 100;

  return (
    <div>
      <div className="shop-range relative h-5">
        <div className="shop-range__track absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full" />
        <div
          className="shop-range__fill absolute top-1/2 h-1 -translate-y-1/2 rounded-full"
          style={{ left: `${pct(range[0])}%`, right: `${100 - pct(range[1])}%` }}
        />
        <input
          type="range"
          min={min}
          max={max}
          value={range[0]}
          onChange={(e) => update(0, Number(e.target.value))}
          aria-label="Minimum price"
          className="shop-range__input absolute inset-x-0 top-0 w-full"
        />
        <input
          type="range"
          min={min}
          max={max}
          value={range[1]}
          onChange={(e) => update(1, Number(e.target.value))}
          aria-label="Maximum price"
          className="shop-range__input absolute inset-x-0 top-0 w-full"
        />
      </div>
      <p className="mt-2 text-sm">
        {currencySymbol}
        {range[0].toLocaleString()} - {currencySymbol}
        {range[1].toLocaleString()}
      </p>
    </div>
  );
}
