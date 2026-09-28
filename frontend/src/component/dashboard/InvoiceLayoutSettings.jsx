"use client";

import { useState } from "react";
import Link from "next/link";
import { FiAlertCircle, FiExternalLink, FiRotateCcw, FiSave } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { errorText } from "@/lib/productAdmin";
import { toInvoiceView } from "@/lib/invoice";
import { DEFAULT_LAYOUT, LAYOUT_FIELDS, normalizeLayout } from "@/lib/invoiceLayout";
import { useStaffHref } from "@/lib/staffPaths";
import { A4Preview, LayoutControl } from "@/component/invoice/LayoutControls";

const same = (a, b) => LAYOUT_FIELDS.every((f) => Number(a[f.key]) === Number(b[f.key]));

// Invoice Print Settings: the global A4 print layout every invoice uses (preview, print, PDF, reprint). Left: the
// settings; right: a live preview of a real invoice rendered by the SAME InvoiceTemplate, at the real 210mm width,
// scaled down only to fit the screen. Saved to Site Settings through PATCH /admin/orders/invoice-layout/ (Admin + CCE).
export default function InvoiceLayoutSettings({ savedLayout, invoice, orderId }) {
  const [saved, setSaved] = useState(savedLayout ?? DEFAULT_LAYOUT);
  const [draft, setDraft] = useState(savedLayout ?? DEFAULT_LAYOUT);
  const [saving, setSaving] = useState(false);
  const to = useStaffHref();
  const dirty = !same(draft, saved);
  const isDefault = same(draft, DEFAULT_LAYOUT);

  if (!savedLayout) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="custom-font text-2xl sm:text-3xl">Invoice Settings</h1>
        <div className="dashboard-card flex flex-col items-center gap-3 rounded-2xl px-6 py-14 text-center">
          <FiAlertCircle className="h-8 w-8" aria-hidden="true" />
          <p className="text-sm">Unable to load the invoice settings. Please refresh the page.</p>
        </div>
      </div>
    );
  }

  const set = (key, value) => setDraft((d) => ({ ...d, [key]: value }));

  async function save() {
    const layout = normalizeLayout(draft);
    setSaving(true);
    let res;
    try {
      const r = await fetch("/api/admin/orders/invoice-layout", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        body: JSON.stringify(Object.fromEntries(LAYOUT_FIELDS.map((f) => [`invoice_${f.key}`, layout[f.key]]))),
      });
      res = { ok: r.ok, status: r.status, data: await r.json().catch(() => null) };
    } catch {
      res = { ok: false, status: 0, data: null };
    }
    setSaving(false);
    if (!res.ok) {
      notify.error(errorText(res, "Unable to save the invoice settings."));
      return;
    }
    const stored = normalizeLayout(res.data, "invoice_");
    setSaved(stored);
    setDraft(stored);
    notify.success("Invoice settings saved.");
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="custom-font text-2xl sm:text-3xl">Invoice Settings</h1>
        <p className="showcase-muted text-sm">The print layout every invoice uses — preview, print, PDF and reprint.</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[22rem_minmax(0,1fr)] lg:items-start">
        <section className="dashboard-card flex flex-col gap-5 rounded-2xl p-5 sm:p-6 lg:sticky lg:top-24">
          <div className="flex items-center justify-between gap-3">
            <h2 className="custom-font text-lg">Invoice Print Settings</h2>
            {dirty && <span className="product-card__chip rounded-full px-2.5 py-0.5 text-xs">Unsaved</span>}
          </div>

          <div className="flex items-center justify-between text-sm">
            <span>Paper Size</span>
            <span className="font-medium">A4 (portrait)</span>
          </div>

          {LAYOUT_FIELDS.map((field) => (
            <LayoutControl key={field.key} field={field} value={draft[field.key]} onChange={(v) => set(field.key, v)} />
          ))}

          <div className="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              onClick={save}
              disabled={saving || !dirty}
              className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium"
            >
              <FiSave className="h-4 w-4" aria-hidden="true" />
              {saving ? "Saving…" : "Save Settings"}
            </button>
            <button
              type="button"
              onClick={() => setDraft(DEFAULT_LAYOUT)}
              disabled={saving || isDefault}
              className="auth-btn auth-btn--outline inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium"
            >
              <FiRotateCcw className="h-4 w-4" aria-hidden="true" />
              Reset to Default
            </button>
          </div>
          <p className="showcase-muted text-xs">
            Reset fills in the standard layout; click Save Settings to apply it. Sizes have limits that keep text
            readable and the QR code / barcode scannable.
          </p>
        </section>

        <section className="flex min-w-0 flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="custom-font text-lg">Live Preview</h2>
            {orderId && (
              <Link
                href={to(`/dashboard/CCE/orders/${orderId}/invoice`)}
                className="showcase-muted inline-flex items-center gap-1.5 text-sm hover:text-current"
              >
                Print / PDF this invoice (saved settings)
                <FiExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
              </Link>
            )}
          </div>
          {invoice ? (
            <A4Preview invoice={{ ...toInvoiceView(invoice), layout: normalizeLayout(draft) }} />
          ) : (
            <div className="dashboard-card rounded-2xl px-6 py-14 text-center text-sm">
              The preview uses your most recent order&apos;s invoice — there are no orders yet.
            </div>
          )}
          {invoice && (
            <p className="showcase-muted text-xs">
              Showing the invoice of order {invoice.order_number}. The grey area is the rest of the A4 sheet; the dashed
              line marks where a longer invoice continues on a new page.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
