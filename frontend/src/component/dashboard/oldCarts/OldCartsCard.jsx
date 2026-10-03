import Link from "next/link";
import { FiArrowRight, FiShoppingCart } from "react-icons/fi";

// "Customers with Old Carts" on the Admin and CCE dashboards. The number comes from the backend (GET
// /admin/orders/old-carts/ — customers with a cart item kept more than 6 hours), fetched separately from the
// dashboard's date range: cart age has nothing to do with the sales period. `href` is the viewer's own section.
export default function OldCartsCard({ count, href }) {
  if (count === null || count === undefined) return null;
  return (
    <section className="dashboard-card flex flex-wrap items-center justify-between gap-4 rounded-2xl p-5 sm:p-6" aria-label="Old carts">
      <div className="flex items-center gap-4">
        <span className="old-carts__icon flex h-11 w-11 shrink-0 items-center justify-center rounded-full">
          <FiShoppingCart className="h-5 w-5" aria-hidden="true" />
        </span>
        <div>
          <p className="showcase-muted text-sm">Customers with Old Carts</p>
          <p className="text-2xl font-semibold">{count}</p>
          <p className="showcase-muted text-xs">
            {count === 1 ? "1 customer has" : `${count} customers have`} cart items older than 6 hours.
          </p>
        </div>
      </div>
      <Link href={href} className="auth-btn auth-btn--outline inline-flex items-center gap-2 rounded-full px-5 py-2 text-sm font-medium">
        View Old Carts
        <FiArrowRight className="h-4 w-4" aria-hidden="true" />
      </Link>
    </section>
  );
}
