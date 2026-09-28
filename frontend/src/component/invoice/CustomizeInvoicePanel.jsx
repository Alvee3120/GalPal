"use client";

import { useState } from "react";
import { FiRotateCcw } from "react-icons/fi";
import Modal from "@/component/shared/Modal";
import { notify } from "@/lib/notify";
import { errorText } from "@/lib/productAdmin";
import { toInvoiceView } from "@/lib/invoice";
import { LAYOUT_FIELDS, layoutOverrides, resolveInvoiceLayout } from "@/lib/invoiceLayout";
import { A4Preview, LayoutControl } from "./LayoutControls";

// "Customize This Invoice": this ONE invoice's print layout, on top of the global Invoice Settings. Opens on the
// currently resolved values (global + this invoice's saved overrides); Apply saves only the values that differ from
// the global settings (PUT /admin/orders/<id>/invoice/layout/), Reset to Global removes them (DELETE). Never touches
// the global settings or anything else on the order. The preview is the same InvoiceTemplate every invoice uses.
async function layoutRequest(orderId, method, body) {
  try {
    const r = await fetch(`/api/admin/orders/${orderId}/invoice/layout`, {
      method,
      cache: "no-store",
      ...(body ? { body: JSON.stringify(body), headers: { "Content-Type": "application/json" } } : {}),
    });
    return { ok: r.ok, status: r.status, data: await r.json().catch(() => null) };
  } catch {
    return { ok: false, status: 0, data: null };
  }
}

export default function CustomizeInvoicePanel({ data, orderId, onClose, onSaved }) {
  const globalLayout = data.layout_global;
  const [draft, setDraft] = useState(() => resolveInvoiceLayout(globalLayout, data.layout_overrides));
  const [busy, setBusy] = useState(false);
  const changes = layoutOverrides(draft, globalLayout);
  const custom = Object.keys(changes).length > 0;

  async function apply() {
    setBusy(true);
    const res = custom ? await layoutRequest(orderId, "PUT", { overrides: changes }) : await layoutRequest(orderId, "DELETE");
    setBusy(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to save this invoice's layout."));
    onSaved(res.data);
    notify.success(custom ? "Custom layout applied to this invoice." : "This invoice uses the global settings.");
    onClose();
  }

  async function resetToGlobal() {
    setBusy(true);
    const res = await layoutRequest(orderId, "DELETE");
    setBusy(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to reset this invoice's layout."));
    onSaved(res.data);
    setDraft(resolveInvoiceLayout(res.data.layout_global, {}));
    notify.success("This invoice now uses the global settings.");
  }

  return (
    <Modal open title="Customize This Invoice" onClose={() => !busy && onClose()} xl>
      <div className="grid gap-5 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <p className="showcase-muted text-sm">Adjust the layout for this invoice only.</p>
            <LayoutBadge custom={custom} />
          </div>

          {LAYOUT_FIELDS.map((field) => (
            <LayoutControl key={field.key} field={field} value={draft[field.key]} onChange={(v) => setDraft((d) => ({ ...d, [field.key]: v }))} />
          ))}

          <div className="flex flex-wrap items-center gap-2 pt-1">
            <button
              type="button"
              onClick={resetToGlobal}
              disabled={busy || (!custom && !Object.keys(data.layout_overrides ?? {}).length)}
              className="auth-btn auth-btn--outline inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium"
            >
              <FiRotateCcw className="h-4 w-4" aria-hidden="true" />
              Reset to Global
            </button>
            <button type="button" onClick={onClose} disabled={busy} className="auth-btn auth-btn--outline rounded-full px-4 py-2 text-sm font-medium">
              Cancel
            </button>
            <button type="button" onClick={apply} disabled={busy} className="auth-btn auth-btn--primary rounded-full px-5 py-2 text-sm font-medium">
              {busy ? "Saving…" : "Apply"}
            </button>
          </div>
          <p className="showcase-muted text-xs">
            Only the values you change are saved for this invoice; everything else keeps following the global Invoice
            Settings.
          </p>
        </div>

        <div className="min-w-0">
          <A4Preview invoice={{ ...toInvoiceView(data), layout: draft }} />
        </div>
      </div>
    </Modal>
  );
}

export function LayoutBadge({ custom }) {
  return (
    <span className="product-card__chip w-fit rounded-full px-2.5 py-0.5 text-xs font-medium">
      {custom ? "Custom Layout Active" : "Using Global Settings"}
    </span>
  );
}
