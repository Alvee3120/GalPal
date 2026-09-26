import Link from "next/link";
import formatPrice from "@/lib/formatPrice";
import { formatOrderDateTime } from "@/lib/orderStatus";
import { COUPON_STATUS_LABEL, COUPON_TYPE_LABEL } from "@/lib/couponAdmin";
import ProductImage from "@/component/shared/ProductImage";

function Row({ label, children }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="showcase-muted text-xs">{label}</dt>
      <dd className="text-sm font-medium">{children}</dd>
    </div>
  );
}

function Card({ title, children }) {
  return (
    <section className="dashboard-card rounded-2xl p-5 sm:p-6">
      <h2 className="custom-font text-lg">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

const yesNo = (value) => (value ? "Yes" : "No");
const chips = (items, empty) =>
  items.length ? (
    <ul className="flex flex-wrap gap-1.5">
      {items.map((name) => (
        <li key={name} className="area-chip rounded-full px-3 py-1 text-xs font-medium">
          {name}
        </li>
      ))}
    </ul>
  ) : (
    <span className="showcase-muted font-normal">{empty}</span>
  );

// A coupon, read-only (CCE): every field of GET /admin/coupons/<id>/ — the same record Admin edits — with no controls.
export default function CouponDetails({ coupon, currencySymbol }) {
  const money = (v) => formatPrice(v, currencySymbol);
  const percentage = coupon.type === "percentage";
  const restricted = coupon.products.length + coupon.categories.length + coupon.brands.length > 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/dashboard/CCE/coupons" className="showcase-muted text-sm hover:underline">
            &larr; Coupons
          </Link>
          <h1 className="custom-font mt-2 font-mono text-2xl sm:text-3xl">{coupon.code}</h1>
          {coupon.description && <p className="showcase-muted mt-1 text-sm">{coupon.description}</p>}
        </div>
        <span className="coupon-status rounded-full px-3 py-1 text-sm font-medium" data-status={coupon.status}>
          {COUPON_STATUS_LABEL[coupon.status] ?? coupon.status}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="Discount">
          <dl className="grid grid-cols-2 gap-4">
            <Row label="Type">{COUPON_TYPE_LABEL[coupon.type] ?? coupon.type}</Row>
            <Row label="Amount">{percentage ? `${Number(coupon.amount)}%` : money(coupon.amount)}</Row>
            <Row label="Max discount amount">{percentage && coupon.max_discount_amount != null ? money(coupon.max_discount_amount) : "No cap"}</Row>
            <Row label="Min order amount">{Number(coupon.min_order_amount) > 0 ? money(coupon.min_order_amount) : "None"}</Row>
            <Row label="Exclude sale items">{yesNo(coupon.exclude_sale_items)}</Row>
            <Row label="First order only">{yesNo(coupon.first_order_only)}</Row>
            <Row label="Free shipping">{yesNo(coupon.free_shipping)}</Row>
          </dl>
        </Card>

        <Card title="Validity & Usage">
          <dl className="grid grid-cols-2 gap-4">
            <Row label="Start at">{coupon.start_at ? formatOrderDateTime(coupon.start_at) : "Immediately"}</Row>
            <Row label="Expiry at">{coupon.expiry_at ? formatOrderDateTime(coupon.expiry_at) : "Never"}</Row>
            <Row label="Is active">{yesNo(coupon.is_active)}</Row>
            <Row label="Current usage">{coupon.usage_count}</Row>
            <Row label="Total usage limit">{coupon.total_usage_limit ?? "Unlimited"}</Row>
            <Row label="Per customer usage limit">{coupon.per_customer_usage_limit ?? "Unlimited"}</Row>
          </dl>
        </Card>
      </div>

      <Card title="Restrictions">
        <p className="showcase-muted mb-4 text-xs">
          {restricted
            ? "Only products matching ANY of these get the discount (a category includes its sub-categories)."
            : "No restrictions: the coupon applies to every product."}
        </p>
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium">Products</span>
            {coupon.products.length ? (
              <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {coupon.products.map((p) => (
                  <li key={p.id} className="flex items-center gap-3">
                    <span className="cart-thumb relative h-10 w-10 shrink-0 overflow-hidden rounded-lg">
                      <ProductImage src={p.feature_image} alt="" tight />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-sm">{p.name}</span>
                      <span className="showcase-muted block text-xs">{p.sku}</span>
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <span className="showcase-muted text-sm">None</span>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium">Categories</span>
            {chips(coupon.categories.map((c) => c.name), "None")}
          </div>
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium">Brands</span>
            {chips(coupon.brands.map((b) => b.name), "None")}
          </div>
        </div>
      </Card>
    </div>
  );
}
