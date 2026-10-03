import Link from "next/link";
import { FiDownload } from "react-icons/fi";
import formatPrice from "@/lib/formatPrice";
import { compactNumber } from "@/lib/dashboardFormat";

function Panel({ title, subtitle, action, children }) {
  return (
    <section className="dashboard-card flex min-w-0 flex-col gap-4 rounded-2xl p-5 sm:p-6">
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

// `columns` = [{ key, label, right?, render? }]; `empty` when there are no rows.
function Table({ columns, rows, rowKey, empty = "Nothing for this period." }) {
  if (!rows?.length) return <p className="chart-empty rounded-xl px-4 py-8 text-center text-sm">{empty}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="product-table w-full min-w-[26rem] text-left text-sm">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} scope="col" className={`px-3 py-2.5 font-medium ${c.right ? "text-right" : ""}`}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={rowKey ? rowKey(row) : i}>
              {columns.map((c) => (
                <td key={c.key} className={`px-3 py-2.5 ${c.right ? "text-right tabular-nums" : ""}`}>
                  {c.render ? c.render(row) : row[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Download({ href, children }) {
  return (
    <a href={href} download className="auth-btn auth-btn--outline inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium">
      <FiDownload className="h-3.5 w-3.5" aria-hidden="true" />
      {children}
    </a>
  );
}

function Figures({ items }) {
  return (
    <dl className="grid grid-cols-2 gap-4">
      {items.map(([label, value, hint]) => (
        <div key={label} className="customer-stat rounded-xl p-3">
          <dt className="showcase-muted text-xs">{label}</dt>
          <dd className="mt-1 text-xl font-semibold tabular-nums">{value}</dd>
          {hint && <dd className="showcase-muted mt-0.5 text-[0.6875rem] leading-snug">{hint}</dd>}
        </div>
      ))}
    </dl>
  );
}

// The report sections of the Admin dashboard (Module 17), for the dashboard's own date range: `reports` from
// GET /admin/dashboard/ (apps.reports.services.breakdowns), plus the CSV exports. A sale = confirmed, processing,
// shipped or delivered order.
export default function DashboardReports({ reports, range, currencySymbol }) {
  if (!reports) return null;
  const money = (v) => formatPrice(v, currencySymbol);
  const qs = `date_from=${range.start}&date_to=${range.end}`;
  const sales = [
    { key: "orders", label: "Orders", right: true },
    { key: "sale_orders", label: "Sales", right: true },
    { key: "revenue", label: "Revenue", right: true, render: (r) => money(r.revenue) },
  ];

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
        <div>
          <h2 className="custom-font text-2xl">Reports</h2>
          <p className="showcase-muted text-xs">Same period · a sale is a confirmed, processing, shipped or delivered order</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Download href={`/api/admin/reports/export/orders?${qs}`}>Orders CSV</Download>
          <Download href="/api/admin/reports/export/products">Products CSV</Download>
          <Download href="/api/admin/reports/export/customers">Customers CSV</Download>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Panel title="Orders by Source" subtitle="Where this period's orders came from">
          <Table columns={[{ key: "label", label: "Source" }, ...sales]} rows={reports.by_source} rowKey={(r) => r.source} />
        </Panel>
        <Panel title="Orders by Staff" subtitle={`Orders entered by hand · ${compactNumber(reports.summary.manual_orders)} in total`}>
          <Table
            columns={[
              { key: "name", label: "Staff member", render: (r) => <span>{r.name} <span className="showcase-muted text-xs">{r.role}</span></span> },
              ...sales,
            ]}
            rows={reports.by_staff}
            rowKey={(r) => r.user_id ?? "former"}
            empty="No staff-entered orders in this period."
          />
        </Panel>
        <Panel title="Delivery Zones" subtitle={`Zone and charge saved on each order · ${money(reports.summary.shipping_revenue)} shipping charged on sales`}>
          <Table
            columns={[
              { key: "zone", label: "Zone" },
              { key: "orders", label: "Orders", right: true },
              { key: "sale_orders", label: "Sales", right: true },
              { key: "shipping_revenue", label: "Shipping", right: true, render: (r) => money(r.shipping_revenue) },
              { key: "revenue", label: "Revenue", right: true, render: (r) => money(r.revenue) },
            ]}
            rows={reports.by_zone}
            rowKey={(r) => r.zone}
          />
        </Panel>
        <Panel title="Coupon Performance" subtitle={`Orders that used a coupon · ${money(reports.summary.discount_given)} discount given on sales`}>
          <Table
            columns={[
              { key: "code", label: "Code" },
              { key: "orders", label: "Orders", right: true },
              { key: "sale_orders", label: "Sales", right: true },
              { key: "discount", label: "Discount", right: true, render: (r) => money(r.discount) },
              { key: "revenue", label: "Revenue", right: true, render: (r) => money(r.revenue) },
            ]}
            rows={reports.coupons}
            rowKey={(r) => r.code}
            empty="No coupons used in this period."
          />
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Panel title="Reviews" subtitle="Submitted in this period">
          <Figures
            items={[
              ["Reviews", compactNumber(reports.reviews.total)],
              ["Average rating", reports.reviews.average_rating ?? "—", "Approved reviews"],
              ["Approved / rejected", `${reports.reviews.approved} / ${reports.reviews.rejected}`],
              ["Awaiting moderation", compactNumber(reports.reviews.awaiting_moderation), "Right now"],
            ]}
          />
          {reports.reviews.awaiting_moderation > 0 && (
            <Link href="/dashboard/admin/reviews" className="text-sm font-medium hover:underline">
              Moderate reviews →
            </Link>
          )}
        </Panel>
        <Panel title="Accounts at Checkout" subtitle="Customers who chose to save their details">
          <Figures
            items={[
              ["New this period", compactNumber(reports.customers.new_via_checkout), `of ${compactNumber(reports.customers.new)} new customers`],
              ["All time", compactNumber(reports.customers.total_via_checkout), `of ${compactNumber(reports.customers.total)} customers`],
            ]}
          />
        </Panel>
        <Panel title="Low Stock" subtitle="At or below the alert level, right now">
          <Table
            columns={[
              { key: "name", label: "Product", render: (r) => <Link href={`/dashboard/admin/products/${r.id}`} className="hover:underline">{r.name}</Link> },
              { key: "stock", label: "Stock", right: true },
              { key: "threshold", label: "Alert", right: true },
            ]}
            rows={reports.low_stock}
            rowKey={(r) => r.id}
            empty="Nothing is running low."
          />
        </Panel>
      </div>
    </>
  );
}
