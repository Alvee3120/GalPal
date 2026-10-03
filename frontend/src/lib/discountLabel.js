import formatPrice from "@/lib/formatPrice";

// The "OFF" text for a product or variant from the backend's own pricing (Product/ProductVariant: on_sale,
// discount_percentage, applied_discount). An Admin fixed-amount discount reads "৳300 OFF"; everything else (an Admin
// percentage discount, or the product's own sale price) reads "20% OFF". null when there's no reduction.
export function discountOff(item, currencySymbol) {
  if (!item?.on_sale) return null;
  const applied = item.applied_discount;
  if (applied?.type === "fixed") return { text: `${formatPrice(applied.value, currencySymbol)} OFF`, short: `-${formatPrice(applied.value, currencySymbol)}` };
  if (item.discount_percentage > 0) return { text: `${item.discount_percentage}% OFF`, short: `-${item.discount_percentage}%` };
  return null;
}
