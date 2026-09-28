import { notFound } from "next/navigation";
import { backendFetch } from "@/lib/backendAuth";
import InvoiceView from "@/component/invoice/InvoiceView";

export const metadata = { title: "Invoice | GalPal" };

async function getInvoice(id) {
  try {
    const res = await backendFetch(`/admin/orders/${encodeURIComponent(id)}/invoice/`);
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`Admin invoice API responded ${res.status}`);
    return await res.json();
  } catch (error) {
    console.error("Failed to load invoice:", error);
    return null;
  }
}

// Staff view/reprint of an order's invoice (GET /admin/orders/<id>/invoice/, IsAdminOrCCE — enforced backend-side).
export default async function StaffInvoicePage({ params }) {
  const { id } = await params;
  const data = await getInvoice(id);
  if (!data) notFound();
  return (
    <InvoiceView
      data={data}
      pdf={{ url: `/api/admin/orders/${encodeURIComponent(id)}/invoice/pdf` }}
      back={{ href: `/dashboard/CCE/orders/${encodeURIComponent(id)}`, label: "Back to order" }}
      reprint
      customizeOrderId={id}
    />
  );
}
