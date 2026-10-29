"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { notify } from "@/lib/notify";
import formatPrice from "@/lib/formatPrice";
import { catalogFetch, errorText, joinStoreDateTime, splitStoreDateTime } from "@/lib/productAdmin";
import { flattenCategoryTree } from "@/lib/categoryAdmin";
import { DISCOUNT_KIND_FIELDS, DISCOUNT_KINDS, DISCOUNT_TARGETS, discountFetch, isProductKind } from "@/lib/discountAdmin";
import DualListPicker from "../coupons/DualListPicker";

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

// A labelled checkbox, matching the "Active" control's look.
function Toggle({ id, checked, onChange, label, hint }) {
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
  const num = (value) => (value === null || value === undefined ? "" : String(Number(value)));
  return {
    name: d?.name ?? "",
    kind: d?.kind ?? "percentage",
    value: d?.value != null ? String(Number(d.value)) : "",
    min_quantity: d?.min_quantity != null ? String(d.min_quantity) : "",
    percent_off: num(d?.percent_off),
    free_quantity: d?.free_quantity != null ? String(d.free_quantity) : "",
    bundle_price: num(d?.bundle_price),
    same_product_group: d?.same_product_group ?? false,
    allow_repeat: d?.allow_repeat ?? true,
    target_type: d?.target_type ?? "category",
    start_date: start.date,
    start_time: start.time || "00:00",
    end_date: end.date,
    end_time: end.time || "23:59",
    is_active: d?.is_active ?? true,
  };
}

// Add / Edit Discount over /admin/discounts/ (apps.discounts — IsAdmin). Product kinds change a single product's price
// (effective_price); the other kinds are cart offers that the backend works out over the whole cart (a coupon, by
// contrast, applies after them). The backend is the authority on everything; the checks here only catch the obvious
// first. The chosen type decides which configuration fields are shown — and sent.
export default function DiscountForm({ discount = null, currencySymbol }) {
  const router = useRouter();
  const isEdit = Boolean(discount);
  const [v, setV] = useState(() => initial(discount));
  const [chosenCategories, setChosenCategories] = useState(() => (discount?.categories ?? []).map((c) => ({ id: c.id, label: c.name })));
  const [products, setProducts] = useState(() =>
    (discount?.products ?? []).map((p) => ({ id: p.id, label: p.name, hint: p.sku, image: p.feature_image })),
  );
  const [categories, setCategories] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const set = (name) => (value) => setV((s) => ({ ...s, [name]: value }));
  const percentage = v.kind === "percentage";
  const productKind = isProductKind(v.kind);
  const fields = DISCOUNT_KIND_FIELDS[v.kind] ?? {};

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
    if (!v.start_date || !v.end_date) return "Choose both a start date and an end date.";
    const start = joinStoreDateTime(v.start_date, v.start_time);
    const end = joinStoreDateTime(v.end_date, v.end_time);
    if (end <= start) return "The end must be after the start.";
    if (v.target_type === "category" && chosenCategories.length === 0) return "Choose at least one category.";
    if (v.target_type === "products" && products.length === 0) return "Choose at least one product.";

    if (productKind) {
      if (!MONEY.test(v.value.trim()) || Number(v.value) <= 0) return "The discount value must be a number greater than 0.";
      if (percentage && Number(v.value) > 100) return "A percentage can't be more than 100.";
    } else {
      if (fields.minQuantity && (!WHOLE.test(v.min_quantity) || Number(v.min_quantity) < 1)) return "The minimum quantity must be a whole number of at least 1.";
      if (fields.percentOff && (!MONEY.test(v.percent_off.trim()) || Number(v.percent_off) <= 0 || Number(v.percent_off) > 100)) return "The percentage must be more than 0 and up to 100.";
      if (fields.freeQuantity && (!WHOLE.test(v.free_quantity) || Number(v.free_quantity) < 1)) return "The free quantity must be a whole number of at least 1.";
      if (fields.bundlePrice && (!MONEY.test(v.bundle_price.trim()) || Number(v.bundle_price) <= 0)) return "The bundle price must be a number greater than 0.";
    }
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
      target_type: v.target_type,
      category_ids: v.target_type === "category" ? chosenCategories.map((c) => c.id) : [],
      product_ids: v.target_type === "products" ? products.map((p) => p.id) : [],
      starts_at: joinStoreDateTime(v.start_date, v.start_time),
      ends_at: joinStoreDateTime(v.end_date, v.end_time),
      is_active: v.is_active,
    };
    if (productKind) {
      body.value = v.value.trim();
    } else {
      body.allow_repeat = v.allow_repeat;
      if (fields.minQuantity) body.min_quantity = Number(v.min_quantity);
      if (fields.percentOff) body.percent_off = v.percent_off.trim();
      if (fields.freeQuantity) body.free_quantity = Number(v.free_quantity);
      if (fields.bundlePrice) body.bundle_price = v.bundle_price.trim();
      if (fields.sameProductGroup) body.same_product_group = v.same_product_group;
    }

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
            <Field id="df-name" label="Discount name" required hint="Shown to customers as the offer's name, e.g. “Summer Sale”.">
              <input id="df-name" type="text" maxLength={120} value={v.name} onChange={(e) => set("name")(e.target.value)} placeholder="Summer Sale" className={INPUT} />
            </Field>
          </div>
          <Field id="df-kind" label="Discount type" required hint="Each type shows only the settings it needs.">
            <select id="df-kind" value={v.kind} onChange={(e) => set("kind")(e.target.value)} className={INPUT}>
              <optgroup label="Product price">
                {DISCOUNT_KINDS.filter((k) => k.group === "price").map((k) => (
                  <option key={k.value} value={k.value}>
                    {k.label}
                  </option>
                ))}
              </optgroup>
              <optgroup label="Cart offers">
                {DISCOUNT_KINDS.filter((k) => k.group === "cart").map((k) => (
                  <option key={k.value} value={k.value}>
                    {k.label}
                  </option>
                ))}
              </optgroup>
            </select>
          </Field>

          {productKind ? (
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
          ) : (
            <>
              {fields.minQuantity && (
                <Field id="df-min-qty" label="Minimum quantity" required hint="How many eligible items are needed to form one offer (X).">
                  <input id="df-min-qty" type="number" inputMode="numeric" min="1" step="1" value={v.min_quantity} onChange={(e) => set("min_quantity")(e.target.value)} placeholder="3" className={INPUT} />
                </Field>
              )}
              {fields.percentOff && (
                <Field id="df-percent-off" label="Discount percentage" required hint="Percent off the qualifying units (Y%), up to 100.">
                  <div className="relative">
                    <input id="df-percent-off" type="number" inputMode="decimal" min="0" max="100" step="0.01" value={v.percent_off} onChange={(e) => set("percent_off")(e.target.value)} placeholder="20" className={`${INPUT} w-full pr-10`} />
                    <span className="showcase-muted pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm" aria-hidden="true">
                      %
                    </span>
                  </div>
                </Field>
              )}
              {fields.freeQuantity && (
                <Field id="df-free-qty" label="Free quantity" required hint="How many of the group's cheapest units are free (Y).">
                  <input id="df-free-qty" type="number" inputMode="numeric" min="1" step="1" value={v.free_quantity} onChange={(e) => set("free_quantity")(e.target.value)} placeholder="1" className={INPUT} />
                </Field>
              )}
              {fields.bundlePrice && (
                <Field id="df-bundle-price" label="Bundle price" required hint="The total payable price for one group of the required quantity (৳Y). Never makes the group cost more.">
                  <div className="relative">
                    <input id="df-bundle-price" type="number" inputMode="decimal" min="0" step="0.01" value={v.bundle_price} onChange={(e) => set("bundle_price")(e.target.value)} placeholder="1000" className={`${INPUT} w-full pr-10`} />
                    <span className="showcase-muted pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm" aria-hidden="true">
                      {currencySymbol}
                    </span>
                  </div>
                </Field>
              )}
            </>
          )}
        </div>

        {!productKind && (
          <div className="mt-4 flex flex-col gap-3 border-t pt-4">
            {fields.sameProductGroup && (
              <Toggle
                id="df-same-product-group"
                checked={v.same_product_group}
                onChange={set("same_product_group")}
                label="Free item must be the same product"
                hint="On: each group's free unit comes from the same eligible product as its paid ones."
              />
            )}
            {fields.allowRepeat && (
              <Toggle
                id="df-allow-repeat"
                checked={v.allow_repeat}
                onChange={set("allow_repeat")}
                label="Repeat for every complete group"
                hint="On: buying twice the required quantity applies the offer twice."
              />
            )}
          </div>
        )}
      </Section>

      <Section
        title="Applies To"
        description={
          v.target_type === "category"
            ? "Every product in the chosen categories, including their sub-categories — products added to them later too."
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
            <DualListPicker
              id="df-categories"
              label="Categories"
              options={categories ?? []}
              chosen={chosenCategories}
              onChange={setChosenCategories}
              allText={categories === null ? "Loading categories..." : "No categories chosen yet."}
            />
          ) : (
            <DualListPicker id="df-products" label="Products" onSearch={searchProducts} chosen={products} onChange={setProducts} showImages allText="No products chosen yet." />
          )}
        </div>
      </Section>

      <Section title="Schedule" description="In the store's time zone. The discount applies only between the start and the end; afterwards it stops on its own. The backend checks the window, not the browser.">
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
