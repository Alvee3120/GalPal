"use client";

import { useMemo, useState } from "react";
import Image from "next/image";
import { useCart } from "@/component/cart/CartProvider";
import { FaStar } from "react-icons/fa";
import { FiCheckCircle } from "react-icons/fi";
import NotifyMeButton from "@/component/shared/NotifyMeButton";
import ProductAccordion from "./ProductAccordion";
import SaleCountdown from "./SaleCountdown";
import formatPrice from "@/lib/formatPrice";
import { notify } from "@/lib/notify";
import { getStockCap, quantityInCart, remainingToAdd } from "@/lib/stockLimit";

// Groups every variant's attribute_values by attribute, e.g. { id, name: "Shade", values: [{id, value}, ...] }.
function buildAttributeGroups(variants) {
  const groups = new Map();
  for (const variant of variants) {
    for (const av of variant.attribute_values) {
      if (!groups.has(av.attribute_id)) groups.set(av.attribute_id, { id: av.attribute_id, name: av.attribute, values: new Map() });
      groups.get(av.attribute_id).values.set(av.id, av.value);
    }
  }
  return [...groups.values()].map((g) => ({ ...g, values: [...g.values.entries()].map(([id, value]) => ({ id, value })) }));
}

// Product detail page: gallery, price, (if any) a variant picker, and a stock-aware action area
// using the SAME three-case rule as the product card (Add to Cart / choose a variant / Notify Me),
// just evaluated against the selected variant instead of the product as a whole.
export default function ProductDetailContent({ product, currencySymbol }) {
  const { addItem, openCart, items } = useCart();
  const [selected, setSelected] = useState({});
  const [quantity, setQuantity] = useState(1);
  const [adding, setAdding] = useState(false);
  const [activeImage, setActiveImage] = useState(product.feature_image);

  const attributeGroups = useMemo(() => buildAttributeGroups(product.variants ?? []), [product.variants]);

  const selectedVariant = useMemo(() => {
    if (!product.has_variants || attributeGroups.length === 0) return null;
    if (Object.keys(selected).length !== attributeGroups.length) return null;
    return (
      product.variants.find((v) => {
        const ids = v.attribute_values.map((av) => av.id);
        return attributeGroups.every((g) => ids.includes(selected[g.id]));
      }) ?? null
    );
  }, [selected, attributeGroups, product.has_variants, product.variants]);

  const gallery = useMemo(() => {
    const urls = [product.feature_image, ...(product.images ?? []).map((img) => img.image)].filter(Boolean);
    return [...new Set(urls)];
  }, [product.feature_image, product.images]);

  const displayImage = selectedVariant?.image || activeImage || product.feature_image;
  const priceSource = selectedVariant ?? product;
  const discounted = priceSource.on_sale && priceSource.regular_price !== priceSource.effective_price;

  let actionState; // "add" | "choose" | "unavailable" | "notify"
  if (!product.has_variants) {
    actionState = product.in_stock === false ? "notify" : "add";
  } else if (Object.keys(selected).length < attributeGroups.length) {
    actionState = "choose";
  } else if (!selectedVariant) {
    actionState = "unavailable";
  } else {
    actionState = selectedVariant.in_stock === false ? "notify" : "add";
  }

  // Same rule everywhere in the app (lib/stockLimit.js): cap = the selected variant's own stock if it has one,
  // else the product's; `in_stock` alone isn't enough here because it stays true even once every unit is already
  // sitting in THIS cart (stock isn't actually deducted until an order is placed).
  const stockCap = getStockCap(selectedVariant ?? product);
  const alreadyInCart = quantityInCart(items, product.id, selectedVariant?.id);
  const remaining = actionState === "add" ? remainingToAdd(stockCap, alreadyInCart) : Infinity;
  const maxedOut = actionState === "add" && remaining <= 0;
  const atStepperMax = quantity >= remaining;

  function pickAttribute(groupId, valueId) {
    setSelected((s) => ({ ...s, [groupId]: valueId }));
    setQuantity(1); // a different variant may allow a different amount; never carry over a stale, possibly-too-high quantity
  }

  async function handleAddToCart() {
    if (adding) return;
    if (maxedOut) {
      notify.error(stockCap === 1 ? "Only 1 item is available in stock." : `Only ${stockCap} items are available in stock.`);
      return;
    }
    if (quantity > remaining) {
      notify.error(remaining === 1 ? "Only 1 more item can be added." : `Only ${remaining} more items can be added.`);
      return;
    }
    setAdding(true);
    const result = await addItem(product.id, quantity, { productSlug: product.slug, variantId: selectedVariant?.id });
    setAdding(false);
    if (result.ok) openCart();
  }

  return (
    <div className="grid gap-8 lg:grid-cols-2 lg:gap-12 pt-10">
      <div>
        <div className="product-card__media relative aspect-square overflow-hidden">
          {displayImage ? (
            <Image src={displayImage} alt={product.name} fill unoptimized sizes="(min-width: 1024px) 45vw, 90vw" className="object-contain p-6" />
          ) : (
            <Image src="/assets/galpal/navlogo.svg" alt="" fill sizes="45vw" className="object-contain p-[20%] opacity-20" />
          )}
        </div>
        {gallery.length > 1 && (
          <div className="mt-3 flex gap-2 overflow-x-auto">
            {gallery.map((url) => (
              <button
                key={url}
                type="button"
                onClick={() => setActiveImage(url)}
                className="product-card__media relative h-16 w-16 shrink-0 overflow-hidden"
                aria-label="Show this photo"
              >
                <Image src={url} alt="" fill unoptimized sizes="64px" className="object-contain p-1.5" />
              </button>
            ))}
          </div>
        )}
      </div>

      <div>
        {(product.brand?.name || product.primary_category?.name) && (
          <p className="showcase-muted text-xs uppercase tracking-widest">{product.brand?.name ?? product.primary_category.name}</p>
        )}
        <h1 className="custom-font mt-2 text-3xl leading-tight sm:text-4xl">{product.name}</h1>

        {product.review_count > 0 && (
          <p className="mt-3 flex items-center gap-2 text-sm">
            <span className="flex gap-0.5" role="img" aria-label={`Rated ${Number(product.average_rating).toFixed(1)} out of 5`}>
              {[1, 2, 3, 4, 5].map((n) => (
                <FaStar key={n} className={`h-3.5 w-3.5 ${n <= Math.round(Number(product.average_rating)) ? "detail-star--on" : "detail-star--off"}`} aria-hidden="true" />
              ))}
            </span>
            <span className="showcase-muted">{product.review_count} {product.review_count === 1 ? "review" : "reviews"}</span>
          </p>
        )}

        <p className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="text-lg font-semibold">{formatPrice(priceSource.effective_price, currencySymbol)}</span>
          {discounted && <span className="showcase-muted text-sm line-through">{formatPrice(priceSource.regular_price, currencySymbol)}</span>}
          {discounted && priceSource.discount_percentage > 0 && (
            <span className="product-card__chip rounded-full px-2 py-0.5 text-xs font-medium">{priceSource.discount_percentage}%</span>
          )}
        </p>

        {/* Only for a product that really has a sale price AND both sale dates; the component itself hides for invalid dates or once the sale is over. */}
        {priceSource.discount_price != null && product.sale_start_at && product.sale_end_at && (
          <SaleCountdown saleStartAt={product.sale_start_at} saleEndAt={product.sale_end_at} className="mt-4" />
        )}

        {product.short_description && <p className="showcase-muted mt-4 text-sm leading-relaxed">{product.short_description}</p>}
        {(selectedVariant?.sku ?? product.sku) && (
          <p className="showcase-muted mt-2 text-xs">SKU: {selectedVariant?.sku ?? product.sku}</p>
        )}

        {attributeGroups.map((group) => (
          <fieldset key={group.id} className="mt-6">
            <legend className="text-xs">{group.name}:</legend>
            <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label={group.name}>
              {group.values.map((value) => (
                <button
                  key={value.id}
                  type="button"
                  aria-pressed={selected[group.id] === value.id}
                  onClick={() => pickAttribute(group.id, value.id)}
                  className="variant-pill min-w-24 flex-1 rounded-full px-4 py-2 text-center text-sm"
                >
                  {value.value}
                </button>
              ))}
            </div>
          </fieldset>
        ))}

        {actionState === "unavailable" && <p className="auth-error mt-4 text-sm">This combination isn&apos;t available.</p>}

        <div className="mt-6 flex items-center gap-3">
          {actionState === "add" && (
            <div className="cart-qty flex items-center rounded-full">
              <button
                type="button"
                onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                aria-label="Decrease quantity"
                className="cart-qty__btn flex h-10 w-10 items-center justify-center rounded-full text-lg"
              >
                −
              </button>
              <span className="w-8 text-center text-sm" aria-live="polite">
                {quantity}
              </span>
              <button
                type="button"
                onClick={() => setQuantity((q) => Math.min(q + 1, Math.max(1, remaining)))}
                disabled={atStepperMax}
                aria-label="Increase quantity"
                className="cart-qty__btn flex h-10 w-10 items-center justify-center rounded-full text-lg"
              >
                +
              </button>
            </div>
          )}

          {actionState === "add" && (
            <button
              type="button"
              onClick={handleAddToCart}
              disabled={adding || maxedOut}
              className="auth-btn auth-btn--primary flex-1 rounded-full py-3 text-sm font-medium uppercase tracking-wider"
            >
              {adding ? "Adding..." : maxedOut ? "Max in Cart" : "Add to Cart"}
            </button>
          )}

          {actionState === "choose" && (
            <button type="button" disabled className="auth-btn auth-btn--primary flex-1 rounded-full py-3 text-sm font-medium">
              Select an option
            </button>
          )}

          {actionState === "unavailable" && (
            <button type="button" disabled className="auth-btn auth-btn--primary flex-1 rounded-full py-3 text-sm font-medium">
              Select Options
            </button>
          )}

          {actionState === "notify" && (
            <NotifyMeButton
              productId={product.id}
              productName={
                selectedVariant ? `${product.name} — ${selectedVariant.attribute_values.map((av) => av.value).join(", ")}` : product.name
              }
              variantId={selectedVariant?.id}
              ariaLabel={`Notify me when ${product.name} is back in stock`}
              className="auth-btn product-card__action--notify flex-1 rounded-full py-3 text-sm font-medium"
            />
          )}
        </div>

        {product.tags?.length > 0 && (
          <ul className="detail-tags mt-6 flex flex-wrap gap-x-4 gap-y-2 rounded-xl px-4 py-3 text-xs">
            {product.tags.map((tag) => (
              <li key={tag.id} className="flex items-center gap-1.5">
                <FiCheckCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
                {tag.name}
              </li>
            ))}
          </ul>
        )}

        <ProductAccordion product={product} />
      </div>
    </div>
  );
}
