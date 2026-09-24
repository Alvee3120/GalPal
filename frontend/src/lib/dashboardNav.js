import { BiHome } from "react-icons/bi";
import { FaMapLocationDot } from "react-icons/fa6";
import { FiAward, FiBell, FiGrid, FiLayers, FiPackage, FiPlusCircle, FiShoppingBag, FiUser } from "react-icons/fi";

// Role -> sidebar links, from the authenticated user's real `role` (apps.accounts.models.User.Role: "customer",
// "admin", "cce" — see lib/currentUser.js). ONLY routes that actually exist are listed here: admin has no
// management pages built yet (a separate, larger effort), so it still gets just the shared dashboard home. CCE's
// "Dashboard" is the order-management list (app/dashboard/page.js branches on role); "My Orders"/"My Account" are
// the CCE account's own orders/profile (apps.orders.views.MyOrderViewSet / /account/profile/ — the same
// customer-facing endpoints, just mounted under /dashboard/CCE/... since /dashboard/customer/... is customer-only;
// "Products" is Product Management over the catalog admin API's CCE-permitted actions (IsCatalogStaff)
// — the route segment is uppercase because that's the actual casing of app/dashboard/CCE/ on disk).
export const DASHBOARD_NAV = {
  customer: [
    { label: "Home", href: "/", icon: BiHome },
    { label: "My Orders", href: "/dashboard/customer/orders", icon: FiShoppingBag },
    { label: "Address", href: "/dashboard/customer/address", icon: FaMapLocationDot },
    { label: "My Account", href: "/dashboard/customer/account", icon: FiUser },
  ],
  admin: [{ label: "Dashboard", href: "/dashboard", icon: FiGrid }],
  cce: [
    { label: "Dashboard", href: "/dashboard", icon: FiGrid },
    { label: "Add Order", href: "/dashboard/CCE/orders/new", icon: FiPlusCircle },
    { label: "Products", href: "/dashboard/CCE/products", icon: FiPackage },
    { label: "Categories", href: "/dashboard/CCE/categories", icon: FiLayers },
    { label: "Brands", href: "/dashboard/CCE/brands", icon: FiAward },
    { label: "Notify Me", href: "/dashboard/CCE/stock-notifications", icon: FiBell },
    { label: "My Orders", href: "/dashboard/CCE/orders/mine", icon: FiShoppingBag },
    { label: "My Account", href: "/dashboard/CCE/account", icon: FiUser },
  ],
};

export const ROLE_LABEL = { customer: "Customer", admin: "Admin", cce: "Customer Care" };

export function navFor(role) {
  return DASHBOARD_NAV[role] ?? [];
}
