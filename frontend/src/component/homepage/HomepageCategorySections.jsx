import CategoryProductShowcase from "./CategoryProductShowcase";
import { getHomepageCategorySections } from "@/lib/content";

// The category product sections the Admin set up for one side of the skincare video section (Admin → Homepage
// Sections; GET /homepage/category-sections/). Each is the existing CategoryProductShowcase: the category's own name as
// the title, its products (sub-categories included) from the shared product fetch, and the Admin's product limit and
// rows. A section whose category has no products is left out rather than shown empty. The list is fetched once per
// render and shared by both positions (Next.js de-duplicates the identical cached request).
//   position  "before_video" | "after_video"
export default async function HomepageCategorySections({ position }) {
  const sections = (await getHomepageCategorySections()).filter((section) => section.position === position);
  return sections.map((section) => (
    <CategoryProductShowcase
      key={section.id}
      category={section.category.slug}
      title={section.category.name}
      description=""
      productLimit={section.product_limit}
      rows={section.rows}
      hideWhenEmpty
    />
  ));
}
