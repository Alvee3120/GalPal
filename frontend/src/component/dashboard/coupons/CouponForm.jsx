"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { notify } from "@/lib/notify";
import { catalogFetch, catalogFetchAll, errorText, joinStoreDateTime, splitStoreDateTime } from "@/lib/productAdmin";
import { flattenCategoryTree } from "@/lib/categoryAdmin";
import { COUPON_TYPES, couponFetch } from "@/lib/couponAdmin";
import DualListPicker from "./DualListPicker";

const INPUT = "checkout-input rounded-lg px-3 py-2.5 text-sm";
const MONEY = /^\d+(\.\d{1,2})?$/;
const WHOLE = /^\d+$/;

function Section({ title, description, children }) {
  return (
    <section className="dashboard-card rounded-2xl p-5 sm:p-6">
      <h2 className="custom-font text-lg">{title}</h2>
      {description && <p className="showcase-muted mt-1 text-xs">{description}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Field({ id, label, hint, required, children }) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label} {required && <span aria-hidden="true">*</span>}
      </label>
      {children}
      {hint && <p className="showcase-muted text-xs">{hint}</p>}
    </div>
  );
}

function Toggle({ id, label, hint, checked, onChange }) {
  return (
    <label htmlFor={id} className="flex cursor-pointer items-start gap-2.5 text-sm">
      <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="form-check mt-0.5 h-4 w-4 shrink-0" />
      <span>
        {label}
        {hint && <span className="showcase-muted block text-xs">{hint}</span>}
      </span>
    </label>
  );
}

// Date + time in the store's zone (Asia/Dhaka), the zone the backend reads naive datetimes in.
function DateTime({ id, label, hint, date, time, onDate, onTime }) {
  return (
    <Field id={id} label={label} hint={hint}>
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,7.5rem)] gap-2">
        <input id={id} type="date" value={date} onChange={(e) => onDate(e.target.value)} className={INPUT} />
        <input type="time" aria-label={`${label} time`} value={time} onChange={(e) => onTime(e.target.value)} className={INPUT} />
      </div>
    </Field>
  );
}

const str = (v) => (v === null || v === undefined ? "" : String(v));
const product = (p) => ({ id: p.id, label: p.name, hint: p.sku, image: p.feature_image });

function initial(c) {
  const start = splitStoreDateTime(c?.start_at);
  const end = splitStoreDateTime(c?.expiry_at);
  return {
    code: str(c?.code),
    description: str(c?.description),
    type: c?.type ?? "percentage",
    amount: c ? String(Number(c.amount)) : "",
    max_discount_amount: c?.max_discount_amount != null ? String(Number(c.max_discount_amount)) : "",
    min_order_amount: c ? String(Number(c.min_order_amount)) : "0",
    start_date: start.date,
    start_time: start.time,
    end_date: end.date,
    end_time: end.time || (end.date ? "23:59" : ""),
    is_active: c?.is_active ?? true,
    total_usage_limit: str(c?.total_usage_limit),
    per_customer_usage_limit: str(c?.per_customer_usage_limit),
    exclude_sale_items: c?.exclude_sale_items ?? false,
    first_order_only: c?.first_order_only ?? false,
    free_shipping: c?.free_shipping ?? false,
  };
}

// Add / Edit Coupon over the EXISTING /admin/coupons/ API (apps.coupons — IsAdmin). Every rule is the backend's: the
// code is stored upper-case and must be unique (ignoring case), a percentage can't pass 100 and only a percentage can
// have a cap, expiry must come after start, and at checkout apps.coupons.services / apps.orders.services recalculate
// and re-check everything (dates, limits, restrictions, first order, free delivery) — the checks here only catch the
// obvious first. Products / categories / brands are sent as ids; empty on all three means the coupon applies to every
// product, and when any are chosen a product qualifies by matching ANY of them (a category includes its sub-categories).
export default function CouponForm({ coupon = null, currencySymbol }) {
  const router = useRouter();
  const isEdit = Boolean(coupon);
  const [v, setV] = useState(() => initial(coupon));
  const [products, setProducts] = useState(() => (coupon?.products ?? []).map(product));
  const [categories, setCategories] = useState(() => (coupon?.categories ?? []).map((c) => ({ id: c.id, label: c.name })));
  const [brands, setBrands] = useState(() => (coupon?.brands ?? []).map((b) => ({ id: b.id, label: b.name })));
  const [lookups, setLookups] = useState({ categories: [], brands: [] });
  const [submitting, setSubmitting] = useState(false);

  const set = (name) => (value) => setV((s) => ({ ...s, [name]: value }));
  const onInput = (name) => (e) => set(name)(e.target.value);
  const percentage = v.type === "percentage";

  useEffect(() => {
    let cancelled = false;
    Promise.all([catalogFetch("categories/tree"), catalogFetchAll("brands?ordering=name")]).then(([tree, brandList]) => {
      if (cancelled) return;
      if (!tree.ok || !brandList) notify.error("Categories or brands couldn't be loaded. Please refresh.");
      setLookups({
        categories: tree.ok ? flattenCategoryTree(tree.data).map((c) => ({ id: c.id, label: `${"— ".repeat(c.depth)}${c.name}` })) : [],
        brands: (brandList ?? []).map((b) => ({ id: b.id, label: b.name, hint: b.is_active ? "" : "Inactive" })),
      });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // Products are searched on the server (there can be many): the first 20 matches of the product list.
  const searchProducts = useCallback(async (query) => {
    const params = new URLSearchParams({ page_size: "20" });
    if (query) params.set("search", query);
    const res = await catalogFetch(`products?${params.toString()}`);
    return res.ok ? (res.data.results ?? []).map(product) : [];
  }, []);

  function validate() {
    const code = v.code.trim();
    if (!code) return "Code is required.";
    if (!/^[A-Za-z0-9_-]+$/.test(code)) return "Code can only use letters, numbers, - and _ (no spaces).";
    if (!MONEY.test(v.amount.trim()) || Number(v.amount) <= 0) return "Amount must be a number greater than 0.";
    if (percentage && Number(v.amount) > 100) return "A percentage can't be more than 100.";
    if (v.max_discount_amount.trim() && !MONEY.test(v.max_discount_amount.trim())) return "Max discount amount must be 0 or more.";
    if (!MONEY.test(v.min_order_amount.trim() || "0")) return "Min order amount must be 0 or more.";
    if ((v.start_time && !v.start_date) || (v.end_time && !v.end_date)) return "Pick a date for the time you entered.";
    const start = joinStoreDateTime(v.start_date, v.start_time);
    const end = joinStoreDateTime(v.end_date, v.end_time || "23:59");
    if (start && end && end <= start) return "Expiry must be after the start.";
    for (const [key, label] of [["total_usage_limit", "Total usage limit"], ["per_customer_usage_limit", "Per customer usage limit"]]) {
      if (v[key].trim() && !WHOLE.test(v[key].trim())) return `${label} must be a whole number, or empty for unlimited.`;
    }
    return null;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting) return;
    const problem = validate();
    if (problem) return notify.error(problem);

    const body = {
      code: v.code.trim().toUpperCase(),
      description: v.description.trim(),
      type: v.type,
      amount: v.amount.trim(),
      max_discount_amount: percentage && v.max_discount_amount.trim() ? v.max_discount_amount.trim() : null,
      min_order_amount: v.min_order_amount.trim() || "0",
      start_at: joinStoreDateTime(v.start_date, v.start_time),
      expiry_at: v.end_date ? joinStoreDateTime(v.end_date, v.end_time || "23:59") : null,
      is_active: v.is_active,
      total_usage_limit: v.total_usage_limit.trim() ? Number(v.total_usage_limit) : null,
      per_customer_usage_limit: v.per_customer_usage_limit.trim() ? Number(v.per_customer_usage_limit) : null,
      product_ids: products.map((p) => p.id),
      category_ids: categories.map((c) => c.id),
      brand_ids: brands.map((b) => b.id),
      exclude_sale_items: v.exclude_sale_items,
      first_order_only: v.first_order_only,
      free_shipping: v.free_shipping,
    };

    setSubmitting(true);
    const res = await couponFetch(isEdit ? `/${coupon.id}` : "", { method: isEdit ? "PATCH" : "POST", body });
    if (!res.ok) {
      setSubmitting(false);
      return notify.error(errorText(res, isEdit ? "Unable to update the coupon. Please try again." : "Unable to create the coupon. Please try again."));
    }
    notify.success(isEdit ? "Coupon updated successfully." : "Coupon created successfully.");
    router.push("/dashboard/admin/coupons");
    router.refresh();
  }

  const restricted = products.length + categories.length + brands.length > 0;

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-6">
      <Section title="Basic Information">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field id="cf-code" label="Code" required hint="Customers type this at checkout. Saved in capitals; not case-sensitive.">
            <input
              id="cf-code"
              type="text"
              maxLength={32}
              autoComplete="off"
              value={v.code}
              onChange={(e) => set("code")(e.target.value.toUpperCase())}
              placeholder="WELCOME10"
              className={`${INPUT} font-mono uppercase`}
            />
          </Field>
          <Field id="cf-type" label="Type" required>
            <select id="cf-type" value={v.type} onChange={onInput("type")} className={INPUT}>
              {COUPON_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </Field>
          <Field id="cf-amount" label="Amount" required hint={percentage ? "Percent off the eligible items, up to 100." : "Taka off the eligible items."}>
            <div className="relative">
              <span className="showcase-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm" aria-hidden="true">
                {percentage ? "%" : currencySymbol}
              </span>
              <input
                id="cf-amount"
                type="number"
                inputMode="decimal"
                min="0"
                max={percentage ? 100 : undefined}
                step="0.01"
                value={v.amount}
                onChange={onInput("amount")}
                className={`${INPUT} w-full pl-8`}
              />
            </div>
          </Field>
          <Field id="cf-description" label="Description" hint="Optional. For your team, e.g. what the coupon is for.">
            <textarea id="cf-description" rows={2} maxLength={255} value={v.description} onChange={onInput("description")} className={INPUT} />
          </Field>
        </div>
      </Section>

      <Section title="Discount Rules">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {percentage && (
            <Field id="cf-max" label="Max discount amount" hint="Optional cap, e.g. 10% off up to ৳500. Empty: no cap.">
              <input id="cf-max" type="number" inputMode="decimal" min="0" step="0.01" value={v.max_discount_amount} onChange={onInput("max_discount_amount")} className={INPUT} />
            </Field>
          )}
          <Field id="cf-min" label="Min order amount" hint="The cart subtotal needed to use it. 0: no minimum.">
            <input id="cf-min" type="number" inputMode="decimal" min="0" step="0.01" value={v.min_order_amount} onChange={onInput("min_order_amount")} className={INPUT} />
          </Field>
          <div className="flex flex-col gap-3 sm:col-span-2">
            <Toggle id="cf-sale" label="Exclude sale items" hint="Products currently on sale don't get the discount." checked={v.exclude_sale_items} onChange={set("exclude_sale_items")} />
            <Toggle
              id="cf-first"
              label="First order only"
              hint="Only for a customer's first order (checked against their past orders by account and phone)."
              checked={v.first_order_only}
              onChange={set("first_order_only")}
            />
            <Toggle id="cf-ship" label="Free shipping" hint="The delivery charge becomes free when this coupon applies." checked={v.free_shipping} onChange={set("free_shipping")} />
          </div>
        </div>
      </Section>

      <Section title="Validity" description="In Bangladesh time. Leave the start empty to make it usable right away, and the expiry empty for no end date.">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <DateTime id="cf-start" label="Start at" date={v.start_date} time={v.start_time} onDate={set("start_date")} onTime={set("start_time")} />
          <DateTime id="cf-end" label="Expiry at" hint="Without a time it ends at 11:59 PM." date={v.end_date} time={v.end_time} onDate={set("end_date")} onTime={set("end_time")} />
          <div className="sm:col-span-2">
            <Toggle id="cf-active" label="Is active" hint="Switch off to stop the coupon working at any time." checked={v.is_active} onChange={set("is_active")} />
          </div>
        </div>
      </Section>

      <Section title="Usage Limits" description="Leave empty for unlimited. Uses are counted per placed order; a cancelled or failed order gives its use back.">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field id="cf-total" label="Total usage limit" hint="Across all customers.">
            <input id="cf-total" type="number" inputMode="numeric" min="0" step="1" value={v.total_usage_limit} onChange={onInput("total_usage_limit")} className={INPUT} />
          </Field>
          <Field id="cf-per" label="Per customer usage limit" hint="Per account, or per phone number for guests.">
            <input id="cf-per" type="number" inputMode="numeric" min="0" step="1" value={v.per_customer_usage_limit} onChange={onInput("per_customer_usage_limit")} className={INPUT} />
          </Field>
        </div>
      </Section>

      <Section
        title="Restrictions"
        description={
          restricted
            ? "Only products matching ANY of the choices below get the discount (a category includes its sub-categories)."
            : "Nothing chosen: the coupon applies to every product."
        }
      >
        <div className="flex flex-col gap-6">
          <DualListPicker id="cf-products" label="Products" onSearch={searchProducts} chosen={products} onChange={setProducts} showImages allText="None — not limited by product." />
          <DualListPicker id="cf-categories" label="Categories" options={lookups.categories} chosen={categories} onChange={setCategories} allText="None — not limited by category." />
          <DualListPicker id="cf-brands" label="Brands" options={lookups.brands} chosen={brands} onChange={setBrands} allText="None — not limited by brand." />
        </div>
      </Section>

      <div className="flex flex-wrap items-center justify-end gap-3">
        <Link href="/dashboard/admin/coupons" className="auth-btn auth-btn--outline rounded-full px-6 py-2.5 text-sm font-medium">
          Cancel
        </Link>
        <button type="submit" disabled={submitting} aria-busy={submitting} className="auth-btn auth-btn--primary rounded-full px-6 py-2.5 text-sm font-medium">
          {submitting ? (isEdit ? "Saving Coupon..." : "Creating Coupon...") : isEdit ? "Save Changes" : "Create Coupon"}
        </button>
      </div>
    </form>
  );
}
