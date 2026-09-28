import { backendFetch } from "@/lib/backendAuth";
import InvoiceView from "@/component/invoice/InvoiceView";
import GuestInvoiceLookup from "@/component/invoice/GuestInvoiceLookup";

export const metadata = { title: "Invoice | GalPal", robots: { index: false, follow: false } };

// The logged-in customer's own order comes straight from GET /orders/<number>/invoice/ (backend-scoped to them).
// Anyone else — a guest after checkout, or a customer whose order was placed logged out — gets the phone check
// (GuestInvoiceLookup). A 401/404 here never reveals whether the order exists.
async function getOwnInvoice(number) {
  try {
    const res = await backendFetch(`/orders/${encodeURIComponent(number)}/invoice/`);
    return res.ok ? await res.json() : null;
  } catch (error) {
    console.error("Failed to load invoice:", error);
    return null;
  }
}

export default async function InvoicePage({ params }) {
  const { number } = await params;
  const data = await getOwnInvoice(number);
  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6">
      {data ? (
        <InvoiceView
          data={data}
          pdf={{ url: `/api/invoice/${encodeURIComponent(number)}/pdf` }}
          back={{ href: `/dashboard/customer/orders/${encodeURIComponent(number)}`, label: "Back to order" }}
        />
      ) : (
        <GuestInvoiceLookup number={number} />
      )}
    </main>
  );
}
