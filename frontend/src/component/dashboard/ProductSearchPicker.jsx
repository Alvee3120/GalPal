"use client";

import { useEffect, useRef, useState } from "react";
import { FiMinus, FiPlus, FiSearch } from "react-icons/fi";
import ProductImage from "@/component/shared/ProductImage";
import formatPrice from "@/lib/formatPrice";
import { notify } from "@/lib/notify";
import { buildAttributeGroups, variantLabel } from "@/lib/productVariants";

const DEBOUNCE_MS = 350;

function groupByProduct(rows) {
  const groups = new Map();
  for (const row of rows) {
    if (!groups.has(row.product_id)) {
      groups.set(row.product_id, {
        product_id: row.product_id,
        slug: row.slug,
        has_variants: row.has_variants,
        name: row.name,
        sku: row.sku,
        image: row.image,
        rows: [],
      });
    }
    groups.get(row.product_id).rows.push(row);
  }
  return [...groups.values()];
}

// The searchable product/variant picker (Add Product / Add Order specs) — one shared unit used both inside a
// modal (CceOrderDetail's "Add Product") and inline (AddOrderForm), so the search/select/quantity logic exists
// once. Search results are grouped one row PER PRODUCT (not per variant — GET /admin/orders/helpers/products/
// returns one row per active variant, per apps.orders.services.pickable_lines, so a variable product would
// otherwise show up several times in the results list). Selecting a simple product goes straight to quantity;
// selecting a variable product fetches its real variants (GET /products/<slug>/, the SAME public endpoint and
// SAME attribute-grouping logic — lib/productVariants.js — the customer-facing Product Details page uses) and
// shows the actual Shade/Size/etc. pickers, never invented ones. Whatever gets added always carries the EXACT
// variant id resolved from that real data, never the parent product id alone.
export default function ProductSearchPicker({ currencySymbol, onAdd }) {
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState(false);
  const requestId = useRef(0);

  const [selectedGroup, setSelectedGroup] = useState(null); // one row from groupByProduct(rows), or null
  const [variantProduct, setVariantProduct] = useState(null); // full PublicProductDetailSerializer payload
  const [variantLoading, setVariantLoading] = useState(false);
  const [variantError, setVariantError] = useState(false);
  const [selectedAttrs, setSelectedAttrs] = useState({}); // { attributeGroupId: attributeValueId }
  const [fallbackRow, setFallbackRow] = useState(null); // a flat picker row, chosen directly when the variant detail fetch fails
  const [quantity, setQuantity] = useState(1);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    const q = query.trim();
    if (!q) return;
    const id = ++requestId.current;
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/admin/orders/helpers/products?search=${encodeURIComponent(q)}`, { cache: "no-store" });
        const data = await res.json().catch(() => null);
        if (id !== requestId.current) return; // a newer keystroke's search has already superseded this one
        if (!res.ok) {
          setError(true);
          setSearched(true);
          return;
        }
        setRows(Array.isArray(data) ? data : []);
        setSearched(true);
        setError(false);
      } catch {
        if (id === requestId.current) {
          setError(true);
          setSearched(true);
        }
      } finally {
        if (id === requestId.current) setLoading(false);
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  const groups = groupByProduct(rows);

  async function selectGroup(group) {
    setSelectedGroup(group);
    setSelectedAttrs({});
    setFallbackRow(null);
    setQuantity(1);
    setVariantProduct(null);
    setVariantError(false);
    if (!group.has_variants) return;
    setVariantLoading(true);
    try {
      const res = await fetch(`/api/products/${encodeURIComponent(group.slug)}`, { cache: "no-store" });
      const data = await res.json().catch(() => null);
      if (!res.ok || !Array.isArray(data?.variants)) {
        setVariantError(true);
        return;
      }
      setVariantProduct(data);
    } catch {
      setVariantError(true);
    } finally {
      setVariantLoading(false);
    }
  }

  function clearSelection() {
    setSelectedGroup(null);
    setVariantProduct(null);
    setVariantError(false);
    setSelectedAttrs({});
    setFallbackRow(null);
    setQuantity(1);
  }

  const attributeGroups = variantProduct ? buildAttributeGroups(variantProduct.variants ?? []) : [];
  const resolvedVariant =
    variantProduct && attributeGroups.length > 0 && Object.keys(selectedAttrs).length === attributeGroups.length
      ? (variantProduct.variants.find((v) => {
          const ids = v.attribute_values.map((av) => av.id);
          return attributeGroups.every((g) => ids.includes(selectedAttrs[g.id]));
        }) ?? null)
      : null;

  function pickAttribute(groupId, valueId) {
    setSelectedAttrs((s) => ({ ...s, [groupId]: valueId }));
    setQuantity(1);
  }

  // The exact line about to be added, in the same shape pickable_lines()/PickerRowSerializer already uses, so
  // onAdd's caller never needs to know whether it came from a simple product or a resolved variant.
  function pendingLine() {
    if (!selectedGroup) return null;
    if (fallbackRow) return { ...fallbackRow };
    if (!selectedGroup.has_variants) {
      const row = selectedGroup.rows[0];
      return { ...row };
    }
    if (!resolvedVariant) return null;
    return {
      product_id: selectedGroup.product_id,
      variant_id: resolvedVariant.id,
      name: selectedGroup.name,
      sku: resolvedVariant.sku,
      variant_label: variantLabel(resolvedVariant),
      price: resolvedVariant.effective_price,
      stock: resolvedVariant.manage_stock ? resolvedVariant.stock_quantity : null,
      image: resolvedVariant.image || selectedGroup.image,
    };
  }

  const line = pendingLine();
  const stockCap = line?.stock ?? null;
  const outOfStock = stockCap !== null && stockCap <= 0;

  async function handleAdd() {
    if (!line || adding) return;
    if (outOfStock) {
      notify.error("This product is currently out of stock.");
      return;
    }
    if (stockCap !== null && quantity > stockCap) {
      notify.error(`Only ${stockCap} unit${stockCap === 1 ? "" : "s"} of this product are currently available.`);
      return;
    }
    setAdding(true);
    try {
      await onAdd(line, quantity);
      clearSelection();
      setQuery("");
      setRows([]);
      setSearched(false);
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="relative">
        <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            clearSelection();
          }}
          placeholder="Search products by name or SKU..."
          className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
        />
      </div>

      {!selectedGroup && (
        <div className="flex max-h-72 flex-col gap-2 overflow-y-auto">
          {!query.trim() ? (
            <p className="showcase-muted py-6 text-center text-sm">Search for a product to add.</p>
          ) : loading ? (
            <p className="showcase-muted py-6 text-center text-sm">Searching...</p>
          ) : !searched ? null : error ? (
            <p className="auth-error py-6 text-center text-sm">Unable to search products. Please try again.</p>
          ) : groups.length === 0 ? (
            <p className="showcase-muted py-6 text-center text-sm">No products found.</p>
          ) : (
            groups.map((group) => {
              const prices = group.rows.map((r) => Number(r.price));
              const minPrice = Math.min(...prices);
              const allOutOfStock = group.rows.every((r) => r.stock !== null && r.stock <= 0);
              return (
                <button
                  type="button"
                  key={group.product_id}
                  onClick={() => selectGroup(group)}
                  disabled={allOutOfStock}
                  className="dashboard-card flex items-center gap-3 rounded-xl p-2.5 text-left disabled:opacity-50"
                >
                  <div className="cart-thumb relative h-12 w-12 shrink-0 overflow-hidden">
                    <ProductImage src={group.image} alt="" tight />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{group.name}</p>
                    {!group.has_variants && <p className="showcase-muted truncate text-xs">SKU: {group.sku}</p>}
                    <p className="showcase-muted text-xs">
                      {group.has_variants && group.rows.length > 1 ? "From " : ""}
                      {formatPrice(minPrice, currencySymbol)}
                      {!group.has_variants && group.rows[0].stock !== null && (
                        <span> &bull; {allOutOfStock ? "Out of stock" : `${group.rows[0].stock} in stock`}</span>
                      )}
                    </p>
                  </div>
                  <span className="auth-btn auth-btn--outline shrink-0 rounded-full px-4 py-1.5 text-xs font-medium">Select</span>
                </button>
              );
            })
          )}
        </div>
      )}

      {selectedGroup && (
        <div className="dashboard-card flex flex-col gap-4 rounded-xl p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="cart-thumb relative h-12 w-12 shrink-0 overflow-hidden">
                <ProductImage src={line?.image ?? selectedGroup.image} alt="" tight />
              </div>
              <p className="text-sm font-medium">{selectedGroup.name}</p>
            </div>
            <button type="button" onClick={clearSelection} className="showcase-muted text-xs underline underline-offset-4">
              Change product
            </button>
          </div>

          {selectedGroup.has_variants && (
            <div className="flex flex-col gap-3">
              {variantLoading ? (
                <p className="showcase-muted text-sm">Loading variants...</p>
              ) : variantError ? (
                <div className="flex flex-col gap-2">
                  <p className="auth-error text-sm">Unable to load this product&apos;s variants. Choose one below instead:</p>
                  <div className="flex flex-wrap gap-2">
                    {selectedGroup.rows.map((row) => (
                      <button
                        key={row.variant_id}
                        type="button"
                        aria-pressed={fallbackRow?.variant_id === row.variant_id}
                        onClick={() => {
                          setFallbackRow(row);
                          setQuantity(1);
                        }}
                        className="variant-pill rounded-full px-4 py-2 text-sm"
                      >
                        {row.variant_label || row.sku}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                attributeGroups.map((group) => (
                  <fieldset key={group.id}>
                    <legend className="text-xs font-medium">{group.name}</legend>
                    <div className="mt-1.5 flex flex-wrap gap-2" role="group" aria-label={group.name}>
                      {group.values.map((value) => (
                        <button
                          key={value.id}
                          type="button"
                          aria-pressed={selectedAttrs[group.id] === value.id}
                          onClick={() => pickAttribute(group.id, value.id)}
                          className="variant-pill rounded-full px-4 py-2 text-sm"
                        >
                          {value.value}
                        </button>
                      ))}
                    </div>
                  </fieldset>
                ))
              )}
              {!variantLoading && !variantError && attributeGroups.length > 0 && Object.keys(selectedAttrs).length === attributeGroups.length && !resolvedVariant && (
                <p className="auth-error text-sm">This combination isn&apos;t available.</p>
              )}
            </div>
          )}

          {line && (
            <>
              <div className="flex items-center justify-between border-t pt-3 text-sm">
                <span className="showcase-muted">Price</span>
                <span className="font-medium">{formatPrice(line.price, currencySymbol)}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="showcase-muted">Stock</span>
                <span className="font-medium">{outOfStock ? "Out of Stock" : stockCap !== null ? stockCap : "Unlimited"}</span>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Quantity:</span>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                      disabled={quantity <= 1}
                      aria-label="Decrease quantity"
                      className="cart-qty__btn flex h-8 w-8 items-center justify-center rounded-full"
                    >
                      <FiMinus className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                    <span className="w-8 text-center text-sm font-medium tabular-nums">{quantity}</span>
                    <button
                      type="button"
                      onClick={() => setQuantity((q) => (stockCap !== null ? Math.min(stockCap, q + 1) : q + 1))}
                      disabled={outOfStock || (stockCap !== null && quantity >= stockCap)}
                      aria-label="Increase quantity"
                      className="cart-qty__btn flex h-8 w-8 items-center justify-center rounded-full"
                    >
                      <FiPlus className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleAdd}
                  disabled={adding || outOfStock}
                  className="auth-btn auth-btn--primary rounded-full px-6 py-2 text-sm font-medium disabled:opacity-50"
                >
                  {adding ? "Adding..." : "Add Product"}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
