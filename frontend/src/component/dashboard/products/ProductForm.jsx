"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FiPlus, FiTrash2 } from "react-icons/fi";
import { notify } from "@/lib/notify";
import {
  GENDERS,
  PRODUCT_STATUS,
  SIZE_UNITS,
  SKIN_TYPES,
  STOCK_STATUS,
  catalogFetch,
  catalogFetchAll,
  errorText,
  joinStoreDateTime,
  splitStoreDateTime,
} from "@/lib/productAdmin";
import TagSelector from "./TagSelector";
import { GalleryInput, SingleImageInput } from "./ImageInputs";
import { useStaffHref } from "@/lib/staffPaths";

// --- small layout helpers ------------------------------------------------------------------------------------------

function Section({ title, description, children }) {
  return (
    <section className="dashboard-card rounded-2xl p-5 sm:p-6">
      <h2 className="custom-font text-lg">{title}</h2>
      {description && <p className="showcase-muted mt-1 text-xs">{description}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Field({ id, label, required, optional, hint, wide, children }) {
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${wide ? "sm:col-span-2" : ""}`}>
      <label htmlFor={id} className="text-sm font-medium">
        {label} {required && <span aria-hidden="true">*</span>}
        {optional && <span className="showcase-muted font-normal">(Optional)</span>}
      </label>
      {children}
      {hint && <p className="showcase-muted text-xs">{hint}</p>}
    </div>
  );
}

function Toggle({ id, label, checked, onChange, hint }) {
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

const INPUT = "checkout-input rounded-lg px-3 py-2.5 text-sm";

// --- mapping between the backend's product/variant JSON and form state ---------------------------------------------

const str = (v) => (v === null || v === undefined ? "" : String(v));
const numOrNull = (v) => (String(v).trim() === "" ? null : String(v).trim());
const blankImage = { url: null, file: null, removed: false };

function initialValues(p) {
  const start = splitStoreDateTime(p?.sale_start_at);
  const end = splitStoreDateTime(p?.sale_end_at);
  const primary = p?.categories?.find((c) => c.is_primary);
  return {
    name: str(p?.name),
    slug: str(p?.slug),
    short_description: str(p?.short_description),
    full_description: str(p?.full_description),
    user_guide: str(p?.user_guide),
    brand: str(p?.brand),
    category_ids: p?.categories?.map((c) => c.id) ?? [],
    primary_category_id: primary?.id ?? null,
    tag_ids: p?.tags?.map((t) => t.id) ?? [],
    regular_price: str(p?.regular_price),
    discount_price: str(p?.discount_price),
    sale_start_date: start.date,
    sale_start_time: start.time,
    sale_end_date: end.date,
    sale_end_time: end.time,
    sku: str(p?.sku),
    manage_stock: p?.manage_stock ?? true,
    stock_quantity: str(p?.stock_quantity ?? 0),
    stock_status: p?.stock_status ?? "in_stock",
    skin_type: p?.skin_type ?? [],
    key_ingredients: (p?.key_ingredients ?? []).join("\n"),
    ingredients: str(p?.ingredients),
    size_value: str(p?.size_value),
    size_unit: str(p?.size_unit),
    country_of_origin: str(p?.country_of_origin),
    manufacture_date: str(p?.manufacture_date),
    expiry_date: str(p?.expiry_date),
    gender: str(p?.gender),
    is_featured: p?.is_featured ?? false,
    is_new_arrival: p?.is_new_arrival ?? false,
    is_bestseller: p?.is_bestseller ?? false,
    status: p?.status ?? "draft",
    meta_title: str(p?.meta_title),
    meta_description: str(p?.meta_description),
  };
}

function variantState(v) {
  return {
    key: v ? `saved-${v.id}` : `new-${crypto.randomUUID()}`,
    id: v?.id ?? null,
    sku: str(v?.sku),
    options: Object.fromEntries((v?.attribute_values ?? []).map((av) => [av.attribute_id, av.value])), // attribute id -> typed value
    regular_price: str(v?.regular_price),
    discount_price: str(v?.discount_price),
    stock_quantity: str(v?.stock_quantity ?? 0),
    saved_stock: v?.stock_quantity ?? 0,
    manage_stock: v?.manage_stock ?? true,
    is_active: v?.is_active ?? true,
    image: { ...blankImage, url: v?.image ?? null },
  };
}

// The product's writable fields (apps.catalog.serializers_product.AdminProductSerializer) from form state. Stock
// quantity is NOT here: it is read-only on that serializer and only changes through POST /admin/stock/adjust/.
function productPayload(v) {
  return {
    name: v.name.trim(),
    short_description: v.short_description,
    full_description: v.full_description,
    user_guide: v.user_guide,
    brand: v.brand ? Number(v.brand) : null,
    category_ids: v.category_ids,
    primary_category_id: v.category_ids.length ? (v.primary_category_id ?? v.category_ids[0]) : null,
    tag_ids: v.tag_ids,
    regular_price: v.regular_price.trim(),
    discount_price: numOrNull(v.discount_price),
    sale_start_at: joinStoreDateTime(v.sale_start_date, v.sale_start_time),
    sale_end_at: joinStoreDateTime(v.sale_end_date, v.sale_end_time),
    sku: v.sku.trim(),
    manage_stock: v.manage_stock,
    stock_status: v.stock_status,
    skin_type: v.skin_type,
    key_ingredients: v.key_ingredients.split("\n").map((s) => s.trim()).filter(Boolean),
    ingredients: v.ingredients,
    size_value: numOrNull(v.size_value),
    size_unit: v.size_unit,
    country_of_origin: v.country_of_origin.trim(),
    manufacture_date: v.manufacture_date || null,
    expiry_date: v.expiry_date || null,
    gender: v.gender,
    is_featured: v.is_featured,
    is_new_arrival: v.is_new_arrival,
    is_bestseller: v.is_bestseller,
    status: v.status,
    meta_title: v.meta_title,
    meta_description: v.meta_description,
  };
}

// Multipart for the create request (the feature image is required, so it must travel with the product). DRF reads
// "" as null for nullable fields and repeated keys as a list; an empty list is simply left out (the default).
function toFormData(payload, files) {
  const fd = new FormData();
  for (const [key, value] of Object.entries(payload)) {
    if (Array.isArray(value)) value.forEach((item) => fd.append(key, String(item)));
    else fd.append(key, value === null ? "" : String(value));
  }
  for (const [key, file] of Object.entries(files)) if (file) fd.append(key, file);
  return fd;
}

// Mirrors the backend's own rules (model constraints + serializer validate) so obvious mistakes are caught before
// any request; the backend stays the final authority and its message is shown if it still refuses.
function validate(v, feature, variants, isEdit) {
  if (!v.name.trim()) return "Name is required.";
  if (!v.sku.trim()) return "SKU is required.";
  const regular = Number(v.regular_price);
  if (!v.regular_price.trim() || !Number.isFinite(regular) || regular <= 0) return "Regular price must be a number greater than 0.";
  if (v.discount_price.trim()) {
    const discount = Number(v.discount_price);
    if (!Number.isFinite(discount) || discount < 0) return "Discount price must be a valid amount.";
    if (discount >= regular) return "Discount price must be less than the regular price.";
  }
  if ((v.sale_start_time && !v.sale_start_date) || (v.sale_end_time && !v.sale_end_date)) return "Pick a date for the sale time you entered.";
  const start = joinStoreDateTime(v.sale_start_date, v.sale_start_time);
  const end = joinStoreDateTime(v.sale_end_date, v.sale_end_time);
  if (start && end && end < start) return "Sale end can't be earlier than sale start.";
  if (!isEdit && !feature.file) return "Feature image is required.";
  if (v.manage_stock && !variants.length && !/^\d+$/.test(v.stock_quantity.trim())) return "Stock quantity must be a whole number, 0 or more.";
  if (v.size_value.trim() && !(Number(v.size_value) >= 0)) return "Size value must be a valid number.";
  for (const [i, variant] of variants.entries()) {
    const n = `Variant ${i + 1}`;
    if (!variant.sku.trim()) return `${n}: SKU is required.`;
    const vr = variant.regular_price.trim() ? Number(variant.regular_price) : null;
    const vd = variant.discount_price.trim() ? Number(variant.discount_price) : null;
    if ((vr !== null && !(vr >= 0)) || (vd !== null && !(vd >= 0))) return `${n}: prices must be valid amounts.`;
    if (vr !== null && vd !== null && vd >= vr) return `${n}: discount price must be less than its regular price.`;
    if (variant.manage_stock && !/^\d+$/.test(variant.stock_quantity.trim())) return `${n}: stock quantity must be a whole number, 0 or more.`;
  }
  const skus = [v.sku.trim(), ...variants.map((x) => x.sku.trim())].map((s) => s.toLowerCase());
  if (new Set(skus).size !== skus.length) return "Each SKU must be different (the product and every variant).";
  return null;
}

// --- category picker ---------------------------------------------------------------------------------------------

function CategoryTree({ nodes, depth = 0, selected, primaryId, onToggle, onPrimary }) {
  return (
    <ul className={depth ? "ml-5 border-l pl-3 category-tree__branch" : ""}>
      {nodes.map((node) => {
        const checked = selected.includes(node.id);
        return (
          <li key={node.id} className="py-1">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <label className="flex cursor-pointer items-center gap-2 text-sm">
                <input type="checkbox" checked={checked} onChange={() => onToggle(node.id)} className="form-check h-4 w-4" />
                <span className={node.is_active ? "" : "showcase-muted"}>
                  {node.name}
                  {!node.is_active && " (inactive)"}
                </span>
              </label>
              {checked && (
                <label className="showcase-muted flex cursor-pointer items-center gap-1.5 text-xs">
                  <input type="radio" name="primary-category" checked={primaryId === node.id} onChange={() => onPrimary(node.id)} className="form-check h-3.5 w-3.5" />
                  Primary
                </label>
              )}
            </div>
            {node.children?.length > 0 && (
              <CategoryTree nodes={node.children} depth={depth + 1} selected={selected} primaryId={primaryId} onToggle={onToggle} onPrimary={onPrimary} />
            )}
          </li>
        );
      })}
    </ul>
  );
}

// --- the form ----------------------------------------------------------------------------------------------------

// Add / Edit Product for the CCE dashboard: one form for both, over the EXISTING catalog admin API (see
// app/api/admin/catalog). Saving is a short sequence of calls to the endpoints that already own each piece:
// the product itself, its gallery (images/ + images/reorder/), its variants (variants/), and stock through
// stock/adjust/ so every quantity change is logged as a StockMovement like any other adjustment.
export default function ProductForm({ product = null, savedVariants = [] }) {
  const to = useStaffHref();
  const router = useRouter();
  const isEdit = Boolean(product);

  const [values, setValues] = useState(() => initialValues(product));
  const [feature, setFeature] = useState({ ...blankImage, url: product?.feature_image ?? null });
  const [ogImage, setOgImage] = useState({ ...blankImage, url: product?.og_image ?? null });
  const [gallery, setGallery] = useState(() => (product?.images ?? []).map((img) => ({ key: `saved-${img.id}`, id: img.id, url: img.image })));
  const [variants, setVariants] = useState(() => savedVariants.map(variantState));

  const [lookups, setLookups] = useState({ loading: true, brands: [], categories: [], tags: [], attributes: [] });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [brands, tree, tags, attributes] = await Promise.all([
        catalogFetchAll("brands?ordering=name"),
        catalogFetch("categories/tree"),
        catalogFetchAll("tags?ordering=name"),
        catalogFetchAll("product-attributes"),
      ]);
      if (cancelled) return;
      if (!brands || !tree.ok || !tags || !attributes) notify.error("Some options (brands, categories, tags or variant options) couldn't be loaded. Please refresh.");
      setLookups({ loading: false, brands: brands ?? [], categories: tree.ok ? tree.data : [], tags: tags ?? [], attributes: attributes ?? [] });
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const set = (name) => (value) => setValues((v) => ({ ...v, [name]: value }));
  const onInput = (name) => (e) => set(name)(e.target.value);
  const hasVariants = variants.length > 0;

  function toggleCategory(id) {
    setValues((v) => {
      const selected = v.category_ids.includes(id) ? v.category_ids.filter((c) => c !== id) : [...v.category_ids, id];
      const primary = selected.includes(v.primary_category_id) ? v.primary_category_id : (selected[0] ?? null);
      return { ...v, category_ids: selected, primary_category_id: primary };
    });
  }

  function toggleSkinType(value) {
    setValues((v) => ({ ...v, skin_type: v.skin_type.includes(value) ? v.skin_type.filter((s) => s !== value) : [...v.skin_type, value] }));
  }

  const updateVariant = (key, patch) => setVariants((list) => list.map((x) => (x.key === key ? { ...x, ...patch } : x)));

  // A variant's typed option (e.g. Size "75ml") as an AttributeValue id: an existing value matched case-insensitively
  // (the backend treats those as the same value), otherwise a new one created via POST /admin/attribute-values/.
  // `known` is updated in place so two variants typing the same new value create it once.
  async function resolveOptionIds(options, known) {
    const ids = [];
    for (const attr of known) {
      const text = (options[attr.id] ?? "").trim();
      if (!text) continue;
      let match = attr.values.find((val) => val.value.toLowerCase() === text.toLowerCase());
      if (!match) {
        const res = await catalogFetch("attribute-values", { method: "POST", body: { attribute: attr.id, value: text } });
        if (!res.ok) return { error: `${attr.name} "${text}": ${errorText(res, "couldn't be added.")}` };
        match = res.data;
        attr.values.push(match);
      }
      ids.push(match.id);
    }
    return { ids };
  }

  // --- saving, step by step (stops at the first refusal and says which step failed) ---

  async function adjustStock(target, desired, saved) {
    const delta = Number(desired) - Number(saved);
    if (!delta) return { ok: true };
    return catalogFetch("stock/adjust", {
      method: "POST",
      body: { ...target, quantity_change: delta, reason: "manual", note: "Set from the product form" },
    });
  }

  async function saveGallery(productId) {
    const originalIds = (product?.images ?? []).map((i) => i.id);
    const keptIds = new Set(gallery.filter((i) => i.id).map((i) => i.id));
    for (const id of originalIds.filter((i) => !keptIds.has(i))) {
      const res = await catalogFetch(`products/${productId}/images/${id}`, { method: "DELETE" });
      if (!res.ok && res.status !== 404) return errorText(res, "Unable to remove a product image.");
    }
    const order = [];
    for (const item of gallery) {
      if (item.id) {
        order.push(item.id);
        continue;
      }
      const fd = new FormData();
      fd.append("image", item.file);
      const res = await catalogFetch(`products/${productId}/images`, { method: "POST", body: fd });
      if (!res.ok) return errorText(res, "Unable to upload a product image.");
      order.push(res.data.id);
      // Remember it's saved, so a retry after a later failure doesn't upload it twice.
      setGallery((list) => list.map((i) => (i.key === item.key ? { key: i.key, id: res.data.id, url: res.data.image } : i)));
    }
    const unchanged = order.length === originalIds.length && order.every((id, i) => id === originalIds[i]);
    if (order.length > 1 && !unchanged) {
      const res = await catalogFetch(`products/${productId}/images/reorder`, { method: "POST", body: order });
      if (!res.ok) return errorText(res, "Unable to save the image order.");
    }
    return null;
  }

  async function saveVariants(productId) {
    const known = lookups.attributes.map((a) => ({ ...a, values: [...a.values] }));
    const keptIds = new Set(variants.filter((x) => x.id).map((x) => x.id));
    for (const saved of savedVariants.filter((x) => !keptIds.has(x.id))) {
      const res = await catalogFetch(`products/${productId}/variants/${saved.id}`, { method: "DELETE" });
      if (!res.ok && res.status !== 404) return `Removing variant ${saved.sku}: ${errorText(res, "the server refused.")}`;
    }
    for (const [i, variant] of variants.entries()) {
      const label = `Variant ${i + 1}`;
      const resolved = await resolveOptionIds(variant.options, known);
      if (resolved.error) {
        setLookups((l) => ({ ...l, attributes: known }));
        return `${label}: ${resolved.error}`;
      }
      const payload = {
        sku: variant.sku.trim(),
        attribute_value_ids: resolved.ids,
        regular_price: numOrNull(variant.regular_price),
        discount_price: numOrNull(variant.discount_price),
        manage_stock: variant.manage_stock,
        is_active: variant.is_active,
        ...(variant.image.removed && !variant.image.file ? { image: null } : {}),
      };
      const res = variant.id
        ? await catalogFetch(`products/${productId}/variants/${variant.id}`, { method: "PATCH", body: payload })
        : await catalogFetch(`products/${productId}/variants`, { method: "POST", body: payload });
      if (!res.ok) return `${label}: ${errorText(res, "the server refused it.")}`;
      const saved = res.data;
      if (variant.image.file) {
        const fd = new FormData();
        fd.append("image", variant.image.file);
        const img = await catalogFetch(`products/${productId}/variants/${saved.id}`, { method: "PATCH", body: fd });
        if (!img.ok) return `${label} image: ${errorText(img, "upload failed.")}`;
      }
      if (variant.manage_stock) {
        const stock = await adjustStock({ variant_id: saved.id }, variant.stock_quantity.trim(), saved.stock_quantity);
        if (!stock.ok) return `${label} stock: ${errorText(stock, "couldn't be updated.")}`;
      }
      // Now saved: a retry after a later failure updates this variant instead of creating it again.
      setLookups((l) => ({ ...l, attributes: known }));
      updateVariant(variant.key, { id: saved.id, saved_stock: variant.manage_stock ? Number(variant.stock_quantity) : saved.stock_quantity, image: { ...variant.image, file: null, removed: false } });
    }
    return null;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting) return;
    const problem = validate(values, feature, variants, isEdit);
    if (problem) return notify.error(problem);

    setSubmitting(true);
    const payload = productPayload(values);
    // A blank slug is generated from the name; an unchanged one isn't re-sent, so it isn't marked hand-set.
    const slug = values.slug.trim();
    if (isEdit ? slug !== product.slug : slug) payload.slug = slug;

    let saved;
    if (isEdit) {
      const res = await catalogFetch(`products/${product.id}`, { method: "PATCH", body: payload });
      if (!res.ok) {
        setSubmitting(false);
        return notify.error(errorText(res, "Unable to update the product. Please try again."));
      }
      saved = res.data;
      if (feature.file || ogImage.file || ogImage.removed) {
        const fd = new FormData();
        if (feature.file) fd.append("feature_image", feature.file);
        if (ogImage.file) fd.append("og_image", ogImage.file);
        else if (ogImage.removed) fd.append("og_image", "");
        const img = await catalogFetch(`products/${product.id}`, { method: "PATCH", body: fd });
        if (!img.ok) {
          setSubmitting(false);
          return notify.error(errorText(img, "The product was saved, but its images couldn't be updated."));
        }
        saved = img.data;
      }
    } else {
      const res = await catalogFetch("products", {
        method: "POST",
        body: toFormData(payload, { feature_image: feature.file, og_image: ogImage.file }),
      });
      if (!res.ok) {
        setSubmitting(false);
        return notify.error(errorText(res, "Unable to create the product. Please try again."));
      }
      saved = res.data;
    }

    // From here the product exists: a later failure is reported, and a new product opens in Edit so a retry
    // updates it instead of creating a duplicate.
    // (Edit keeps the form as typed, with what did save marked as saved, so fixing and re-submitting finishes the job.)
    const fail = (message) => {
      setSubmitting(false);
      notify.error(`${isEdit ? "Product saved" : "Product created"}, but not everything was saved. ${message}`);
      if (!isEdit) router.replace(to(`/dashboard/CCE/products/${saved.id}`));
      else {
        setFeature({ ...blankImage, url: saved.feature_image });
        setOgImage({ ...blankImage, url: saved.og_image });
      }
    };

    if (!hasVariants && values.manage_stock) {
      const stock = await adjustStock({ product_id: saved.id }, values.stock_quantity.trim(), saved.stock_quantity);
      if (!stock.ok) return fail(`Stock: ${errorText(stock, "couldn't be updated.")}`);
    }
    const galleryError = await saveGallery(saved.id);
    if (galleryError) return fail(galleryError);
    const variantError = await saveVariants(saved.id);
    if (variantError) return fail(variantError);
    if (saved.has_variants !== hasVariants) {
      const flag = await catalogFetch(`products/${saved.id}`, { method: "PATCH", body: { has_variants: hasVariants } });
      if (!flag.ok) return fail(errorText(flag, "Couldn't update the product's variant setting."));
    }

    notify.success(isEdit ? "Product updated successfully." : "Product created successfully.");
    router.push(to("/dashboard/CCE/products"));
    router.refresh();
  }

  const v = values;
  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-6">
      <Section title="Basic Information">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field id="pf-name" label="Name" required>
            <input id="pf-name" type="text" maxLength={200} value={v.name} onChange={onInput("name")} className={INPUT} />
          </Field>
          <Field id="pf-slug" label="Slug" optional hint="Leave blank to generate it from the name.">
            <input id="pf-slug" type="text" maxLength={255} value={v.slug} onChange={onInput("slug")} className={INPUT} />
          </Field>
          <Field id="pf-short" label="Short Description" optional wide>
            <textarea id="pf-short" rows={2} maxLength={300} value={v.short_description} onChange={onInput("short_description")} className={INPUT} />
          </Field>
          <Field id="pf-full" label="Full Description" optional wide hint="Shown on the product page. HTML formatting is supported.">
            <textarea id="pf-full" rows={6} value={v.full_description} onChange={onInput("full_description")} className={INPUT} />
          </Field>
          <Field id="pf-guide" label="User Guide" optional wide hint="How to use. HTML formatting is supported.">
            <textarea id="pf-guide" rows={4} value={v.user_guide} onChange={onInput("user_guide")} className={INPUT} />
          </Field>
        </div>
      </Section>

      <Section title="Images" description="The feature image is the main photo on product cards; product images form the gallery on the product page.">
        <div className="flex flex-col gap-6">
          <SingleImageInput id="pf-feature" label="Feature Image" required value={feature} onChange={setFeature} />
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium">
              Product Images <span className="showcase-muted font-normal">(Optional)</span>
            </span>
            <GalleryInput items={gallery} onChange={setGallery} />
          </div>
        </div>
      </Section>

      <Section title="Organization">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field id="pf-status" label="Status" required>
            <select id="pf-status" value={v.status} onChange={onInput("status")} className={INPUT}>
              {PRODUCT_STATUS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
          <Field id="pf-brand" label="Brand" optional>
            <select id="pf-brand" value={v.brand} onChange={onInput("brand")} className={INPUT} disabled={lookups.loading}>
              <option value="">{lookups.loading ? "Loading brands..." : "Select Brand"}</option>
              {lookups.brands.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                  {b.is_active ? "" : " (inactive)"}
                </option>
              ))}
            </select>
          </Field>
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <span className="text-sm font-medium">
              Category <span className="showcase-muted font-normal">(Optional)</span>
            </span>
            <div className="checkout-input max-h-64 overflow-y-auto rounded-lg px-3 py-2">
              {lookups.loading ? (
                <p className="showcase-muted text-sm">Loading categories...</p>
              ) : lookups.categories.length === 0 ? (
                <p className="showcase-muted text-sm">No categories yet.</p>
              ) : (
                <CategoryTree
                  nodes={lookups.categories}
                  selected={v.category_ids}
                  primaryId={v.primary_category_id}
                  onToggle={toggleCategory}
                  onPrimary={set("primary_category_id")}
                />
              )}
            </div>
            <p className="showcase-muted text-xs">Tick a parent and/or sub-category. The primary one sets the product&apos;s breadcrumb.</p>
          </div>
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <span className="text-sm font-medium">
              Tags <span className="showcase-muted font-normal">(Optional)</span>
            </span>
            <TagSelector
              allTags={lookups.tags}
              onTagsChange={(tags) => setLookups((l) => ({ ...l, tags }))}
              selectedIds={v.tag_ids}
              onChange={set("tag_ids")}
            />
          </div>
        </div>
      </Section>

      <Section title="Pricing" description="Sale dates are in Bangladesh time. Leave them empty for a discount that always applies.">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field id="pf-regular" label="Regular Price" required>
            <input id="pf-regular" type="number" inputMode="decimal" min="0.01" step="0.01" value={v.regular_price} onChange={onInput("regular_price")} className={INPUT} />
          </Field>
          <Field id="pf-discount" label="Discount Price" optional>
            <input id="pf-discount" type="number" inputMode="decimal" min="0" step="0.01" value={v.discount_price} onChange={onInput("discount_price")} className={INPUT} />
          </Field>
          <Field id="pf-sale-start" label="Sale Start At" optional>
            <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,7.5rem)] gap-2">
              <input id="pf-sale-start" type="date" value={v.sale_start_date} onChange={onInput("sale_start_date")} className={INPUT} />
              <input type="time" aria-label="Sale start time" value={v.sale_start_time} onChange={onInput("sale_start_time")} className={INPUT} />
            </div>
          </Field>
          <Field id="pf-sale-end" label="Sale End At" optional>
            <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,7.5rem)] gap-2">
              <input id="pf-sale-end" type="date" value={v.sale_end_date} onChange={onInput("sale_end_date")} className={INPUT} />
              <input type="time" aria-label="Sale end time" value={v.sale_end_time} onChange={onInput("sale_end_time")} className={INPUT} />
            </div>
          </Field>
        </div>
      </Section>

      <Section title="Inventory">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field id="pf-sku" label="SKU" required hint="Unique across all products and variants.">
            <input id="pf-sku" type="text" maxLength={64} value={v.sku} onChange={onInput("sku")} className={INPUT} />
          </Field>
          <Field id="pf-stock-status" label="Stock Status" hint="In/out of stock follows the quantity automatically. Backorder keeps it sellable at 0.">
            <select id="pf-stock-status" value={v.stock_status} onChange={onInput("stock_status")} className={INPUT}>
              {STOCK_STATUS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
          <div className="sm:col-span-2">
            <Toggle id="pf-manage-stock" label="Manage stock" hint="Track quantity and stop selling at 0 (unless on backorder)." checked={v.manage_stock} onChange={set("manage_stock")} />
          </div>
          {hasVariants ? (
            <p className="showcase-muted text-sm sm:col-span-2">This product has variants, so stock is set on each variant below.</p>
          ) : (
            v.manage_stock && (
              <Field id="pf-stock" label="Stock Quantity" required hint={isEdit ? `Currently ${product.stock_quantity}. Changes are logged as a manual stock adjustment.` : undefined}>
                <input id="pf-stock" type="number" inputMode="numeric" min="0" step="1" value={v.stock_quantity} onChange={onInput("stock_quantity")} className={INPUT} />
              </Field>
            )
          )}
        </div>
      </Section>

      <Section title="Product Variants" description="For products sold in options (e.g. shade or size). Each variant has its own SKU and stock; leave a price empty to use the product's price.">
        <div className="flex flex-col gap-4">
          {variants.map((variant, index) => (
            <fieldset key={variant.key} aria-labelledby={`${variant.key}-title`} className="variant-card rounded-xl p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <h3 id={`${variant.key}-title`} className="text-sm font-semibold">
                  Variant {index + 1}
                </h3>
                <button
                  type="button"
                  onClick={() => setVariants((list) => list.filter((x) => x.key !== variant.key))}
                  className="auth-error inline-flex items-center gap-1.5 text-xs font-medium"
                >
                  <FiTrash2 className="h-3.5 w-3.5" aria-hidden="true" /> Remove Variant
                </button>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {lookups.attributes.map((attr) => (
                  <Field key={attr.id} id={`${variant.key}-attr-${attr.id}`} label={attr.name} optional>
                    <input
                      id={`${variant.key}-attr-${attr.id}`}
                      type="text"
                      maxLength={60}
                      placeholder={attr.values[0] ? `e.g. ${attr.values[0].value}` : undefined}
                      value={variant.options[attr.id] ?? ""}
                      onChange={(e) => updateVariant(variant.key, { options: { ...variant.options, [attr.id]: e.target.value } })}
                      className={INPUT}
                    />
                  </Field>
                ))}
                <Field id={`${variant.key}-sku`} label="SKU" required>
                  <input id={`${variant.key}-sku`} type="text" maxLength={64} value={variant.sku} onChange={(e) => updateVariant(variant.key, { sku: e.target.value })} className={INPUT} />
                </Field>
                <Field id={`${variant.key}-regular`} label="Regular Price" optional>
                  <input
                    id={`${variant.key}-regular`}
                    type="number"
                    inputMode="decimal"
                    min="0"
                    step="0.01"
                    placeholder={v.regular_price || "Product price"}
                    value={variant.regular_price}
                    onChange={(e) => updateVariant(variant.key, { regular_price: e.target.value })}
                    className={INPUT}
                  />
                </Field>
                <Field id={`${variant.key}-discount`} label="Discount Price" optional>
                  <input
                    id={`${variant.key}-discount`}
                    type="number"
                    inputMode="decimal"
                    min="0"
                    step="0.01"
                    value={variant.discount_price}
                    onChange={(e) => updateVariant(variant.key, { discount_price: e.target.value })}
                    className={INPUT}
                  />
                </Field>
                {variant.manage_stock && (
                  <Field id={`${variant.key}-stock`} label="Stock Quantity" required hint={variant.id ? `Currently ${variant.saved_stock}.` : undefined}>
                    <input
                      id={`${variant.key}-stock`}
                      type="number"
                      inputMode="numeric"
                      min="0"
                      step="1"
                      value={variant.stock_quantity}
                      onChange={(e) => updateVariant(variant.key, { stock_quantity: e.target.value })}
                      className={INPUT}
                    />
                  </Field>
                )}
                <div className="flex flex-col justify-center gap-2">
                  <Toggle id={`${variant.key}-manage`} label="Manage Stock" checked={variant.manage_stock} onChange={(checked) => updateVariant(variant.key, { manage_stock: checked })} />
                  <Toggle id={`${variant.key}-active`} label="Is Active" checked={variant.is_active} onChange={(checked) => updateVariant(variant.key, { is_active: checked })} />
                </div>
                <div className="sm:col-span-2 lg:col-span-3">
                  <SingleImageInput label="Image" compact clearable value={variant.image} onChange={(image) => updateVariant(variant.key, { image })} />
                </div>
              </div>
            </fieldset>
          ))}
          {!lookups.loading && lookups.attributes.length === 0 && (
            <p className="showcase-muted text-xs">No variant options (like Shade or Size) exist yet. An administrator can add them.</p>
          )}
          <div>
            <button
              type="button"
              onClick={() => setVariants((list) => [...list, variantState(null)])}
              className="auth-btn auth-btn--outline inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-xs font-medium"
            >
              <FiPlus className="h-3.5 w-3.5" aria-hidden="true" /> Add Variant
            </button>
          </div>
        </div>
      </Section>

      <Section title="Product Details">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <span className="text-sm font-medium">
              Skin Type <span className="showcase-muted font-normal">(Optional)</span>
            </span>
            <div className="flex flex-wrap gap-x-5 gap-y-2">
              {SKIN_TYPES.map((o) => (
                <Toggle key={o.value} id={`pf-skin-${o.value}`} label={o.label} checked={v.skin_type.includes(o.value)} onChange={() => toggleSkinType(o.value)} />
              ))}
            </div>
          </div>
          <Field id="pf-key-ingredients" label="Key Ingredients" optional hint="One per line.">
            <textarea id="pf-key-ingredients" rows={4} value={v.key_ingredients} onChange={onInput("key_ingredients")} className={INPUT} />
          </Field>
          <Field id="pf-ingredients" label="Ingredients" optional hint="Full ingredient list (INCI).">
            <textarea id="pf-ingredients" rows={4} value={v.ingredients} onChange={onInput("ingredients")} className={INPUT} />
          </Field>
          <Field id="pf-size" label="Size" optional>
            <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,7.5rem)] gap-2">
              <input
                id="pf-size"
                type="number"
                inputMode="decimal"
                min="0"
                step="0.01"
                placeholder="Value"
                value={v.size_value}
                onChange={onInput("size_value")}
                className={INPUT}
              />
              <select aria-label="Size unit" value={v.size_unit} onChange={onInput("size_unit")} className={INPUT}>
                <option value="">Unit</option>
                {SIZE_UNITS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
          </Field>
          <Field id="pf-country" label="Country of Origin" optional>
            <input id="pf-country" type="text" maxLength={80} value={v.country_of_origin} onChange={onInput("country_of_origin")} className={INPUT} />
          </Field>
          <Field id="pf-mfg" label="Manufacture Date" optional>
            <input id="pf-mfg" type="date" value={v.manufacture_date} onChange={onInput("manufacture_date")} className={INPUT} />
          </Field>
          <Field id="pf-expiry" label="Expiry Date" optional>
            <input id="pf-expiry" type="date" value={v.expiry_date} onChange={onInput("expiry_date")} className={INPUT} />
          </Field>
          <Field id="pf-gender" label="Gender" optional>
            <select id="pf-gender" value={v.gender} onChange={onInput("gender")} className={INPUT}>
              <option value="">Not specified</option>
              {GENDERS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
          <div className="flex flex-col gap-2 sm:col-span-2">
            <span className="text-sm font-medium">Flags</span>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              <Toggle id="pf-featured" label="Is Featured" checked={v.is_featured} onChange={set("is_featured")} />
              <Toggle id="pf-new" label="Is New Arrival" checked={v.is_new_arrival} onChange={set("is_new_arrival")} />
              <Toggle id="pf-best" label="Is Bestseller" checked={v.is_bestseller} onChange={set("is_bestseller")} />
            </div>
          </div>
        </div>
      </Section>

      <Section title="SEO">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field id="pf-meta-title" label="Meta Title" optional hint={`${v.meta_title.length}/70`}>
            <input id="pf-meta-title" type="text" maxLength={70} value={v.meta_title} onChange={onInput("meta_title")} className={INPUT} />
          </Field>
          <Field id="pf-meta-desc" label="Meta Description" optional hint={`${v.meta_description.length}/320`}>
            <textarea id="pf-meta-desc" rows={3} maxLength={320} value={v.meta_description} onChange={onInput("meta_description")} className={INPUT} />
          </Field>
          <div className="sm:col-span-2">
            <SingleImageInput id="pf-og" label="OG Image" clearable value={ogImage} onChange={setOgImage} />
          </div>
        </div>
      </Section>

      {isEdit && (
        <Section title="Ratings" description="Calculated automatically from approved customer reviews, so they can't be edited here.">
          <dl className="grid grid-cols-2 gap-4 text-sm sm:max-w-sm">
            <div>
              <dt className="showcase-muted text-xs">Average Rating</dt>
              <dd className="mt-1 font-medium">{Number(product.average_rating).toFixed(2)} / 5</dd>
            </div>
            <div>
              <dt className="showcase-muted text-xs">Review Count</dt>
              <dd className="mt-1 font-medium">{product.review_count}</dd>
            </div>
          </dl>
        </Section>
      )}

      <div className="flex flex-wrap items-center justify-end gap-3">
        <Link href={to("/dashboard/CCE/products")} className="auth-btn auth-btn--outline rounded-full px-6 py-2.5 text-sm font-medium">
          Cancel
        </Link>
        <button type="submit" disabled={submitting} aria-busy={submitting} className="auth-btn auth-btn--primary rounded-full px-6 py-2.5 text-sm font-medium">
          {submitting ? (isEdit ? "Saving Product..." : "Creating Product...") : isEdit ? "Save Changes" : "Create Product"}
        </button>
      </div>
    </form>
  );
}
