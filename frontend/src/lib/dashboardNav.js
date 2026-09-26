import { BiHome } from "react-icons/bi";
import { FaMapLocationDot } from "react-icons/fa6";
import { FiAward, FiBell, FiClipboard, FiGrid, FiLayers, FiPackage, FiPlusCircle, FiShoppingBag, FiStar, FiTag, FiTruck, FiUser, FiUsers, FiVideo } from "react-icons/fi";

// Role -> sidebar links, from the authenticated user's real `role` (apps.accounts.models.User.Role: "customer",
// "admin", "cce" — see lib/currentUser.js). ONLY routes that actually exist are listed here. Admin shares
// the staff tools, served at /dashboard/admin/ (lib/staffPaths.js) (every one of those backend endpoints already allows Admin); its /dashboard
// is the full ecommerce overview. CCE's
// "Dashboard" is the analytics overview and "Orders" the order-management list; "My Orders"/"My Account" are
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
  admin: [
    { label: "Dashboard", href: "/dashboard", icon: FiGrid },
    { label: "Orders", href: "/dashboard/admin/orders", icon: FiClipboard },
    { label: "Products", href: "/dashboard/admin/products", icon: FiPackage },
    { label: "Categories", href: "/dashboard/admin/categories", icon: FiLayers },
    { label: "Brands", href: "/dashboard/admin/brands", icon: FiAward },
    { label: "Notify Me", href: "/dashboard/admin/stock-notifications", icon: FiBell },
    { label: "Reviews", href: "/dashboard/admin/reviews", icon: FiStar },
    { label: "Video Cards", href: "/dashboard/admin/video-cards", icon: FiVideo },
    { label: "Users", href: "/dashboard/admin/users", icon: FiUsers },
    { label: "Coupons", href: "/dashboard/admin/coupons", icon: FiTag },
    { label: "Delivery Charges", href: "/dashboard/admin/delivery-charges", icon: FiTruck },
    { label: "My Account", href: "/dashboard/admin/account", icon: FiUser },
  ],
  cce: [
    { label: "Dashboard", href: "/dashboard", icon: FiGrid },
    { label: "Orders", href: "/dashboard/CCE/orders", icon: FiClipboard },
    { label: "Add Order", href: "/dashboard/CCE/orders/new", icon: FiPlusCircle },
    { label: "Products", href: "/dashboard/CCE/products", icon: FiPackage },
    { label: "Categories", href: "/dashboard/CCE/categories", icon: FiLayers },
    { label: "Brands", href: "/dashboard/CCE/brands", icon: FiAward },
    { label: "Notify Me", href: "/dashboard/CCE/stock-notifications", icon: FiBell },
    { label: "Reviews", href: "/dashboard/CCE/reviews", icon: FiStar },
    { label: "Video Cards", href: "/dashboard/CCE/video-cards", icon: FiVideo },
    { label: "My Orders", href: "/dashboard/CCE/orders/mine", icon: FiShoppingBag },
    { label: "My Account", href: "/dashboard/CCE/account", icon: FiUser },
  ],
};

export const ROLE_LABEL = { customer: "Customer", admin: "Admin", cce: "Customer Care" };

export function navFor(role) {
  return DASHBOARD_NAV[role] ?? [];
}
