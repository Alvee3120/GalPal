import ProductShowcase from "./ProductShowcase";

// Products carrying a given tag, straight from the backend's `tag` filter (GET /products/?tag=<slug>).
// The tag is the single source of truth: an admin adds or removes the "trending" tag on a product and it
// appears in / drops out of this section on the next revalidation. There is no separate list of products.
//   tag          the Tag slug (the backend derives it from the name: "Trending" -> "trending")
//   hideWhenEmpty is on by default: with no matching products the whole section disappears
export default function TrendingProducts({
  tag = "trending",
  title = "Trending Now",
  description = "The products everyone's loving right now.",
  hideWhenEmpty = true,
  ...props
}) {
  // Slugs are lowercase; normalizing keeps "Trending" / "TRENDING" from becoming a different tag.
  return <ProductShowcase filter={{ tag: tag.trim().toLowerCase() }} title={title} description={description} hideWhenEmpty={hideWhenEmpty} {...props} />;
}
