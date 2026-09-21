"use client";

import { useMemo, useSyncExternalStore } from "react";

const pad = (n) => String(n).padStart(2, "0");

// The current second, ticking once a second, for as long as the sale hasn't ended. `useSyncExternalStore` gives the
// server render no time at all (null), so the server and the first client render match — no hydration mismatch — and the
// countdown appears right after mount. The interval clears itself the moment the sale ends and on unmount.
function useSecondClock(stopAtMs) {
  const store = useMemo(
    () => ({
      subscribe(onChange) {
        const id = setInterval(() => {
          if (Date.now() >= stopAtMs) clearInterval(id);
          onChange();
        }, 1000);
        return () => clearInterval(id);
      },
      snapshot: () => Math.floor(Date.now() / 1000) * 1000,
      server: () => null,
    }),
    [stopAtMs],
  );
  return useSyncExternalStore(store.subscribe, store.snapshot, store.server);
}

// "Sale starts in" / "Sale ends in" countdown in four boxes (days, hrs, mins, secs). Give it the product's real
// `sale_start_at` / `sale_end_at` (ISO date-times from the API, which carry their own UTC offset, so the count is right
// in any browser timezone). It renders nothing unless both are valid and in order, and nothing once the sale has ended.
// Whether the product actually has a discount is the caller's check (it uses the page's existing price logic).
export default function SaleCountdown({ saleStartAt, saleEndAt, className = "" }) {
  const startMs = saleStartAt ? Date.parse(saleStartAt) : NaN;
  const endMs = saleEndAt ? Date.parse(saleEndAt) : NaN;
  const valid = Number.isFinite(startMs) && Number.isFinite(endMs) && startMs < endMs;
  const now = useSecondClock(valid ? endMs : 0);

  if (!valid || now === null || now >= endMs) return null;

  const beforeStart = now < startMs;
  const seconds = Math.max(0, Math.floor(((beforeStart ? startMs : endMs) - now) / 1000));
  const parts = [
    ["days", Math.floor(seconds / 86400)],
    ["hrs", Math.floor((seconds % 86400) / 3600)],
    ["mins", Math.floor((seconds % 3600) / 60)],
    ["secs", seconds % 60],
  ];
  const heading = beforeStart ? "Sale starts in" : "Sale ends in";

  return (
    <div className={className} role="timer" aria-label={heading}>
      <p className="sale-countdown__heading text-xs font-semibold uppercase tracking-widest">{heading}</p>
      <ol className="mt-2 flex gap-1.5 sm:gap-2">
        {parts.map(([label, value]) => (
          <li key={label} className="sale-countdown__box flex min-w-14 flex-col items-center rounded-lg px-2 py-2 sm:min-w-16 sm:px-3">
            <span className="text-xl font-bold leading-none tabular-nums sm:text-2xl">{pad(value)}</span>
            <span className="mt-1 text-[0.6875rem] leading-none sm:text-xs">{label}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
