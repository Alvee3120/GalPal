"use client";

import { useState } from "react";

const SIZE = 168;
const STROKE = 22;
const R = (SIZE - STROKE) / 2;
const C = 2 * Math.PI * R;
const GAP = 2; // px of surface between segments

// Order status donut: one segment per status with orders, colored by the existing status tokens (the same palette as
// the order status dropdown), the total in the middle, and a legend that always names every status with its count —
// so identity never rests on color alone. Hovering / focusing a legend row highlights its segment.
export default function StatusDonut({ counts, order, labels, emptyText }) {
  const [active, setActive] = useState(null);
  const total = order.reduce((sum, s) => sum + (counts[s] ?? 0), 0);
  const visible = order.filter((s) => (counts[s] ?? 0) > 0);

  let offset = 0;
  const segments = visible.map((status) => {
    const length = ((counts[status] ?? 0) / total) * C;
    const segment = { status, dash: Math.max(0, length - (visible.length > 1 ? GAP : 0)), offset };
    offset += length;
    return segment;
  });

  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-center">
      <div className="relative shrink-0" style={{ width: SIZE, height: SIZE }}>
        <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label={`${total} orders by status`}>
          <circle cx={SIZE / 2} cy={SIZE / 2} r={R} className="donut-track" strokeWidth={STROKE} fill="none" />
          {total > 0 &&
            segments.map((s) => (
              <circle
                key={s.status}
                cx={SIZE / 2}
                cy={SIZE / 2}
                r={R}
                fill="none"
                strokeWidth={active === s.status ? STROKE + 4 : STROKE}
                strokeDasharray={`${s.dash} ${C - s.dash}`}
                strokeDashoffset={-s.offset}
                transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
                data-status={s.status}
                className={`donut-segment ${active && active !== s.status ? "donut-segment--dim" : ""}`}
              />
            ))}
        </svg>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-semibold tabular-nums">{active ? counts[active] : total}</span>
          <span className="showcase-muted text-xs">{active ? labels[active] : "Orders"}</span>
        </div>
      </div>

      {total === 0 ? (
        <p className="showcase-muted text-sm">{emptyText}</p>
      ) : (
        <ul className="grid w-full min-w-0 grid-cols-1 gap-1.5 min-[380px]:grid-cols-2 sm:grid-cols-1">
          {order.map((status) => {
            const n = counts[status] ?? 0;
            return (
              <li key={status}>
                <button
                  type="button"
                  onMouseEnter={() => n && setActive(status)}
                  onMouseLeave={() => setActive(null)}
                  onFocus={() => n && setActive(status)}
                  onBlur={() => setActive(null)}
                  className="donut-legend flex w-full items-center justify-between gap-3 rounded-md px-2 py-1 text-left text-sm"
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <span data-status={status} className="order-status order-status--dot h-2.5 w-2.5 shrink-0 rounded-full" aria-hidden="true" />
                    <span className="truncate">{labels[status] ?? status}</span>
                  </span>
                  <span className="tabular-nums">
                    <span className="font-semibold">{n}</span>
                    <span className="showcase-muted ml-1.5 text-xs">{total ? Math.round((n / total) * 100) : 0}%</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
