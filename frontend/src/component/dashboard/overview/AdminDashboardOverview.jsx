"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  FiAlertCircle,
  FiArrowDownRight,
  FiArrowUpRight,
  FiCalendar,
  FiCheck,
  FiChevronDown,
  FiPackage,
  FiRefreshCw,
  FiShoppingBag,
  FiUserPlus,
} from "react-icons/fi";
import { TbCurrencyTaka } from "react-icons/tb";
import { notify } from "@/lib/notify";
import formatPrice from "@/lib/formatPrice";
import { STATUS_LABEL, formatOrderDate } from "@/lib/orderStatus";
import { GRANULARITY_WORD, compactMoney, compactNumber } from "@/lib/dashboardFormat";
import { DEFAULT_PRESET, RANGE_PRESETS, formatCalendarDate, rangeLabel, rangeToQuery, todayIso } from "@/lib/dashboardRange";
import ProductImage from "@/component/shared/ProductImage";
import OrderDateRangePicker from "../OrderDateRangePicker";
import TimeSeriesChart from "./TimeSeriesChart";
import StatusDonut from "./StatusDonut";

const STATUS_ORDER = ["pending", "confirmed", "processing", "shipped", "delivered", "cancelled", "returned", "failed"];

// --- pieces ---------------------------------------------------------------------------------------------------------

function Delta({ change }) {
  if (change === null || change === undefined) return <span className="showcase-muted text-xs">No earlier data to compare</span>;
  const up = change > 0;
  const flat = change === 0;
  const Icon = up ? FiArrowUpRight : FiArrowDownRight;
  return (
    <span className="flex items-center gap-1.5 text-xs">
      <span className={`inline-flex items-center gap-0.5 font-semibold ${flat ? "" : up ? "trend-up" : "trend-down"}`}>
        {!flat && <Icon className="h-3.5 w-3.5" aria-hidden="true" />}
        {Math.abs(change).toLocaleString("en-US", { maximumFractionDigits: 1 })}%
      </span>
      <span className="showcase-muted">vs previous period</span>
    </span>
  );
}

function StatCard({ label, value, fullValue, icon: Icon, footer, loading }) {
  return (
    <div className="dashboard-card flex min-w-0 items-start gap-3 rounded-2xl p-5">
      <span className="dashboard-card__icon flex h-10 w-10 shrink-0 items-center justify-center rounded-xl">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="showcase-muted text-sm">{label}</p>
        {loading ? (
          <div className="product-skeleton__line mt-2 h-7 w-20 animate-pulse rounded-lg" />
        ) : (
          <p className="mt-1 truncate text-2xl font-semibold tabular-nums" title={fullValue}>
            {value}
          </p>
        )}
        <div className="mt-2 min-h-4">{!loading && footer}</div>
      </div>
    </div>
  );
}

function Panel({ title, subtitle, action, children, className = "" }) {
  return (
    <section className={`dashboard-card flex min-w-0 flex-col gap-4 rounded-2xl p-5 sm:p-6 ${className}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="custom-font text-lg">{title}</h2>
          {subtitle && <p className="showcase-muted text-xs">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function ViewAll({ href, children = "View All" }) {
  return (
    <Link href={href} className="auth-btn auth-btn--outline shrink-0 rounded-full px-3 py-1 text-xs font-medium">
      {children}
    </Link>
  );
}

function StatusPill({ status }) {
  return (
    <span className="order-status order-status--pill rounded-full px-2.5 py-0.5 text-xs font-medium" data-status={status}>
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

// The one date range for the whole dashboard: a trigger showing the range, a menu of presets, and "Custom Range"
// which reveals the existing date picker (OrderDateRangePicker) beside it.
function RangeFilter({ range, onChange, disabled }) {
  const [open, setOpen] = useState(false);
  const [custom, setCustom] = useState(range.preset === "custom");
  const rootRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const close = (e) => !rootRef.current?.contains(e.target) && setOpen(false);
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const presetLabel = range.preset === "custom" ? "Custom Range" : RANGE_PRESETS.find((p) => p.key === range.preset)?.label;

  return (
    <div className="flex flex-wrap items-center justify-end gap-2">
      {custom && (
        <OrderDateRangePicker
          value={range.preset === "custom" ? { start: range.start, end: range.end } : null}
          onChange={(value) => {
            if (value) return onChange({ preset: "custom", start: value.start, end: value.end });
            // Cleared (the picker's ✕): drop the custom range and go back to the default period.
            setCustom(false);
            const fallback = RANGE_PRESETS.find((p) => p.key === DEFAULT_PRESET);
            onChange({ preset: fallback.key, ...fallback.range(todayIso()) });
          }}
        />
      )}
      <div ref={rootRef} className="relative">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          disabled={disabled}
          aria-haspopup="menu"
          aria-expanded={open}
          className="checkout-input flex items-center gap-2 rounded-lg px-3 py-2.5 text-left text-sm disabled:opacity-70"
        >
          <FiCalendar className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span className="font-medium">{presetLabel}</span>
          <span className="showcase-muted hidden sm:inline">· {rangeLabel(range)}</span>
          <FiChevronDown className={`h-4 w-4 shrink-0 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden="true" />
        </button>
        {open && (
          <ul role="menu" className="shop-sort__menu absolute right-0 top-full z-50 mt-1.5 w-60 rounded-lg p-1">
            {RANGE_PRESETS.map((p) => {
              const r = p.range(todayIso());
              return (
                <li key={p.key} role="none">
                  <button
                    type="button"
                    role="menuitemradio"
                    aria-checked={range.preset === p.key}
                    onClick={() => {
                      setOpen(false);
                      setCustom(false);
                      onChange({ preset: p.key, ...r });
                    }}
                    className="shop-sort__item flex w-full items-center justify-between gap-2 rounded-md px-3 py-1.5 text-left text-sm"
                  >
                    <span>
                      {p.label}
                      <span className="showcase-muted block text-[0.6875rem]">{r.start === r.end ? formatCalendarDate(r.start) : `${formatCalendarDate(r.start)} – ${formatCalendarDate(r.end)}`}</span>
                    </span>
                    {range.preset === p.key && <FiCheck className="h-4 w-4 shrink-0" aria-hidden="true" />}
                  </button>
                </li>
              );
            })}
            <li role="none" className="mt-1 border-t pt-1">
              <button
                type="button"
                role="menuitemradio"
                aria-checked={range.preset === "custom"}
                onClick={() => {
                  setOpen(false);
                  setCustom(true);
                }}
                className="shop-sort__item flex w-full items-center justify-between gap-2 rounded-md px-3 py-1.5 text-left text-sm"
              >
                Custom Range
                {range.preset === "custom" && <FiCheck className="h-4 w-4 shrink-0" aria-hidden="true" />}
              </button>
            </li>
          </ul>
        )}
      </div>
    </div>
  );
}

// --- the page ---------------------------------------------------------------------------------------------------------

// Admin /dashboard: an ecommerce overview driven by ONE global date range (kept in the URL: ?range=this_month, or
// ?range=custom&from=…&to=…). All numbers come from a single backend call, GET /admin/dashboard/
// (apps.orders.analytics.admin_dashboard — aggregated in the database; nothing is computed from lists in the browser).
// Inventory figures are current stock (no history is stored); everything else follows the range, and the four headline
// figures are compared with the preceding period of the same length. Order Management stays its own page.
export default function AdminDashboardOverview({ user, initialRange, initialData, currencySymbol }) {
  const [range, setRange] = useState(initialRange);
  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(!initialData);
  const requestId = useRef(0);

  const money = (v) => formatPrice(v, currencySymbol);
  const short = (v) => compactMoney(v, currencySymbol);

  async function load(next) {
    const id = ++requestId.current;
    setLoading(true);
    try {
      const res = await fetch(`/api/admin/dashboard?date_from=${next.start}&date_to=${next.end}`, { cache: "no-store" });
      const body = await res.json().catch(() => null);
      if (id !== requestId.current) return;
      if (!res.ok) throw new Error(body?.error?.message);
      setData(body);
      setFailed(false);
    } catch (error) {
      if (id !== requestId.current) return;
      notify.error(error.message || "Unable to load dashboard data. Please try again.");
      if (!data) setFailed(true);
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }

  function changeRange(next) {
    setRange(next);
    // Keep the range in the address bar without a navigation (no second server render/fetch).
    window.history.replaceState(null, "", `/dashboard?${rangeToQuery(next)}`);
    load(next);
  }

  const head = data?.headline;
  const inv = data?.inventory;
  const series = data?.series ?? [];
  const unit = GRANULARITY_WORD[data?.granularity] ?? "day";
  const healthy = inv ? inv.in_stock - inv.low_stock : 0;
  const stockBar = inv && inv.total_products ? [
    { key: "in", label: "In Stock", n: healthy, cls: "stock-seg--in" },
    { key: "low", label: "Low Stock", n: inv.low_stock, cls: "stock-seg--low" },
    { key: "out", label: "Out of Stock", n: inv.out_of_stock, cls: "stock-seg--out" },
  ] : [];
  const categoryMax = Math.max(1, ...(data?.category_sales?.categories ?? []).map((c) => Number(c.revenue)));

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="custom-font text-3xl sm:text-4xl">Overview</h1>
          <p className="showcase-muted mt-1 text-sm">
            Here&apos;s what&apos;s happening with your store{user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}.
          </p>
        </div>
        <RangeFilter range={range} onChange={changeRange} disabled={loading} />
      </header>

      {failed ? (
        <div className="dashboard-card flex flex-col items-center gap-3 rounded-2xl px-6 py-14 text-center">
          <FiAlertCircle className="showcase-muted h-8 w-8" aria-hidden="true" />
          <p className="custom-font text-xl">Unable to load dashboard data</p>
          <button type="button" onClick={() => load(range)} disabled={loading} className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-5 py-2 text-sm font-medium">
            <FiRefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
            {loading ? "Retrying..." : "Retry"}
          </button>
        </div>
      ) : (
        <div className={`flex flex-col gap-6 transition-opacity ${loading ? "opacity-70" : ""}`} aria-busy={loading}>
          <section aria-label="Key figures" className="grid grid-cols-1 gap-4 min-[520px]:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
            <StatCard
              label="Total Revenue"
              value={short(head?.revenue.value)}
              fullValue={money(head?.revenue.value)}
              icon={TbCurrencyTaka}
              footer={<Delta change={head?.revenue.change} />}
              loading={loading}
            />
            <StatCard label="Total Orders" value={compactNumber(head?.orders.value)} icon={FiShoppingBag} footer={<Delta change={head?.orders.change} />} loading={loading} />
            <StatCard label="Products Sold" value={compactNumber(head?.products_sold.value)} icon={FiPackage} footer={<Delta change={head?.products_sold.change} />} loading={loading} />
            <StatCard label="New Customers" value={compactNumber(head?.new_customers.value)} icon={FiUserPlus} footer={<Delta change={head?.new_customers.change} />} loading={loading} />
            <StatCard
              label="Inventory Value"
              value={short(inv?.inventory_value)}
              fullValue={money(inv?.inventory_value)}
              icon={TbCurrencyTaka}
              footer={<span className="showcase-muted text-xs">Current stock × today&apos;s price</span>}
            />
          </section>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            <Panel
              className="xl:col-span-2"
              title="Revenue Overview"
              subtitle={`Confirmed, processing, shipped and delivered orders, by ${unit}`}
              action={<p className="text-xl font-semibold tabular-nums">{money(head?.revenue.value ?? 0)}</p>}
            >
              <TimeSeriesChart title="Revenue" data={series} valueKey="sales" format={money} formatAxis={short} granularity={data?.granularity} kind="area" emptyText="No sales data for this period." />
            </Panel>
            <Panel title="Order Status" subtitle="Orders placed in this period, by current status">
              <StatusDonut counts={data?.orders.by_status ?? {}} order={STATUS_ORDER} labels={STATUS_LABEL} emptyText="No orders for this period." />
            </Panel>
          </div>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
            <Panel
              className="xl:col-span-2"
              title="Orders Overview"
              subtitle={`Every order placed, by ${unit}`}
              action={<p className="text-xl font-semibold tabular-nums">{data?.orders.total ?? 0}</p>}
            >
              <TimeSeriesChart
                title="Orders"
                data={series}
                valueKey="orders"
                format={(v) => `${v} order${v === 1 ? "" : "s"}`}
                formatAxis={(v) => String(v)}
                granularity={data?.granularity}
                kind="bar"
                emptyText="No orders for this period."
              />
            </Panel>
            <Panel title="Inventory Overview" subtitle="Published products, right now" action={<ViewAll href="/dashboard/admin/products">View Products</ViewAll>}>
              {inv && (
                <>
                  {stockBar.length > 0 && (
                    <div className="flex h-2.5 w-full gap-0.5 overflow-hidden rounded-full" role="img" aria-label={`${healthy} in stock, ${inv.low_stock} low, ${inv.out_of_stock} out of stock`}>
                      {stockBar.filter((s) => s.n > 0).map((s) => (
                        <span key={s.key} className={`stock-seg ${s.cls}`} style={{ flexGrow: s.n }} />
                      ))}
                    </div>
                  )}
                  <ul className="flex flex-col gap-2 text-sm">
                    {stockBar.map((s) => (
                      <li key={s.key} className="flex items-center justify-between">
                        <span className="flex items-center gap-2">
                          <span className={`stock-seg ${s.cls} h-2.5 w-2.5 rounded-full`} aria-hidden="true" />
                          {s.label}
                        </span>
                        <span className="font-semibold tabular-nums">{s.n}</span>
                      </li>
                    ))}
                  </ul>
                  {data.out_of_stock_products?.length > 0 && (
                    <div className="border-t pt-3">
                      <p className="showcase-muted mb-2 text-xs font-medium uppercase tracking-wide">Out of stock</p>
                      <ul className="flex flex-col gap-2.5">
                        {data.out_of_stock_products.map((p) => (
                          <li key={p.id} className="flex items-center gap-3">
                            <div className="cart-thumb relative h-9 w-9 shrink-0 overflow-hidden rounded-lg">
                              <ProductImage src={p.image} alt="" tight />
                            </div>
                            <div className="min-w-0 flex-1">
                              <Link href={`/dashboard/admin/products/${p.id}`} className="block truncate text-sm font-medium hover:underline">
                                {p.name}
                              </Link>
                              <p className="showcase-muted truncate text-xs">{p.sku}{p.has_variants ? " · all variants sold out" : ""}</p>
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              )}
            </Panel>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
            <Panel title="Top Selling Products" subtitle="By units sold in this period">
              {data?.top_products?.length ? (
                <ul className="flex flex-col gap-3">
                  {data.top_products.map((p, i) => (
                    <li key={p.product_id} className="flex items-center gap-3">
                      <span className="showcase-muted w-4 shrink-0 text-xs tabular-nums">{i + 1}</span>
                      <div className="cart-thumb relative h-11 w-11 shrink-0 overflow-hidden rounded-lg">
                        <ProductImage src={p.image} alt="" tight />
                      </div>
                      <div className="min-w-0 flex-1">
                        <Link href={`/dashboard/admin/products/${p.product_id}`} className="block truncate text-sm font-medium hover:underline">
                          {p.name}
                        </Link>
                        <p className="showcase-muted text-xs">{p.sold} sold</p>
                      </div>
                      <span className="shrink-0 text-sm font-semibold tabular-nums" title={money(p.revenue)}>{short(p.revenue)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="chart-empty rounded-xl px-4 py-8 text-center text-sm">No sales data for this period.</p>
              )}
            </Panel>

            <Panel title="Sales by Category" subtitle="Item sales by each product's primary category">
              {data?.category_sales?.categories?.length ? (
                <ul className="flex flex-col gap-3">
                  {data.category_sales.categories.map((c) => (
                    <li key={c.name} className="flex flex-col gap-1.5">
                      <div className="flex items-center justify-between gap-3 text-sm">
                        <span className="truncate">{c.name}</span>
                        <span className="shrink-0 font-semibold tabular-nums" title={money(c.revenue)}>
                          {short(c.revenue)} <span className="showcase-muted text-xs font-normal">· {c.units} sold</span>
                        </span>
                      </div>
                      <span className="category-bar h-1.5 w-full overflow-hidden rounded-full">
                        <span className="category-bar__fill block h-full rounded-full" style={{ width: `${(Number(c.revenue) / categoryMax) * 100}%` }} />
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="chart-empty rounded-xl px-4 py-8 text-center text-sm">No sales data for this period.</p>
              )}
            </Panel>

            <Panel title="Customers" subtitle="Registered customer accounts" className="lg:col-span-2 xl:col-span-1">
              {data?.customers && (
                <dl className="grid grid-cols-2 gap-4">
                  {[
                    ["Total customers", data.customers.total, "All time"],
                    ["New customers", data.customers.new, "Signed up in this period"],
                    ["Returning", data.customers.returning, "Ordered before, and again now"],
                    ["First-time buyers", data.customers.first_time, "First order in this period"],
                  ].map(([label, value, hint]) => (
                    <div key={label} className="customer-stat rounded-xl p-3">
                      <dt className="showcase-muted text-xs">{label}</dt>
                      <dd className="mt-1 text-xl font-semibold tabular-nums">{compactNumber(value)}</dd>
                      <dd className="showcase-muted mt-0.5 text-[0.6875rem] leading-snug">{hint}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </Panel>
          </div>

          <Panel title="Recent Orders" subtitle="The latest orders placed in this period" action={<ViewAll href="/dashboard/admin/orders" />}>
            {data?.recent_orders?.length ? (
              <>
                <div className="hidden overflow-x-auto md:block">
                  <table className="product-table w-full min-w-[560px] text-left text-sm">
                    <thead>
                      <tr>
                        <th scope="col" className="px-3 py-2.5 font-medium">Order</th>
                        <th scope="col" className="px-3 py-2.5 font-medium">Customer</th>
                        <th scope="col" className="px-3 py-2.5 font-medium">Date</th>
                        <th scope="col" className="px-3 py-2.5 text-right font-medium">Amount</th>
                        <th scope="col" className="px-3 py-2.5 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent_orders.map((o) => (
                        <tr key={o.id}>
                          <td className="px-3 py-2.5">
                            <Link href={`/dashboard/admin/orders/${o.id}`} className="font-medium hover:underline">
                              #{o.number}
                            </Link>
                          </td>
                          <td className="px-3 py-2.5">{o.customer_name}</td>
                          <td className="whitespace-nowrap px-3 py-2.5">{formatOrderDate(o.created_at)}</td>
                          <td className="px-3 py-2.5 text-right tabular-nums">{money(o.grand_total)}</td>
                          <td className="px-3 py-2.5">
                            <StatusPill status={o.status} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <ul className="flex flex-col gap-3 md:hidden">
                  {data.recent_orders.map((o) => (
                    <li key={o.id} className="flex items-center justify-between gap-3 border-b pb-3 last:border-0 last:pb-0">
                      <div className="min-w-0">
                        <Link href={`/dashboard/admin/orders/${o.id}`} className="block truncate text-sm font-medium hover:underline">
                          #{o.number}
                        </Link>
                        <p className="showcase-muted truncate text-xs">
                          {o.customer_name} · {formatOrderDate(o.created_at)}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1">
                        <span className="text-sm font-semibold tabular-nums">{money(o.grand_total)}</span>
                        <StatusPill status={o.status} />
                      </div>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="chart-empty rounded-xl px-4 py-8 text-center text-sm">No orders for this period.</p>
            )}
          </Panel>

          {data?.previous_period && (
            <p className="showcase-muted text-center text-xs">
              Showing {rangeLabel(range)} · compared with {formatCalendarDate(data.previous_period.date_from)} – {formatCalendarDate(data.previous_period.date_to)}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
