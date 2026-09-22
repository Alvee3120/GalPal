"use client";

import { useState } from "react";
import Link from "next/link";
import { FiSearch } from "react-icons/fi";
import { notify } from "@/lib/notify";
import formatPrice from "@/lib/formatPrice";
import { ORDER_SOURCE_LABEL, PAYMENT_METHOD_LABEL, STATUS_LABEL, formatOrderDate } from "@/lib/orderStatus";

const STATUS_OPTIONS = ["", "pending", "confirmed", "processing", "shipped", "delivered", "cancelled", "returned", "failed"];

// Order Management: the customer orders a CCE/Admin is authorized to work, via the EXISTING /admin/orders/ API
// (apps.orders.views_admin.AdminOrderViewSet, permission IsAdminOrCCE — enforced backend-side; this page only
// renders what that endpoint returns). Distinct from "My Orders", which is the CCE account's own orders via the
// customer-facing MyOrderViewSet — see component/dashboard/OrdersList.jsx and lib/dashboardNav.js's comment.
export default function CceOrderManagement({ initialOrders, initialCount, currencySymbol }) {
  const [orders, setOrders] = useState(initialOrders);
  const [count, setCount] = useState(initialCount);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  async function runSearch(nextSearch, nextStatus) {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page_size: "30" });
      if (nextSearch) params.set("search", nextSearch);
      if (nextStatus) params.set("status", nextStatus);
      const res = await fetch(`/api/admin/orders?${params.toString()}`, { cache: "no-store" });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        notify.error("Unable to load orders. Please try again.");
        return;
      }
      setOrders(data.results ?? []);
      setCount(data.count ?? 0);
    } catch {
      notify.error("Unable to load orders. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    runSearch(search, status);
  }

  function handleStatusChange(e) {
    const next = e.target.value;
    setStatus(next);
    runSearch(search, next);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="custom-font text-2xl sm:text-3xl">Order Management</h1>
        <p className="showcase-muted text-sm">{count} order{count === 1 ? "" : "s"}</p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-0 flex-1">
          <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search order no., customer name, phone or email..."
            className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
          />
        </div>
        <select value={status} onChange={handleStatusChange} className="checkout-input rounded-lg px-3 py-2.5 text-sm">
          {STATUS_OPTIONS.map((s) => (
            <option key={s || "all"} value={s}>
              {s ? STATUS_LABEL[s] : "All Statuses"}
            </option>
          ))}
        </select>
        <button type="submit" disabled={loading} className="auth-btn auth-btn--primary rounded-full px-5 py-2.5 text-sm font-medium">
          {loading ? "Searching..." : "Search"}
        </button>
      </form>

      {orders.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-2 rounded-2xl px-6 py-14 text-center">
          <p className="custom-font text-xl">No orders found</p>
          <p className="showcase-muted text-sm">Try a different search or status filter.</p>
        </div>
      ) : (
        <ul className="flex flex-col gap-3">
          {orders.map((order) => (
            <li key={order.id} className="dashboard-card rounded-2xl p-4 sm:p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">
                    #{order.number} &middot; {order.customer_name}
                  </p>
                  <p className="showcase-muted text-xs">
                    {order.phone} &bull; {order.district} &bull; {formatOrderDate(order.created_at)}
                  </p>
                </div>
                <span className="product-card__chip rounded-full px-3 py-1 text-xs font-medium">{STATUS_LABEL[order.status] ?? order.status}</span>
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
                <span className="showcase-muted">{order.item_count} item{order.item_count === 1 ? "" : "s"}</span>
                <span className="showcase-muted">{PAYMENT_METHOD_LABEL[order.payment_method] ?? order.payment_method}</span>
                <span className="showcase-muted">{ORDER_SOURCE_LABEL[order.source] ?? order.source}</span>
                {order.is_manual && <span className="showcase-muted">Manual order{order.created_by ? ` by ${order.created_by.full_name}` : ""}</span>}
              </div>

              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <p className="font-semibold">{formatPrice(order.grand_total, currencySymbol)}</p>
                <Link href={`/dashboard/CCE/orders/${order.id}`} className="auth-btn auth-btn--primary rounded-full px-5 py-2 text-xs font-medium">
                  Manage Order
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
