import { relayInvoice } from "@/lib/invoiceProxy";

// The same two ways in as ../route.js, answered with the backend-rendered A4 PDF.
export async function GET(request, { params }) {
  const { number } = await params;
  return relayInvoice(`/orders/${encodeURIComponent(number)}/invoice/pdf/`);
}

export async function POST(request, { params }) {
  const { number } = await params;
  const { phone = "" } = (await request.json().catch(() => null)) ?? {};
  return relayInvoice("/orders/track/invoice/pdf/", { method: "POST", body: JSON.stringify({ order_number: number, phone: String(phone) }) });
}
