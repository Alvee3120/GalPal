import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/currentUser";
import { backendFetch } from "@/lib/backendAuth";
import AccountForm from "@/component/dashboard/AccountForm";

export const metadata = { title: "My Account | GalPal" };

async function getAddresses() {
  try {
    const res = await backendFetch("/account/addresses/");
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : (data.results ?? []);
  } catch {
    return [];
  }
}

// The EXISTING account form/profile system (same /account/profile/ + /account/addresses/ endpoints the customer
// "My Account" page uses — role-agnostic) — no separate account system for CCE.
export default async function CceAccountPage() {
  const [profile, addresses] = await Promise.all([getCurrentUser(), getAddresses()]);
  if (!profile) redirect("/login");
  return (
    <div className="flex flex-col gap-6">
      <h1 className="custom-font text-2xl sm:text-3xl">My Account</h1>
      <AccountForm initialProfile={profile} addresses={addresses} />
    </div>
  );
}
