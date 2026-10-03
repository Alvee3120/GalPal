import Link from "next/link";
import LegalPage from "@/component/shared/LegalPage";
import CmsPage, { cmsMetadata } from "@/component/content/CmsPage";
import { getContentPage } from "@/lib/content";
import { getCurrencySymbol } from "@/lib/siteSettings";
import formatPrice from "@/lib/formatPrice";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";

const FALLBACK_METADATA = {
  title: "Shipping Policy | GalPal",
  description: "Where GalPal delivers, what delivery costs and how long it takes.",
};

// The live delivery zones (Admin → Delivery Charges), so the charges stated here are always the real ones.
async function getZones() {
  try {
    const res = await fetch(`${API_BASE_URL}/shipping/zones/`, { next: { revalidate: 300 } });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : (data?.results ?? []);
  } catch {
    return [];
  }
}

export async function generateMetadata() {
  return cmsMetadata(await getContentPage("shipping-policy"), FALLBACK_METADATA);
}

// Admin → Content Pages can write this page ("shipping-policy"); until then it lists the live delivery zones.
export default async function ShippingPolicyPage() {
  const page = await getContentPage("shipping-policy");
  if (page) return <CmsPage page={page} />;
  const [zones, currencySymbol] = await Promise.all([getZones(), getCurrencySymbol()]);

  return (
    <LegalPage title="Shipping Policy" intro="We deliver across Bangladesh. This page explains what delivery costs and how your order reaches you.">
      <section>
        <h2>Delivery Charges</h2>
        {zones.length > 0 ? (
          <ul>
            {zones.map((zone) => (
              <li key={zone.id}>
                <strong>{zone.name}</strong>: {formatPrice(zone.charge, currencySymbol)}
                {zone.estimated_days ? `, usually ${zone.estimated_days}` : ""}
                {Number(zone.free_shipping_threshold) > 0 ? ` (free on orders of ${formatPrice(zone.free_shipping_threshold, currencySymbol)} or more)` : ""}
              </li>
            ))}
          </ul>
        ) : (
          <p>The delivery charge for your address is shown at checkout before you place your order.</p>
        )}
        <p>The exact charge for your address is always shown at checkout, before you confirm your order.</p>
      </section>

      <section>
        <h2>Order Processing</h2>
        <p>
          We confirm every order before sending it out. You can follow its progress from <Link href="/dashboard/customer/orders">My Orders</Link>{" "}
          or the order confirmation page.
        </p>
      </section>

      <section>
        <h2>Problems With a Delivery</h2>
        <p>
          If your parcel arrives damaged or something is missing, contact us as soon as possible. See our{" "}
          <Link href="/return-and-cancellation-policy">Return &amp; Cancellation Policy</Link> for how we handle it.
        </p>
      </section>
    </LegalPage>
  );
}
