import { cookies } from "next/headers";
import { backendFetch } from "@/lib/backendAuth";

// Proxy to POST /checkout/lead/ (apps.care): remembers a checkout once the shopper has typed a name and phone, so
// Admin can follow up if no order follows. The cart comes from the login or the guest cart cookie, as at checkout.
export async function POST(request) {
  const { name, phone, email, district } = (await request.json().catch(() => null)) ?? {};
  const cartToken = (await cookies()).get("cart_token")?.value;
  try {
    await backendFetch("/checkout/lead/", {
      method: "POST",
      body: JSON.stringify({ name, phone, email, district }),
      headers: cartToken ? { "X-Cart-Token": cartToken } : {},
    });
  } catch {
    // never matters to the shopper
  }
  return new Response(null, { status: 204 });
}
