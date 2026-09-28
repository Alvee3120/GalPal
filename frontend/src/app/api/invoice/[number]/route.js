import { relayInvoice } from "@/lib/invoiceProxy";

// Invoice data for one order number (see lib/invoice.js):
//   GET  → GET /orders/<number>/invoice/       the logged-in customer's OWN order (404 for anyone else's)
//   POST → POST /orders/track/invoice/          a guest: { phone } — checked (and throttled) like order tracking
export async function GET(request, { params }) {
  const { number } = await params;
  return relayInvoice(`/orders/${encodeURIComponent(number)}/invoice/`);
}

export async function POST(request, { params }) {
  const { number } = await params;
  const { phone = "" } = (await request.json().catch(() => null)) ?? {};
  return relayInvoice("/orders/track/invoice/", { method: "POST", body: JSON.stringify({ order_number: number, phone: String(phone) }) });
}
