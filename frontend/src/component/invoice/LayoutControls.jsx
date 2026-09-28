"use client";

import { useLayoutEffect, useRef, useState } from "react";
import { normalizeLayout } from "@/lib/invoiceLayout";
import InvoiceTemplate from "./InvoiceTemplate";

// Shared by the global Invoice Settings page and "Customize This Invoice": one slider + number control per layout
// setting, and the live preview — the real InvoiceTemplate at its true A4 size, scaled down only to fit the screen.

const A4_WIDTH_PX = (210 / 25.4) * 96; // 210mm in CSS px
const A4_HEIGHT_PX = (297 / 25.4) * 96;
const FRAME_PAD = 16; // px around the scaled sheet

export function LayoutControl({ field, value, onChange }) {
  const id = `layout-${field.key}`;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-3 text-sm">
        <label htmlFor={id}>{field.label}</label>
        <span className="flex items-center gap-1">
          <input
            type="number"
            min={field.min}
            max={field.max}
            step={field.step}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onBlur={() => onChange(normalizeLayout({ [field.key]: value })[field.key])}
            aria-label={`${field.label} (${field.unit})`}
            className="checkout-input w-20 rounded-md px-2 py-1 text-right text-sm"
          />
          <span className="showcase-muted w-6 text-xs">{field.unit}</span>
        </span>
      </div>
      <input
        id={id}
        type="range"
        min={field.min}
        max={field.max}
        step={field.step}
        value={Number(value) || field.default}
        onChange={(e) => onChange(Number(e.target.value))}
        className="invoice-layout-range w-full"
        aria-valuetext={`${value} ${field.unit}`}
      />
    </div>
  );
}

// The invoice at its real A4 size (210mm wide, content height), on a 210×297mm sheet outline, scaled down to fit
// the column. Scaling happens here only — the invoice itself is laid out exactly as it prints.
export function A4Preview({ invoice }) {
  const frameRef = useRef(null);
  const pageRef = useRef(null);
  const [scale, setScale] = useState(1);
  const [height, setHeight] = useState(A4_HEIGHT_PX);

  useLayoutEffect(() => {
    const frame = frameRef.current;
    const page = pageRef.current;
    if (!frame || !page) return undefined;
    const measure = () => {
      setScale(Math.min(1, (frame.clientWidth - 2 * FRAME_PAD) / A4_WIDTH_PX));
      setHeight(page.offsetHeight);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(frame);
    observer.observe(page);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={frameRef} className="invoice-a4-frame" style={{ padding: FRAME_PAD, height: height * scale + 2 * FRAME_PAD }}>
      <div style={{ width: A4_WIDTH_PX, transform: `scale(${scale})`, transformOrigin: "top left" }}>
        <div ref={pageRef} className="invoice-a4-page">
          <InvoiceTemplate invoice={invoice} a4 />
        </div>
      </div>
    </div>
  );
}
