"use client";

import { usePathname } from "next/navigation";

// The staff tools (orders, products, categories, brands, Notify Me, reviews, account) are one set of pages served at
// two addresses: /dashboard/CCE/… for Customer Care and /dashboard/admin/… for Admin (app/dashboard/admin/ re-exports
// the CCE pages behind an admin-only layout). Components write their links in the CCE form; `useStaffHref` points them
// at whichever section the viewer is actually in, so an admin never lands on a /CCE address.
export const CCE_BASE = "/dashboard/CCE";
export const ADMIN_BASE = "/dashboard/admin";

export function staffBase(pathname) {
  return pathname?.startsWith(ADMIN_BASE) ? ADMIN_BASE : CCE_BASE;
}

export function useStaffHref() {
  const base = staffBase(usePathname());
  return (href) => (href.startsWith(CCE_BASE) ? base + href.slice(CCE_BASE.length) : href);
}
