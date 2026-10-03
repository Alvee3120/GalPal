"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { notify } from "@/lib/notify";
import formatPrice from "@/lib/formatPrice";
import { catalogFetch, errorText, joinStoreDateTime, splitStoreDateTime } from "@/lib/productAdmin";
import { flattenCategoryTree } from "@/lib/categoryAdmin";
import { DISCOUNT_KINDS, DISCOUNT_TARGETS, discountFetch } from "@/lib/discountAdmin";
import DualListPicker from "../coupons/DualListPicker";
import SearchPicker from "../SearchPicker";

const INPUT = "checkout-input rounded-lg px-3 py-2.5 text-sm";
const MONEY = /^\d+(\.\d{1,2})?$/;

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

// Date + time in the store's time zone (the zone the backend reads naive datetimes in) — the same pattern as coupons.
function DateTime({ id, label, hint, date, time, onDate, onTime }) {
  return (
    <Field id={id} label={label} hint={hint} required>
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,7.5rem)] gap-2">
        <input id={id} type="date" value={date} onChange={(e) => onDate(e.target.value)} className={INPUT} />
        <input type="time" aria-label={`${label} time`} value={time} onChange={(e) => onTime(e.target.value)} className={INPUT} />
      </div>
    </Field>
  );
}

const stockText = (p) =>
  p.has_variants ? `${p.variant_stock ?? 0} in variants` : p.manage_stock === false ? "Stock not tracked" : p.in_stock === false ? "Out of stock" : `${p.stock_quantity} in stock`;

// Picker items for every category, with its place in the tree as the hint ("Skincare › Serums"), inactive ones marked.
function withPaths(flat) {
  const trail = [];
  return flat.map((c) => {
    trail[c.depth] = c.name;
    trail.length = c.depth + 1;
    const path = trail.slice(0, -1).join(" › ");
    return { id: c.id, label: c.name, hint: [path || "Top level", c.is_active === false ? "Inactive" : ""].filter(Boolean).join(" · ") };
  });
}

function initial(d) {
  const start = splitStoreDateTime(d?.starts_at);
  const end = splitStoreDateTime(d?.ends_at);
  return {
    name: d?.name ?? "",
    kind: d?.kind ?? "percentage",
    value: d ? String(Number(d.value)) : "",
    target_type: d?.target_type ?? "category",
    start_date: start.date,
    start_time: start.time || "00:00",
    end_date: end.date,
    end_time: end.time || "23:59",
    is_active: d?.is_active ?? true,
  };
}

// Add / Edit Discount over /admin/discounts/ (apps.discounts — IsAdmin). The backend is the authority on everything: the
// value range, end after start, the category / products existing, a fixed amount not exceeding any covered price, and
// at every price shown or charged it works out the single effective reduction (product discount beats category; the
// lower of that and a product's own sale price; never stacked). The checks here only catch the obvious first.
export default function DiscountForm({ discount = null, currencySymbol }) {
  const router = useRouter();
  const isEdit = Boolean(discount);
  const [v, setV] = useState(() => initial(discount));
  const [category, setCategory] = useState(() => (discount?.category ? { id: discount.category.id, label: discount.category.name } : null));
  const [products, setProducts] = useState(() =>
    (discount?.products ?? []).map((p) => ({ id: p.id, label: p.name, hint: p.sku, image: p.feature_image })),
  );
  const [categories, setCategories] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const set = (name) => (value) => setV((s) => ({ ...s, [name]: value }));
  const percentage = v.kind === "percentage";

  useEffect(() => {
    let cancelled = false;
    catalogFetch("categories/tree").then((res) => {
      if (cancelled) return;
      if (!res.ok) notify.error("Categories couldn't be loaded. Please refresh.");
      setCategories(res.ok ? withPaths(flattenCategoryTree(res.data)) : []);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const searchCategories = useCallback(
    async (query) => {
      const q = query.toLowerCase();
      return (categories ?? []).filter((c) => !q || c.label.toLowerCase().includes(q)).slice(0, 50);
    },
    [categories],
  );

  const searchProducts = useCallback(
    async (query) => {
      const params = new URLSearchParams({ page_size: "20" });
      if (query) params.set("search", query);
      const res = await catalogFetch(`products?${params.toString()}`);
      return res.ok
        ? (res.data.results ?? []).map((p) => ({
            id: p.id,
            label: p.name,
            hint: [p.sku, formatPrice(p.effective_price ?? p.regular_price, currencySymbol), stockText(p)].filter(Boolean).join(" · "),
            image: p.feature_image,
          }))
        : [];
    },
    [currencySymbol],
  );

  function validate() {
    if (!v.name.trim()) return "Give the discount a name.";
    if (!MONEY.test(v.value.trim()) || Number(v.value) <= 0) return "The discount value must be a number greater than 0.";
    if (percentage && Number(v.value) > 100) return "A percentage can't be more than 100.";
    if (!v.start_date || !v.end_date) return "Choose both a start date and an end date.";
    const start = joinStoreDateTime(v.start_date, v.start_time);
    const end = joinStoreDateTime(v.end_date, v.end_time);
    if (end <= start) return "The end must be after the start.";
    if (v.target_type === "category" && !category) return "Choose a category.";
    if (v.target_type === "products" && products.length === 0) return "Choose at least one product.";
    return null;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting) return;
    const problem = validate();
    if (problem) return notify.error(problem);

    const body = {
      name: v.name.trim(),
      kind: v.kind,
      value: v.value.trim(),
      target_type: v.target_type,
      category_id: v.target_type === "category" ? category.id : null,
      product_ids: v.target_type === "products" ? products.map((p) => p.id) : [],
      starts_at: joinStoreDateTime(v.start_date, v.start_time),
      ends_at: joinStoreDateTime(v.end_date, v.end_time),
      is_active: v.is_active,
    };
    setSubmitting(true);
    const res = await discountFetch(isEdit ? `/${discount.id}` : "", { method: isEdit ? "PATCH" : "POST", body });
    if (!res.ok) {
      setSubmitting(false);
      return notify.error(errorText(res, isEdit ? "Unable to update the discount. Please try again." : "Unable to create the discount. Please try again."));
    }
    notify.success(isEdit ? "Discount updated successfully." : "Discount created successfully.");
    router.push("/dashboard/admin/discounts");
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-6">
      <Section title="Discount">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Field id="df-name" label="Discount name" required hint="For your team, e.g. “Summer Sale”. Customers see the reduced price.">
              <input id="df-name" type="text" maxLength={120} value={v.name} onChange={(e) => set("name")(e.target.value)} placeholder="Summer Sale" className={INPUT} />
            </Field>
          </div>
          <Field id="df-kind" label="Discount type" required>
            <select id="df-kind" value={v.kind} onChange={(e) => set("kind")(e.target.value)} className={INPUT}>
              {DISCOUNT_KINDS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </select>
          </Field>
          <Field
            id="df-value"
            label="Discount value"
            required
            hint={percentage ? "Percent off the regular price, up to 100." : "Taka off the regular price; it can't be more than the price of any product it covers."}
          >
            <div className="relative">
              <input
                id="df-value"
                type="number"
                inputMode="decimal"
                min="0"
                max={percentage ? 100 : undefined}
                step="0.01"
                value={v.value}
                onChange={(e) => set("value")(e.target.value)}
                placeholder={percentage ? "20" : "500"}
                className={`${INPUT} w-full pr-10`}
              />
              <span className="showcase-muted pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm" aria-hidden="true">
                {percentage ? "%" : currencySymbol}
              </span>
            </div>
          </Field>
        </div>
      </Section>

      <Section
        title="Applies To"
        description={
          v.target_type === "category"
            ? "Every product in the category, including its sub-categories — products added to it later too."
            : "Only the products you choose. A product discount takes priority over a category discount."
        }
      >
        <div className="flex flex-col gap-4">
          <div role="radiogroup" aria-label="Target type" className="flex flex-wrap gap-2">
            {DISCOUNT_TARGETS.map((t) => (
              <button
                key={t.value}
                type="button"
                role="radio"
                aria-checked={v.target_type === t.value}
                onClick={() => set("target_type")(t.value)}
                className={`rounded-full px-4 py-2 text-sm font-medium ${v.target_type === t.value ? "auth-btn auth-btn--primary" : "auth-btn auth-btn--outline"}`}
              >
                {t.label}
              </button>
            ))}
          </div>

          {v.target_type === "category" ? (
            <div className="max-w-xl">
              <SearchPicker
                id="df-category"
                label="Target category"
                placeholder={categories === null ? "Loading categories..." : "Search categories..."}
                search={searchCategories}
                value={category}
                onChange={setCategory}
                required
                disabled={categories === null}
              />
            </div>
          ) : (
            <DualListPicker id="df-products" label="Products" onSearch={searchProducts} chosen={products} onChange={setProducts} showImages allText="No products chosen yet." />
          )}
        </div>
      </Section>

      <Section title="Schedule" description="In the store's time zone. The discount applies only between the start and the end; afterwards prices go back to normal on their own.">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <DateTime id="df-start" label="Start" date={v.start_date} time={v.start_time} onDate={set("start_date")} onTime={set("start_time")} />
          <DateTime id="df-end" label="End" date={v.end_date} time={v.end_time} onDate={set("end_date")} onTime={set("end_time")} />
          <label htmlFor="df-active" className="flex cursor-pointer items-start gap-2.5 text-sm sm:col-span-2">
            <input id="df-active" type="checkbox" checked={v.is_active} onChange={(e) => set("is_active")(e.target.checked)} className="form-check mt-0.5 h-4 w-4 shrink-0" />
            <span>
              Active
              <span className="showcase-muted block text-xs">Switch off to stop the discount at any time; it stays in the list.</span>
            </span>
          </label>
        </div>
      </Section>

      <div className="flex flex-wrap items-center justify-end gap-3">
        <Link href="/dashboard/admin/discounts" className="auth-btn auth-btn--outline rounded-full px-6 py-2.5 text-sm font-medium">
          Cancel
        </Link>
        <button type="submit" disabled={submitting} aria-busy={submitting} className="auth-btn auth-btn--primary rounded-full px-6 py-2.5 text-sm font-medium">
          {submitting ? (isEdit ? "Saving..." : "Creating...") : isEdit ? "Save Changes" : "Create Discount"}
        </button>
      </div>
    </form>
  );
}
