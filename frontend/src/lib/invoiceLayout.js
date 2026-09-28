// Invoice print layout (A4): the admin's Invoice Print Settings, stored in Site Settings. Mirrors the backend's
// apps.site_settings.models.INVOICE_LAYOUT (same keys without the "invoice_" prefix, same defaults and limits — the
// backend validates the limits too). Every invoice's preview, print, PDF and reprint uses the saved values.
export const LAYOUT_FIELDS = [
  { key: "content_width", label: "Content Width", unit: "%", min: 70, max: 100, step: 1, default: 100 },
  { key: "padding_top", label: "Top Padding", unit: "mm", min: 0, max: 25, step: 0.5, default: 9 },
  { key: "padding_right", label: "Right Padding", unit: "mm", min: 0, max: 25, step: 0.5, default: 9 },
  { key: "padding_bottom", label: "Bottom Padding", unit: "mm", min: 0, max: 25, step: 0.5, default: 9 },
  { key: "padding_left", label: "Left Padding", unit: "mm", min: 0, max: 25, step: 0.5, default: 9 },
  { key: "text_size", label: "Text Size", unit: "pt", min: 8, max: 12, step: 0.5, default: 9 },
  { key: "section_spacing", label: "Section Spacing", unit: "mm", min: 1, max: 10, step: 0.5, default: 4 },
  { key: "logo_width", label: "Logo Size", unit: "mm", min: 30, max: 80, step: 1, default: 58 },
  { key: "qr_size", label: "QR Code Size", unit: "mm", min: 20, max: 40, step: 1, default: 28 },
  { key: "barcode_height", label: "Barcode Size", unit: "mm", min: 12, max: 24, step: 1, default: 16 },
];

export const DEFAULT_LAYOUT = Object.fromEntries(LAYOUT_FIELDS.map((f) => [f.key, f.default]));

const clamp = (field, value) => {
  const n = Number(value);
  return Number.isFinite(n) ? Math.min(field.max, Math.max(field.min, n)) : field.default;
};

// Any layout-like object (the invoice's `layout`, or Site Settings' invoice_* strings) -> a complete, in-range layout.
export function normalizeLayout(values = {}, prefix = "") {
  return Object.fromEntries(LAYOUT_FIELDS.map((f) => [f.key, clamp(f, values?.[prefix + f.key])]));
}

// The CSS custom properties the invoice stylesheet derives every size from (globals.css, "Invoice" section).
export function layoutStyle(layout) {
  const l = normalizeLayout(layout);
  return {
    "--inv-pad-top": `${l.padding_top}mm`,
    "--inv-pad-right": `${l.padding_right}mm`,
    "--inv-pad-bottom": `${l.padding_bottom}mm`,
    "--inv-pad-left": `${l.padding_left}mm`,
    "--inv-content-width": `${l.content_width}%`,
    "--inv-text": `${l.text_size}pt`,
    "--inv-gap": `${l.section_spacing}mm`,
    "--inv-logo": `${l.logo_width}mm`,
    "--inv-qr": `${l.qr_size}mm`,
    "--inv-barcode": `${l.barcode_height}mm`,
  };
}

// Global Invoice Settings + one invoice's own overrides ("Customize This Invoice"): { ...global, ...overrides }. The
// backend applies the same rule (apps.orders.invoice.resolve_layout) to every invoice's `layout` — preview, print,
// reprint and PDF — so this is only needed while editing, before the overrides are saved.
export function resolveInvoiceLayout(globalLayout, overrides) {
  return normalizeLayout({ ...normalizeLayout(globalLayout), ...(overrides ?? {}) });
}

// The values of `layout` that differ from the global settings — all that gets saved for one invoice.
export function layoutOverrides(layout, globalLayout) {
  const draft = normalizeLayout(layout);
  const base = normalizeLayout(globalLayout);
  return Object.fromEntries(LAYOUT_FIELDS.filter((f) => draft[f.key] !== base[f.key]).map((f) => [f.key, draft[f.key]]));
}
