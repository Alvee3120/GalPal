"use client";

import { useEffect, useId, useRef, useState } from "react";

const HEIGHT = 240;
const PAD = { top: 16, right: 16, bottom: 28, left: 64 };
const BAR_MAX = 24;

// Round the axis up to a clean number and split it into 4 steps (0 / 25 / 50 / 75 / 100 ...).
function niceScale(max) {
  if (max <= 0) return { top: 4, ticks: [0, 1, 2, 3, 4] };
  const rough = max / 4;
  const power = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => s >= rough);
  return { top: step * 4, ticks: [0, 1, 2, 3, 4].map((i) => i * step) };
}

// A bucket's label. `point.date` is "YYYY-MM-DD" (day / week start / month) or "YYYY-MM-DDTHH:00" (hour); a week
// also carries `end`. Built from the string itself, so the site's time zone as the backend grouped it is kept.
function formatBucket(point, granularity, long = false) {
  const day = (iso) => new Date(`${iso.slice(0, 10)}T00:00:00`);
  const dm = (iso) => day(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  if (granularity === "hour") {
    const h = Number(point.date.slice(11, 13));
    const clock = `${h % 12 || 12}${h < 12 ? "am" : "pm"}`;
    return long ? `${clock} – ${((h + 1) % 12) || 12}${h + 1 < 12 || h + 1 === 24 ? "am" : "pm"}, ${dm(point.date)}` : clock;
  }
  if (granularity === "month") return day(point.date).toLocaleDateString("en-GB", { month: long ? "long" : "short", year: "numeric" });
  if (granularity === "week") return long ? `${dm(point.date)} – ${dm(point.end ?? point.date)} ${point.date.slice(0, 4)}` : dm(point.date);
  return day(point.date).toLocaleDateString("en-GB", long ? { weekday: "short", day: "numeric", month: "short", year: "numeric" } : { day: "numeric", month: "short" });
}

const UNIT = { hour: "hour", day: "day", week: "week", month: "month" };

// A single-series time chart drawn in plain SVG (no chart library in the project): `kind="area"` for money (a 2px
// line over a 10% wash) or `kind="bar"` for counts (<=24px columns, rounded tops, square at the baseline). One
// recessive axis, clean ticks, a crosshair tooltip on hover — also driven by the arrow keys when the chart is
// focused — and every value in the "View as table" disclosure, so nothing lives only in the tooltip. Colors come
// from the --color-chart-* tokens in globals.css.
export default function TimeSeriesChart({ title, data, valueKey, format, formatAxis = format, granularity, kind = "area", emptyText }) {
  const wrapRef = useRef(null);
  const [width, setWidth] = useState(0);
  const [active, setActive] = useState(null);
  const titleId = useId();

  useEffect(() => {
    const node = wrapRef.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const values = data.map((d) => Number(d[valueKey]) || 0);
  const isEmpty = values.every((v) => v === 0);
  const { top, ticks } = niceScale(Math.max(...values, 0));

  const plotW = Math.max(0, width - PAD.left - PAD.right);
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const n = data.length;
  const slot = n ? plotW / n : 0;
  const xAt = (i) => PAD.left + slot * i + slot / 2;
  const yAt = (v) => PAD.top + plotH - (v / top) * plotH;
  const barW = Math.max(2, Math.min(BAR_MAX, slot - 2)); // 2px surface gap between neighbours

  const labelEvery = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(plotW / 70))));
  const line = values.map((v, i) => `${i ? "L" : "M"}${xAt(i).toFixed(1)},${yAt(v).toFixed(1)}`).join(" ");
  const area = n ? `${line} L${xAt(n - 1).toFixed(1)},${yAt(0)} L${xAt(0).toFixed(1)},${yAt(0)} Z` : "";

  function pick(clientX) {
    const rect = wrapRef.current.getBoundingClientRect();
    const i = Math.floor((clientX - rect.left - PAD.left) / slot);
    setActive(i >= 0 && i < n ? i : null);
  }

  function onKeyDown(e) {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const step = e.key === "ArrowRight" ? 1 : -1;
      setActive((i) => Math.min(n - 1, Math.max(0, (i ?? (step > 0 ? -1 : n)) + step)));
    } else if (e.key === "Escape") setActive(null);
  }

  // Bar path: rounded 4px data-end, square at the baseline.
  const bar = (i, v) => {
    const x = xAt(i) - barW / 2;
    const y = yAt(v);
    const h = yAt(0) - y;
    if (h <= 0) return "";
    const r = Math.min(4, barW / 2, h);
    return `M${x},${yAt(0)} V${y + r} Q${x},${y} ${x + r},${y} H${x + barW - r} Q${x + barW},${y} ${x + barW},${y + r} V${yAt(0)} Z`;
  };

  const tooltipLeft = active === null ? 0 : Math.min(Math.max(xAt(active), 80), Math.max(80, width - 80));

  return (
    <div className="flex flex-col gap-3">
      <div ref={wrapRef} className="relative w-full" style={{ height: HEIGHT }}>
        {isEmpty ? (
          <div className="chart-empty flex h-full items-center justify-center rounded-xl text-sm">{emptyText}</div>
        ) : (
          width > 0 && (
            <>
              <svg
                width={width}
                height={HEIGHT}
                role="img"
                aria-labelledby={titleId}
                tabIndex={0}
                onPointerMove={(e) => pick(e.clientX)}
                onPointerLeave={() => setActive(null)}
                onKeyDown={onKeyDown}
                onBlur={() => setActive(null)}
                className="chart-svg block touch-pan-y"
              >
                <title id={titleId}>{`${title}. Use the left and right arrow keys to read each ${UNIT[granularity] ?? "day"}.`}</title>
                {ticks.map((t) => (
                  <g key={t}>
                    <line x1={PAD.left} x2={width - PAD.right} y1={yAt(t)} y2={yAt(t)} className="chart-grid" />
                    <text x={PAD.left - 8} y={yAt(t)} dy="0.32em" textAnchor="end" className="chart-axis-text">
                      {formatAxis(t)}
                    </text>
                  </g>
                ))}
                {data.map((d, i) =>
                  i % labelEvery === 0 ? (
                    <text key={d.date} x={xAt(i)} y={HEIGHT - 8} textAnchor="middle" className="chart-axis-text">
                      {formatBucket(d, granularity)}
                    </text>
                  ) : null,
                )}
                {active !== null && <line x1={xAt(active)} x2={xAt(active)} y1={PAD.top} y2={yAt(0)} className="chart-crosshair" />}
                {kind === "area" ? (
                  <>
                    <path d={area} className="chart-area" />
                    <path d={line} className="chart-line" />
                    {active !== null && <circle cx={xAt(active)} cy={yAt(values[active])} r={5} className="chart-dot" />}
                  </>
                ) : (
                  values.map((v, i) => <path key={data[i].date} d={bar(i, v)} className={`chart-bar ${active === i ? "chart-bar--active" : ""}`} />)
                )}
              </svg>
              {active !== null && (
                <div
                  role="status"
                  className="chart-tooltip pointer-events-none absolute top-0 -translate-x-1/2 rounded-lg px-3 py-2 text-xs"
                  style={{ left: tooltipLeft }}
                >
                  <p className="text-sm font-semibold">{format(values[active])}</p>
                  <p className="showcase-muted">{formatBucket(data[active], granularity, true)}</p>
                </div>
              )}
            </>
          )
        )}
      </div>
      {!isEmpty && (
        <details className="text-sm">
          <summary className="showcase-muted cursor-pointer text-xs hover:underline">View as table</summary>
          <div className="mt-2 max-h-56 overflow-y-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr>
                  <th scope="col" className="py-1 font-medium">{granularity === "month" ? "Month" : granularity === "hour" ? "Time" : granularity === "week" ? "Week" : "Date"}</th>
                  <th scope="col" className="py-1 text-right font-medium">{title}</th>
                </tr>
              </thead>
              <tbody>
                {data.map((d, i) => (
                  <tr key={d.date} className="chart-table-row">
                    <td className="py-1">{formatBucket(d, granularity, true)}</td>
                    <td className="py-1 text-right tabular-nums">{format(values[i])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </div>
  );
}
