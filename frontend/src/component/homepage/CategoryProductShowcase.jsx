import ProductShowcase from "./ProductShowcase";

export { ProductShowcaseSkeleton } from "./ProductShowcase";

// A parent category's products, sub-categories included: the backend's `category` filter takes a category
// slug and already covers every sub-category, so one request returns the parent's and all of its children's.
//   category  slug of the parent category (as used by the API's `category` filter)
export default function CategoryProductShowcase({ category, ...props }) {
  return <ProductShowcase filter={{ category }} {...props} />;
}
