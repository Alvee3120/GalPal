"use client";

import Link from "next/link";
import { FiMinus, FiPlus, FiTrash2 } from "react-icons/fi";
import formatPrice from "@/lib/formatPrice";
import { variantLabel } from "@/lib/cartItem";
import ProductImage from "@/component/shared/ProductImage";

// Quantity stepper, shared between the table row and the mobile card. Same `.cart-qty` look/markup as the
// cart drawer, reusing the exact same setQuantity/removeItem calls from useCart() — no separate cart logic.
function QuantityStepper({ item, busy, onQuantity }) {
  const { id, quantity, available_quantity, product } = item;
  const atMax = typeof available_quantity === "number" && quantity >= available_quantity;
  return (
    <div className="cart-qty inline-flex items-center rounded-full">
      <button
        type="button"
        onClick={() => onQuantity(id, quantity - 1)}
        disabled={busy || quantity <= 1}
        aria-label={`Decrease quantity of ${product.name}`}
        className="cart-qty__btn flex h-8 w-8 items-center justify-center rounded-full"
      >
        <FiMinus className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
      <span className="min-w-8 text-center text-sm tabular-nums" aria-live="polite" aria-label={`Quantity ${quantity}`}>
        {quantity}
      </span>
      <button
        type="button"
        onClick={() => onQuantity(id, quantity + 1)}
        disabled={busy || atMax}
        aria-label={`Increase quantity of ${product.name}`}
        className="cart-qty__btn flex h-8 w-8 items-center justify-center rounded-full"
      >
        <FiPlus className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </div>
  );
}

function ProductCell({ product, label }) {
  return (
    <div className="flex min-w-0 items-center gap-3 sm:gap-4">
      <Link href={`/products/${product.slug}`} className="cart-thumb relative h-16 w-16 shrink-0 overflow-hidden sm:h-20 sm:w-20">
        <ProductImage src={product.feature_image} alt="" />
      </Link>
      <div className="min-w-0">
        <Link href={`/products/${product.slug}`} className="cart-link line-clamp-2 text-sm font-medium leading-snug sm:text-base">
          {product.name}
        </Link>
        {label && <p className="showcase-muted mt-0.5 text-xs">Set : {label}</p>}
        {product.sku && <p className="showcase-muted mt-0.5 text-xs">SKU: {product.sku}</p>}
      </div>
    </div>
  );
}

function RemoveButton({ item, busy, onRemove }) {
  return (
    <button
      type="button"
      onClick={() => onRemove(item.id)}
      disabled={busy}
      aria-label={`Remove ${item.product.name} from cart`}
      className="cart-remove-btn flex h-9 w-9 items-center justify-center rounded-full"
    >
      <FiTrash2 className="h-4 w-4" aria-hidden="true" />
    </button>
  );
}

// Cart items as a real <table> on tablet/desktop (matching the reference's Product Code / Quantity / Total /
// Action columns) and as stacked cards on phones — same data, same handlers, two layouts so nothing needs a
// cramped horizontal table-scroll on small screens.
export default function CartItemsTable({ items, currencySymbol, pendingIds, onQuantity, onRemove }) {
  return (
    <>
      <table className="cart-table hidden w-full md:table">
        <thead>
          <tr className="cart-table__head-row text-left text-sm">
            <th scope="col" className="pb-4 font-semibold">
              Product Code
            </th>
            <th scope="col" className="pb-4 text-center font-semibold">
              Quantity
            </th>
            <th scope="col" className="pb-4 text-right font-semibold">
              Total
            </th>
            <th scope="col" className="pb-4 pl-4 text-right font-semibold">
              Action
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const busy = pendingIds.has(item.id);
            return (
              <tr key={item.id} className="cart-table__row">
                <td className="py-4 pr-4 align-top">
                  <ProductCell product={item.product} label={variantLabel(item.variant)} />
                  {!item.is_available && <p className="auth-error mt-1 text-xs">No longer available</p>}
                </td>
                <td className="py-4 align-middle">
                  <div className="flex justify-center">
                    <QuantityStepper item={item} busy={busy} onQuantity={onQuantity} />
                  </div>
                </td>
                <td className="py-4 text-right align-middle text-base font-semibold">{formatPrice(item.line_total, currencySymbol)}</td>
                <td className="py-4 pl-4 text-right align-middle">
                  <div className="flex justify-end">
                    <RemoveButton item={item} busy={busy} onRemove={onRemove} />
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <ul className="cart-item-cards flex flex-col gap-4 md:hidden">
        {items.map((item) => {
          const busy = pendingIds.has(item.id);
          return (
            <li key={item.id} className="cart-item-card rounded-2xl p-4">
              <div className="flex items-start justify-between gap-3">
                <ProductCell product={item.product} label={variantLabel(item.variant)} />
                <RemoveButton item={item} busy={busy} onRemove={onRemove} />
              </div>
              {!item.is_available && <p className="auth-error mt-2 text-xs">No longer available</p>}
              <div className="mt-3 flex items-center justify-between">
                <QuantityStepper item={item} busy={busy} onQuantity={onQuantity} />
                <span className="text-base font-semibold">{formatPrice(item.line_total, currencySymbol)}</span>
              </div>
            </li>
          );
        })}
      </ul>
    </>
  );
}
