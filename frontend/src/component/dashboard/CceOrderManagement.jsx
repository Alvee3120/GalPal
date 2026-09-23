"use client";

import { useState } from "react";
import Link from "next/link";
import { FiSearch } from "react-icons/fi";
import { notify } from "@/lib/notify";
import formatPrice from "@/lib/formatPrice";
import { ORDER_SOURCE_LABEL, PAYMENT_METHOD_LABEL, STATUS_LABEL, formatOrderDate } from "@/lib/orderStatus";
import OrderStatusDropdown from "./OrderStatusDropdown";
import OrderDateRangePicker, { formatCalendarDate } from "./OrderDateRangePicker";
import DashboardPagination from "./DashboardPagination";

// Matches OrderStatusDropdown's VISIBLE_STATUSES exactly — the same status vocabulary everywhere in this UI.
const STATUS_OPTIONS = ["", "confirmed", "processing", "shipped", "delivered", "cancelled", "returned"];
const PAGE_SIZE = 10;

// Order Management: the customer orders a CCE/Admin is authorized to work, via the EXISTING /admin/orders/ API
// (apps.orders.views_admin.AdminOrderViewSet, permission IsAdminOrCCE — enforced backend-side; this page only
// renders what that endpoint returns). Distinct from "My Orders", which is the CCE account's own orders via the
// customer-facing MyOrderViewSet — see component/dashboard/OrdersList.jsx and lib/dashboardNav.js's comment.
//
// Search/status filters were already plain client-side state (no URL query params) before this page had a date
// filter, so the date filter follows that same pattern rather than bolting on a one-off URL-synced filter next to
// two that aren't — see apps.orders.filters.OrderFilter's `date_from`/`date_to`, which this reuses as-is (already
// inclusive, already resolved against the project's actual timezone — see that filter's own comment).
export default function CceOrderManagement({ initialOrders, initialCount, currencySymbol }) {
  const [orders, setOrders] = useState(initialOrders);
  const [count, setCount] = useState(initialCount);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [dateRange, setDateRange] = useState(null); // { start: "YYYY-MM-DD", end: "YYYY-MM-DD" } | null
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  async function runSearch(nextSearch, nextStatus, nextDateRange, nextPage) {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page_size: String(PAGE_SIZE), page: String(nextPage) });
      if (nextSearch) params.set("search", nextSearch);
      if (nextStatus) params.set("status", nextStatus);
      if (nextDateRange) {
        params.set("date_from", nextDateRange.start);
        params.set("date_to", nextDateRange.end);
      }
      const res = await fetch(`/api/admin/orders?${params.toString()}`, { cache: "no-store" });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        notify.error("Unable to load orders. Please try again.");
        return;
      }
      setOrders(data.results ?? []);
      setCount(data.count ?? 0);
      setPage(nextPage);
    } catch {
      notify.error("Unable to load orders. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    runSearch(search, status, dateRange, 1);
  }

  function handleStatusChange(e) {
    const next = e.target.value;
    setStatus(next);
    runSearch(search, next, dateRange, 1);
  }

  function handleDateChange(next) {
    setDateRange(next);
    runSearch(search, status, next, 1);
  }

  function handlePageChange(nextPage) {
    if (nextPage === page) return;
    runSearch(search, status, dateRange, nextPage);
  }

  function handleOrderChanged(updated) {
    setOrders((list) => list.map((o) => (o.id === updated.id ? { ...o, status: updated.status, allowed_transitions: updated.allowed_transitions } : o)));
  }

  const emptyMessage = !dateRange
    ? "Try a different search or status filter."
    : dateRange.start === dateRange.end
      ? `No orders found for ${formatCalendarDate(dateRange.start)}.`
      : `No orders found for the selected date range.`;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="custom-font text-2xl sm:text-3xl">Order Management</h1>
        <p className="showcase-muted text-sm">{count} order{count === 1 ? "" : "s"}</p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
        <div className="relative min-w-0 flex-1">
          <label htmlFor="om-search" className="mb-1.5 block text-sm font-medium">
            Search
          </label>
          <div className="relative">
            <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
            <input
              id="om-search"
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search order no., customer name, phone or email..."
              className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
            />
          </div>
        </div>

        <div className="flex items-end gap-2">
          <div>
            <span className="mb-1.5 block text-sm font-medium">Order Date</span>
            <OrderDateRangePicker value={dateRange} onChange={handleDateChange} />
          </div>
        </div>

        <div>
          <label htmlFor="om-status" className="mb-1.5 block text-sm font-medium">
            Status
          </label>
          <select id="om-status" value={status} onChange={handleStatusChange} className="checkout-input rounded-lg px-3 py-2.5 text-sm">
            {STATUS_OPTIONS.map((s) => (
              <option key={s || "all"} value={s}>
                {s ? STATUS_LABEL[s] : "All Status"}
              </option>
            ))}
          </select>
        </div>

        <button type="submit" disabled={loading} className="auth-btn auth-btn--primary rounded-full px-5 py-2.5 text-sm font-medium">
          {loading ? "Searching..." : "Search"}
        </button>
      </form>

      {orders.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-2 rounded-2xl px-6 py-14 text-center">
          <p className="custom-font text-xl">No orders found</p>
          <p className="showcase-muted text-sm">{emptyMessage}</p>
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
                <OrderStatusDropdown orderId={order.id} status={order.status} onChanged={handleOrderChanged} className="w-40 shrink-0" />
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

      <DashboardPagination page={page} totalPages={totalPages} onPageChange={handlePageChange} disabled={loading} />
    </div>
  );
}
