"use client";

import { useState } from "react";
import { notify } from "@/lib/notify";
import { messageFor } from "@/lib/apiError";
import ParcelCodes from "@/component/invoice/ParcelCodes";

// Parcel Information on Order Management's order detail: Admin/CCE type the courier's Parcel ID by hand and save it
// (POST /admin/orders/<id>/parcel/ — trimmed, validated and duplicate-checked backend-side). The QR code and barcode
// shown are the backend's, drawn from the SAVED value, so they always match what the invoice/PDF will print.
// Render with key={order.consignment_id} so the field resets to the saved value whenever it changes.
export default function ParcelPanel({ order, onSaved }) {
  const saved = order.consignment_id || "";
  const [value, setValue] = useState(saved);
  const [saving, setSaving] = useState(false);
  const trimmed = value.trim();

  async function save(event) {
    event.preventDefault();
    if (!trimmed) {
      notify.error("Enter the parcel ID.");
      return;
    }
    setSaving(true);
    try {
      const res = await fetch(`/api/admin/orders/${order.id}/parcel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ parcel_id: trimmed }),
        cache: "no-store",
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        notify.error(messageFor({ status: res.status, details: data?.error?.details }, "Unable to save the parcel ID."));
        return;
      }
      onSaved(data);
      notify.success("Parcel ID saved.");
    } catch {
      notify.error("Unable to save the parcel ID.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="dashboard-card rounded-2xl p-5 sm:p-6">
      <h2 className="custom-font text-lg">Parcel Information</h2>
      <form onSubmit={save} className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
        <label className="flex flex-col gap-1.5 text-sm">
          Parcel ID
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            maxLength={100}
            placeholder="e.g. DHK-2026-001245"
            autoComplete="off"
            spellCheck={false}
            className="checkout-input rounded-lg px-3 py-2.5"
          />
        </label>
        <button
          type="submit"
          disabled={saving || !trimmed || trimmed === saved}
          className="auth-btn auth-btn--primary rounded-full px-6 py-2.5 text-sm font-medium"
        >
          {saving ? "Saving…" : "Save Parcel ID"}
        </button>
      </form>

      {saved ? (
        <div className="mt-5 flex flex-col gap-3">
          <p className="text-sm">
            <span className="showcase-muted">Parcel ID:</span> <span className="font-semibold">{saved}</span>
          </p>
          <ParcelCodes id={saved} qrSvg={order.parcel_codes?.qr_svg} barcodeSvg={order.parcel_codes?.barcode_svg} />
        </div>
      ) : (
        <p className="showcase-muted mt-3 text-xs">No parcel ID yet — the QR code and barcode appear once one is saved.</p>
      )}
    </section>
  );
}
