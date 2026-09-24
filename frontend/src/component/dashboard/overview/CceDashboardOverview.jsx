"use client";

import { useState } from "react";
import Link from "next/link";
import { FiAlertCircle, FiBox, FiCheckCircle, FiRefreshCw, FiTrendingUp, FiXCircle } from "react-icons/fi";
import { TbCurrencyTaka } from "react-icons/tb";
import { notify } from "@/lib/notify";
import formatPrice from "@/lib/formatPrice";
import { STATUS_LABEL } from "@/lib/orderStatus";
import { splitStoreDateTime } from "@/lib/productAdmin";
import OrderDateRangePicker, { formatCalendarDate } from "../OrderDateRangePicker";
import TimeSeriesChart from "./TimeSeriesChart";

const STATUS_ORDER = ["pending", "confirmed", "processing", "shipped", "delivered", "cancelled", "returned", "failed"];

// Calendar dates in the store's zone (Asia/Dhaka), the same zone the backend reads date_from/date_to in.
const todayIso = () => splitStoreDateTime(new Date().toISOString()).date;
function shiftIso(iso, days) {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
const PRESETS = [
  { key: "7d", label: "Last 7 days", range: () => ({ start: shiftIso(todayIso(), -6), end: todayIso() }) },
  { key: "30d", label: "Last 30 days", range: () => ({ start: shiftIso(todayIso(), -29), end: todayIso() }) },
  { key: "month", label: "This month", range: () => ({ start: `${todayIso().slice(0, 8)}01`, end: todayIso() }) },
  { key: "12m", label: "Last 12 months", range: () => ({ start: shiftIso(todayIso(), -364), end: todayIso() }) },
];

// From 10,000 up: "10k", "10.34k" (at most 2 decimals, trailing zeros dropped); from a million: "1.04M".
// Below 10,000 the full amount is short enough ("9,850"). Cards show the full figure on hover (title).
const trim2 = (n) => String(Number(n.toFixed(2)));
function compactMoney(value, symbol) {
  const n = Number(value) || 0;
  if (Math.abs(n) >= 1_000_000) return `${symbol}${trim2(n / 1_000_000)}M`;
  if (Math.abs(n) >= 10_000) return `${symbol}${trim2(n / 1_000)}k`;
  return formatPrice(n, symbol);
}

function StatCard({ label, value, fullValue, hint, icon: Icon, loading }) {
  return (
    <div className="dashboard-card flex min-w-0 flex-col gap-3 rounded-2xl p-5">
      <div className="flex items-center justify-between gap-3">
        <p className="showcase-muted text-sm">{label}</p>
        <span className="dashboard-card__icon flex h-9 w-9 shrink-0 items-center justify-center rounded-full">
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
      </div>
      {loading ? (
        <div className="product-skeleton__line h-8 w-24 animate-pulse rounded-lg" />
      ) : (
        <p className="truncate text-2xl font-semibold tabular-nums sm:text-3xl" title={fullValue}>
          {value}
        </p>
      )}
      {hint && <p className="showcase-muted text-xs">{hint}</p>}
    </div>
  );
}

function Panel({ title, subtitle, children, action }) {
  return (
    <section className="dashboard-card flex min-w-0 flex-col gap-4 rounded-2xl p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="custom-font text-lg">{title}</h2>
          {subtitle && <p className="showcase-muted text-xs">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

// The CCE /dashboard: current inventory and sales/orders for a period, from ONE backend call
// (GET /admin/orders/dashboard/, apps.orders.analytics — counts, sums and the time series are aggregated there, never
// from lists fetched into the browser). Inventory is always "now"; the date range drives sales, orders and the charts.
// Order Management is its own page (/dashboard/CCE/orders).
export default function CceDashboardOverview({ initialData, currencySymbol }) {
  const [data, setData] = useState(initialData);
  const [preset, setPreset] = useState("30d");
  const [customRange, setCustomRange] = useState(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(!initialData);

  const money = (v) => formatPrice(v, currencySymbol);

  async function load(range) {
    setLoading(true);
    try {
      const qs = range ? `?date_from=${range.start}&date_to=${range.end}` : "";
      const res = await fetch(`/api/admin/orders/dashboard${qs}`, { cache: "no-store" });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(body?.error?.message);
      setData(body);
      setFailed(false);
    } catch (error) {
      notify.error(error.message || "Unable to load the dashboard. Please try again.");
      if (!data) setFailed(true);
    } finally {
      setLoading(false);
    }
  }

  function choosePreset(p) {
    setPreset(p.key);
    setCustomRange(null);
    load(p.range());
  }

  function chooseCustom(range) {
    setCustomRange(range);
    if (range) {
      setPreset("custom");
      load(range);
    } else {
      choosePreset(PRESETS[1]);
    }
  }

  const inventory = data?.inventory;
  const periodLabel = data
    ? data.date_from === data.date_to
      ? formatCalendarDate(data.date_from)
      : `${formatCalendarDate(data.date_from)} – ${formatCalendarDate(data.date_to)}`
    : "";
  const series = data?.series ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="custom-font text-2xl sm:text-3xl">Dashboard Overview</h1>
          <p className="showcase-muted mt-1 text-sm">Inventory right now, and sales and orders for the selected period.</p>
        </div>
        <Link href="/dashboard/CCE/orders" className="auth-btn auth-btn--outline rounded-full px-5 py-2 text-sm font-medium">
          Go to Order Management
        </Link>
      </div>

      {failed ? (
        <div className="dashboard-card flex flex-col items-center gap-3 rounded-2xl px-6 py-14 text-center">
          <FiAlertCircle className="showcase-muted h-8 w-8" aria-hidden="true" />
          <p className="custom-font text-xl">The dashboard couldn&apos;t be loaded</p>
          <button type="button" onClick={() => load(customRange)} disabled={loading} className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-5 py-2 text-sm font-medium">
            <FiRefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
            {loading ? "Retrying..." : "Retry"}
          </button>
        </div>
      ) : (
        <>
          <section aria-label="Inventory" className="grid grid-cols-1 gap-4 min-[480px]:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            <StatCard label="Total Products" value={inventory?.total_products ?? 0} hint="Published products" icon={FiBox} />
            <StatCard label="In Stock" value={inventory?.in_stock ?? 0} hint="Available to order now" icon={FiCheckCircle} />
            <StatCard label="Out of Stock" value={inventory?.out_of_stock ?? 0} hint="Nothing left to sell" icon={FiXCircle} />
            <StatCard
              label="Total Product Value"
              value={compactMoney(inventory?.inventory_value ?? 0, currencySymbol)}
              fullValue={money(inventory?.inventory_value ?? 0)}
              hint="Stock on hand × current price"
              icon={TbCurrencyTaka}
            />
            <StatCard
              label="Total Sales"
              value={compactMoney(data?.sales.total ?? 0, currencySymbol)}
              fullValue={money(data?.sales.total ?? 0)}
              hint={`${data?.sales.orders ?? 0} confirmed order${data?.sales.orders === 1 ? "" : "s"} · selected period`}
              icon={FiTrendingUp}
              loading={loading}
            />
          </section>

          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
            <div role="group" aria-label="Period" className="flex flex-wrap gap-1.5">
              {PRESETS.map((p) => (
                <button
                  key={p.key}
                  type="button"
                  aria-pressed={preset === p.key}
                  onClick={() => choosePreset(p)}
                  disabled={loading}
                  className={`auth-btn rounded-full px-4 py-2 text-xs font-medium ${preset === p.key ? "auth-btn--primary" : "auth-btn--outline"}`}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <OrderDateRangePicker value={customRange} onChange={chooseCustom} />
            <p className="showcase-muted text-xs sm:ml-auto" aria-live="polite">
              {loading ? "Updating..." : periodLabel}
            </p>
          </div>

          <div className={`grid grid-cols-1 gap-6 xl:grid-cols-2 ${loading ? "opacity-60 transition-opacity" : ""}`} aria-busy={loading}>
            <Panel
              title="Sales Overview"
              subtitle={`Confirmed, processing, shipped and delivered orders, by ${data?.granularity === "month" ? "month" : "day"} placed`}
              action={<p className="text-sm font-semibold tabular-nums">{money(data?.sales.total ?? 0)}</p>}
            >
              <TimeSeriesChart
                title="Sales"
                data={series}
                valueKey="sales"
                format={money}
                formatAxis={(v) => compactMoney(v, currencySymbol)}
                granularity={data?.granularity}
                kind="area"
                emptyText="No sales in this period."
              />
            </Panel>
            <Panel
              title="Orders Overview"
              subtitle={`Every order placed, by ${data?.granularity === "month" ? "month" : "day"}`}
              action={<p className="text-sm font-semibold tabular-nums">{data?.orders.total ?? 0} orders</p>}
            >
              <TimeSeriesChart
                title="Orders"
                data={series}
                valueKey="orders"
                format={(v) => `${v} order${v === 1 ? "" : "s"}`}
                formatAxis={(v) => String(v)}
                granularity={data?.granularity}
                kind="bar"
                emptyText="No orders in this period."
              />
            </Panel>
          </div>

          <Panel title="Orders by Status" subtitle="Orders placed in the selected period, by their current status">
            <ul className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
              {STATUS_ORDER.map((status) => (
                <li key={status} className="flex items-center justify-between gap-3 text-sm">
                  <span className="flex items-center gap-2">
                    <span data-status={status} className="order-status order-status--dot h-2 w-2 shrink-0 rounded-full" aria-hidden="true" />
                    {STATUS_LABEL[status] ?? status}
                  </span>
                  <span className="font-semibold tabular-nums">{data?.orders.by_status?.[status] ?? 0}</span>
                </li>
              ))}
            </ul>
          </Panel>
        </>
      )}
    </div>
  );
}
