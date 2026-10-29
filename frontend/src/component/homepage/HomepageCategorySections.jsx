import ProductShowcase from "./ProductShowcase";
import { getHomepageCategorySections } from "@/lib/content";

// Newest first for New Arrivals; everything else keeps the showcase's default (popularity).
const ORDERING = { new_arrival: "-newest" };

// The product sections the Admin set up for one side of the skincare video section (Admin → Homepage Sections; GET
// /homepage/category-sections/): a category (titled with the category's name, sub-categories included) or the Trending /
// New Arrivals / Bestsellers sections (products with the Is Featured / Is New Arrival / Is Bestseller flag, titled as the
// Admin chose). Each is the shared ProductShowcase — same carousel, product cards, prices, Add to Cart — fed the
// section's own `filter`, product limit and rows. A section with no products is left out rather than shown empty. The
// list is fetched once per render and shared by both positions (Next.js de-duplicates the identical cached request).
//   position  "before_video" | "after_video"
export default async function HomepageCategorySections({ position }) {
  const sections = (await getHomepageCategorySections()).filter((section) => section.position === position && section.filter);
  return sections.map((section) => (
    <ProductShowcase
      key={section.id}
      filter={section.filter}
      title={section.title}
      description=""
      productLimit={section.product_limit}
      rows={section.rows}
      ordering={ORDERING[section.source]}
      hideWhenEmpty
    />
  ));
}
