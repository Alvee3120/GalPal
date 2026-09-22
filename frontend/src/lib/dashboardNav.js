import { BiHome } from "react-icons/bi";
import { FaMapLocationDot } from "react-icons/fa6";
import { FiGrid, FiShoppingBag, FiUser } from "react-icons/fi";

// Role -> sidebar links, from the authenticated user's real `role` (apps.accounts.models.User.Role: "customer",
// "admin", "cce" — see lib/currentUser.js). ONLY routes that actually exist are listed here: admin/CCE have no
// management pages built yet (a separate, larger effort), so today they get just the shared dashboard home.
export const DASHBOARD_NAV = {
  customer: [
    { label: "Home", href: "/", icon: BiHome },
    { label: "My Orders", href: "/dashboard/customer/orders", icon: FiShoppingBag },
    { label: "Address", href: "/dashboard/customer/address", icon: FaMapLocationDot },
    { label: "My Account", href: "/dashboard/customer/account", icon: FiUser },
  ],
  admin: [{ label: "Dashboard", href: "/dashboard", icon: FiGrid }],
  cce: [{ label: "Dashboard", href: "/dashboard", icon: FiGrid }],
};

export const ROLE_LABEL = { customer: "Customer", admin: "Admin", cce: "Customer Care" };

export function navFor(role) {
  return DASHBOARD_NAV[role] ?? [];
}
