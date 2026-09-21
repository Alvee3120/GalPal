"use client";

import { useMemo, useState } from "react";
import Image from "next/image";
import { useCart } from "@/component/cart/CartProvider";
import NotifyMeButton from "@/component/shared/NotifyMeButton";
import formatPrice from "@/lib/formatPrice";

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
  const { addItem, openCart } = useCart();
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

  async function handleAddToCart() {
    if (adding) return;
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
          {discounted && priceSource.discount_percentage > 0 && (
            <span className="product-card__badge absolute left-3 top-3 rounded-full px-3 py-1 text-xs font-medium">
              {priceSource.discount_percentage}% OFF
            </span>
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
        {product.brand?.name && <p className="showcase-muted text-sm">{product.brand.name}</p>}
        <h1 className="custom-font mt-1 text-2xl sm:text-3xl">{product.name}</h1>

        <p className="mt-3 flex items-baseline gap-2 text-2xl">
          <span className="font-semibold">{formatPrice(priceSource.effective_price, currencySymbol)}</span>
          {discounted && <span className="showcase-muted text-base line-through">{formatPrice(priceSource.regular_price, currencySymbol)}</span>}
        </p>

        {product.short_description && <p className="showcase-muted mt-4 text-sm leading-relaxed">{product.short_description}</p>}

        {attributeGroups.map((group) => (
          <fieldset key={group.id} className="mt-5">
            <legend className="text-sm font-medium">{group.name}</legend>
            <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label={group.name}>
              {group.values.map((value) => (
                <button
                  key={value.id}
                  type="button"
                  aria-pressed={selected[group.id] === value.id}
                  onClick={() => setSelected((s) => ({ ...s, [group.id]: value.id }))}
                  className="variant-pill rounded-full px-4 py-1.5 text-sm"
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
                onClick={() => setQuantity((q) => q + 1)}
                aria-label="Increase quantity"
                className="cart-qty__btn flex h-10 w-10 items-center justify-center rounded-full text-lg"
              >
                +
              </button>
            </div>
          )}

          {actionState === "add" && (
            <button type="button" onClick={handleAddToCart} disabled={adding} className="auth-btn auth-btn--primary flex-1 rounded-full py-3 text-sm font-medium">
              {adding ? "Adding..." : "Add to Cart"}
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

        {product.full_description && (
          <div className="mt-8 border-t pt-6 text-sm leading-relaxed" dangerouslySetInnerHTML={{ __html: product.full_description }} />
        )}
      </div>
    </div>
  );
}
