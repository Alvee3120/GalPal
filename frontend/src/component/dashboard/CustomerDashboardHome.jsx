import Link from "next/link";
import { FiShoppingBag, FiUser } from "react-icons/fi";

// The customer's own /dashboard landing: a welcome, and their real order count (from the same MyOrderViewSet
// the "My Orders" page lists) rather than an invented stat.
export default function CustomerDashboardHome({ user, orderCount }) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="custom-font text-2xl sm:text-3xl">Welcome, {user.full_name}</h1>
        <p className="showcase-muted mt-1 text-sm">Here&apos;s a quick look at your account.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Link href="/dashboard/customer/orders" className="dashboard-card flex items-center gap-4 rounded-2xl p-5">
          <span className="dashboard-card__icon flex h-11 w-11 shrink-0 items-center justify-center rounded-full">
            <FiShoppingBag className="h-5 w-5" aria-hidden="true" />
          </span>
          <div>
            <p className="text-2xl font-semibold">{orderCount}</p>
            <p className="showcase-muted text-sm">{orderCount === 1 ? "Order" : "Orders"} placed</p>
          </div>
        </Link>

        <Link href="/dashboard/customer/account" className="dashboard-card flex items-center gap-4 rounded-2xl p-5">
          <span className="dashboard-card__icon flex h-11 w-11 shrink-0 items-center justify-center rounded-full">
            <FiUser className="h-5 w-5" aria-hidden="true" />
          </span>
          <div>
            <p className="text-sm font-semibold">My Account</p>
            <p className="showcase-muted text-sm">View and edit your details</p>
          </div>
        </Link>
      </div>
    </div>
  );
}
