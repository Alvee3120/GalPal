import { backendFetch } from "@/lib/backendAuth";
import AddressesPageContent from "@/component/dashboard/AddressesPageContent";

export const metadata = { title: "My Addresses | GalPal" };

async function getInitialAddresses() {
  try {
    const res = await backendFetch("/account/addresses/");
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : (data.results ?? []);
  } catch {
    return [];
  }
}

export default async function CustomerAddressPage() {
  const addresses = await getInitialAddresses();
  return <AddressesPageContent initialAddresses={addresses} />;
}
