import ProductShowcase from "./ProductShowcase";
import SaleCountdown from "@/component/product/SaleCountdown";
import { DISCOUNTS_TAG, getActiveDiscounts } from "@/lib/discounts";

// One homepage product section per live Admin discount, in the same shared ProductShowcase as the category and
// trending sections (same header, carousel, product cards, Add to Cart, skeleton). The title is the discount's own
// name as the Admin typed it; the products are exactly the ones that discount is pricing right now
// (GET /products/?discount=<id>), so their cards already show the discounted price and "OFF" tag from the backend.
// A discount that hasn't started, has ended, is switched off or prices nothing has no section at all.
// Beside the name, the product page's countdown boxes (SaleCountdown, without its heading) to the discount's own end.
// No product limit: every product the discount prices is in its carousel (`product_count` from the backend; the
// shared fetch follows the API's pages, and the arrows page through them).
export function DiscountProductShowcase({ discount, ...props }) {
  return (
    <ProductShowcase
      filter={{ discount: String(discount.id) }}
      title={discount.name}
      productLimit={Math.max(1, discount.product_count ?? 1)}
      hideWhenEmpty
      cacheTags={[DISCOUNTS_TAG]}
      // Keyed: this element is created inside the discounts.map() below, so React's list-key check covers it.
      headerExtra={<SaleCountdown key={`countdown-${discount.id}`} saleStartAt={discount.starts_at} saleEndAt={discount.ends_at} showHeading={false} className="shrink-0" />}
      {...props}
    />
  );
}

export default async function DiscountProductShowcases(props) {
  const discounts = await getActiveDiscounts();
  return discounts.map((discount) => <DiscountProductShowcase key={discount.id} discount={discount} {...props} />);
}
