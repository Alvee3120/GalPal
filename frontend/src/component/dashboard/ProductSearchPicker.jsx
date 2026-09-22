"use client";

import { useState } from "react";
import { FiMinus, FiPlus, FiSearch } from "react-icons/fi";
import ProductImage from "@/component/shared/ProductImage";
import formatPrice from "@/lib/formatPrice";
import { notify } from "@/lib/notify";

const rowKey = (row) => `${row.product_id}:${row.variant_id ?? "base"}`;

// The searchable product/variant picker (Add Product / Add Order specs) — one shared unit used both inside a
// modal (CceOrderDetail's "Add Product") and inline (AddOrderForm), so the search/select/quantity logic exists
// once. Backed by the EXISTING GET /admin/orders/helpers/products/?search= (apps.orders.services.pickable_lines,
// via the /api/admin/orders proxy) — one row per buyable product/variant, with its real price and stock; nothing
// here is hardcoded and stock is never trusted beyond "how many can I ask to add" (the backend re-validates for
// real when the order is actually created/edited).
export default function ProductSearchPicker({ currencySymbol, onAdd }) {
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [selectedKey, setSelectedKey] = useState(null);
  const [quantity, setQuantity] = useState(1);

  async function runSearch(q) {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (q) params.set("search", q);
      const res = await fetch(`/api/admin/orders/helpers/products?${params.toString()}`, { cache: "no-store" });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        notify.error("Unable to search products. Please try again.");
        return;
      }
      setRows(Array.isArray(data) ? data : []);
      setSearched(true);
    } catch {
      notify.error("Unable to search products. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    runSearch(query);
  }

  function selectRow(row) {
    setSelectedKey(rowKey(row));
    setQuantity(1);
  }

  const selected = rows.find((r) => rowKey(r) === selectedKey) ?? null;
  const stockCap = selected?.stock ?? null; // null = stock isn't tracked for this line

  function handleAdd() {
    if (!selected) return;
    if (stockCap !== null && stockCap <= 0) {
      notify.error("This product is currently out of stock.");
      return;
    }
    if (stockCap !== null && quantity > stockCap) {
      notify.error(`Only ${stockCap} unit${stockCap === 1 ? "" : "s"} of this product are currently available.`);
      return;
    }
    onAdd(selected, quantity);
    setSelectedKey(null);
    setQuantity(1);
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleSubmit} className="relative">
        <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search products by name or SKU..."
          className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
        />
      </form>

      <div className="flex max-h-72 flex-col gap-2 overflow-y-auto">
        {loading ? (
          <p className="showcase-muted py-6 text-center text-sm">Searching...</p>
        ) : !searched ? (
          <p className="showcase-muted py-6 text-center text-sm">Search for a product to add.</p>
        ) : rows.length === 0 ? (
          <p className="showcase-muted py-6 text-center text-sm">No products found.</p>
        ) : (
          rows.map((row) => {
            const key = rowKey(row);
            const isSelected = key === selectedKey;
            const outOfStock = row.stock !== null && row.stock <= 0;
            return (
              <button
                type="button"
                key={key}
                onClick={() => selectRow(row)}
                disabled={outOfStock}
                aria-pressed={isSelected}
                className={`dashboard-card flex items-center gap-3 rounded-xl p-2.5 text-left disabled:opacity-50 ${
                  isSelected ? "product-picker-row--selected" : ""
                }`}
              >
                <div className="cart-thumb relative h-12 w-12 shrink-0 overflow-hidden">
                  <ProductImage src={row.image} alt="" tight />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{row.name}</p>
                  {row.variant_label && <p className="showcase-muted truncate text-xs">{row.variant_label}</p>}
                  <p className="showcase-muted text-xs">
                    {formatPrice(row.price, currencySymbol)}
                    {row.stock !== null && <span> &bull; {outOfStock ? "Out of stock" : `${row.stock} in stock`}</span>}
                  </p>
                </div>
              </button>
            );
          })
        )}
      </div>

      {selected && (
        <div className="dashboard-card flex flex-wrap items-center justify-between gap-3 rounded-xl p-3">
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
                disabled={stockCap !== null && quantity >= stockCap}
                aria-label="Increase quantity"
                className="cart-qty__btn flex h-8 w-8 items-center justify-center rounded-full"
              >
                <FiPlus className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </div>
          </div>
          <button type="button" onClick={handleAdd} className="auth-btn auth-btn--primary rounded-full px-6 py-2 text-sm font-medium">
            Add Product
          </button>
        </div>
      )}
    </div>
  );
}
