"use client";

import { useState } from "react";
import Link from "next/link";
import { FiArrowLeft, FiDownload, FiPrinter, FiSliders } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { downloadInvoicePdf, toInvoiceView, waitForInvoiceAssets } from "@/lib/invoice";
import { useStaffHref } from "@/lib/staffPaths";
import InvoiceTemplate from "./InvoiceTemplate";
import CustomizeInvoicePanel, { LayoutBadge } from "./CustomizeInvoicePanel";

// An invoice on screen: Print / Download PDF / Back, then the A4 preview. Print uses the browser's own print of the
// page (only the invoice sheet prints — see globals.css); Download fetches the backend-rendered PDF.
//   pdf  — { url, method?, body? } for the matching /api/.../invoice/pdf route
//   back — { href, label } (staff links in their /dashboard/CCE form; useStaffHref points an admin at /dashboard/admin)
//   reprint — staff view of an existing order: the print button reads "Reprint Invoice" (same stored invoice, nothing
//             is regenerated — same number, parcel ID and amounts)
//   customizeOrderId — staff only: adds "Customize This Invoice" (this invoice's own layout overrides). The invoice's
//             `layout` is already resolved by the backend (global settings + overrides), so print, reprint and the PDF
//             all use it as-is.
export default function InvoiceView({ data: initialData, pdf, back, reprint = false, customizeOrderId = null }) {
  const [data, setData] = useState(initialData);
  const [customizing, setCustomizing] = useState(false);
  const invoice = toInvoiceView(data);
  const custom = Object.keys(data.layout_overrides ?? {}).length > 0;
  const [downloading, setDownloading] = useState(false);
  const [preparingPrint, setPreparingPrint] = useState(false);
  const to = useStaffHref();

  const print = async () => {
    setPreparingPrint(true);
    await waitForInvoiceAssets();
    setPreparingPrint(false);
    window.print();
  };

  const download = async () => {
    setDownloading(true);
    const error = await downloadInvoicePdf(pdf, invoice.invoiceNumber);
    setDownloading(false);
    if (error) notify.error(error);
  };

  return (
    <div className="invoice-page flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {back ? (
          <Link href={to(back.href)} className="showcase-muted inline-flex items-center gap-1.5 text-sm hover:text-current">
            <FiArrowLeft className="h-4 w-4" aria-hidden="true" />
            {back.label}
          </Link>
        ) : (
          <span />
        )}
        <div className="flex flex-wrap items-center gap-2">
          {customizeOrderId && <LayoutBadge custom={custom} />}
          {customizeOrderId && (
            <button
              type="button"
              onClick={() => setCustomizing(true)}
              className="auth-btn auth-btn--outline inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium"
            >
              <FiSliders className="h-4 w-4" aria-hidden="true" />
              Customize This Invoice
            </button>
          )}
          <button
            type="button"
            onClick={print}
            disabled={preparingPrint}
            className="auth-btn auth-btn--outline inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium"
          >
            <FiPrinter className="h-4 w-4" aria-hidden="true" />
            {preparingPrint ? "Preparing…" : reprint ? "Reprint Invoice" : "Print Invoice"}
          </button>
          <button
            type="button"
            onClick={download}
            disabled={downloading}
            className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium"
          >
            <FiDownload className="h-4 w-4" aria-hidden="true" />
            {downloading ? "Preparing PDF…" : "Download PDF"}
          </button>
        </div>
      </div>

      <div className="invoice-preview">
        <InvoiceTemplate invoice={invoice} />
      </div>

      {/* Mounted only while open, so the page never holds a second invoice sheet (printing prints every sheet). */}
      {customizing && (
        <CustomizeInvoicePanel data={data} orderId={customizeOrderId} onClose={() => setCustomizing(false)} onSaved={setData} />
      )}
    </div>
  );
}
