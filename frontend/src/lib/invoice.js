import formatPrice from "@/lib/formatPrice";

// Invoice data flows one way: backend invoice (apps.orders.invoice.build_invoice — the order's own stored snapshot,
// the same data the PDF is built from) → toInvoiceView() here → <InvoiceTemplate>. The template never computes or
// fetches anything; every number on it was decided by the backend when the order was placed/paid.

const joined = (parts, sep = ", ") => parts.filter(Boolean).join(sep);

export function toInvoiceView(data) {
  const symbol = data.store?.currency_symbol || "৳";
  const money = (value) => formatPrice(value, symbol);
  const customer = data.customer ?? {};

  const totals = [{ label: "Subtotal", value: money(data.subtotal) }];
  if (Number(data.product_discount) > 0) {
    totals.push({ label: "Product discount (in prices)", value: `− ${money(data.product_discount)}` });
  }
  if (Number(data.coupon_discount) > 0) {
    totals.push({ label: data.coupon_code ? `Coupon discount (${data.coupon_code})` : "Coupon discount", value: `− ${money(data.coupon_discount)}` });
  }
  totals.push({ label: "Delivery charge", value: Number(data.delivery_charge) > 0 ? money(data.delivery_charge) : "Free" });
  if (Number(data.tax_amount) > 0) totals.push({ label: `Tax (${Number(data.tax_percent)}%)`, value: money(data.tax_amount) });

  return {
    store: {
      name: data.store?.name || "",
      // Under the logo: phone and email first, then the address (all from Site Settings).
      lines: [
        data.store?.phone && `Phone: ${data.store.phone}`,
        data.store?.email && `Email: ${data.store.email}`,
        data.store?.address,
      ].filter(Boolean),
    },
    invoiceNumber: data.invoice_number,
    orderNumber: data.order_number,
    date: data.date,
    time: data.time,
    billTo: {
      name: customer.name,
      lines: [
        customer.phone,
        customer.email,
        customer.address,
        joined([customer.area, customer.city, customer.division]),
        customer.postal_code && `Postal code: ${customer.postal_code}`,
        data.delivery_zone && `Delivery zone: ${data.delivery_zone}`,
      ].filter(Boolean),
    },
    payment: { method: data.payment_method, status: data.payment_status, reference: data.payment_reference || "" },
    items: (data.items ?? []).map((item, index) => ({
      key: `${index}-${item.sku || item.name}`,
      name: item.name,
      meta: joined([item.variant, item.sku && `SKU ${item.sku}`], " · "),
      quantity: item.quantity,
      price: money(item.unit_price),
      discount: Number(item.discount) > 0 ? money(item.discount) : "—",
      total: money(item.total),
    })),
    totals,
    grandTotal: money(data.total),
    paid: money(data.paid),
    due: money(data.due),
    parcel: data.parcel_id
      ? { id: data.parcel_id, courier: data.courier, qrSvg: data.parcel_qr_svg, barcodeSvg: data.parcel_barcode_svg }
      : null,
    note: data.note || "",
    layout: data.layout,  // the saved print layout (Site Settings) — see lib/invoiceLayout.js
  };
}

// Client side, before window.print(): wait until the invoice's fonts (the site's Montserrat weights + Honacu) and its
// logo are actually loaded, so print never captures a fallback font or an empty logo box. The QR code and barcode are
// inline SVG, ready as soon as they're rendered. Never rejects — a font that genuinely fails just prints in fallback.
const INVOICE_FONTS = ["400 1em Montserrat", "600 1em Montserrat", "700 1em Montserrat", "400 1em Honacu"];

export async function waitForInvoiceAssets() {
  if (document.fonts) {
    await Promise.all(INVOICE_FONTS.map((font) => document.fonts.load(font).catch(() => null)));
    await document.fonts.ready;
  }
  const images = [...document.querySelectorAll(".invoice-sheet img")];
  await Promise.all(images.map((img) => img.decode().catch(() => null)));
}

// Client side: fetch one of the /api/.../invoice/pdf routes and save the file it returns (the server-rendered PDF —
// real text, vector codes; nothing here screenshots the page). Resolves to an error message, or null on success.
export async function downloadInvoicePdf({ url, method = "GET", body }, fallbackName) {
  let res;
  try {
    res = await fetch(url, {
      method,
      cache: "no-store",
      ...(body ? { body: JSON.stringify(body), headers: { "Content-Type": "application/json" } } : {}),
    });
  } catch {
    return "We couldn't reach the server. Please try again.";
  }
  if (!res.ok || !(res.headers.get("Content-Type") || "").includes("application/pdf")) {
    const data = await res.json().catch(() => null);
    return data?.error?.message || "Unable to download the invoice. Please try again.";
  }
  const blob = await res.blob();
  const name = /filename="?([^";]+)"?/.exec(res.headers.get("Content-Disposition") || "")?.[1] || `${fallbackName}.pdf`;
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
  return null;
}
