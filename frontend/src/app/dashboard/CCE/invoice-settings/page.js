import { backendFetch } from "@/lib/backendAuth";
import { normalizeLayout } from "@/lib/invoiceLayout";
import InvoiceLayoutSettings from "@/component/dashboard/InvoiceLayoutSettings";

export const metadata = { title: "Invoice Settings | GalPal" };

async function getJson(path) {
  try {
    const res = await backendFetch(path);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

// Invoice Print Settings for Admin and CCE (served at /dashboard/CCE/… and, re-exported, /dashboard/admin/…). The layout
// lives in Site Settings but is read and changed through its own endpoint, GET/PATCH /admin/orders/invoice-layout/
// (IsAdminOrCCE, layout fields only — the rest of Site Settings stays Admin-only). The preview shows the most recent
// real order's invoice through the same InvoiceTemplate every invoice uses.
export default async function InvoiceSettingsPage() {
  const [layout, latest] = await Promise.all([
    getJson("/admin/orders/invoice-layout/"),
    getJson("/admin/orders/?page_size=1&ordering=-created_at"),
  ]);
  const order = latest?.results?.[0] ?? null;
  const invoice = order ? await getJson(`/admin/orders/${order.id}/invoice/`) : null;
  return (
    <InvoiceLayoutSettings
      savedLayout={layout ? normalizeLayout(layout, "invoice_") : null}
      invoice={invoice}
      orderId={order?.id ?? null}
    />
  );
}
