// The ONE place that decides a product card's action button, from the real API fields
// (`in_stock`, `has_variants` — both computed server-side, never inferred from name/id/frontend guesses).
//   "notify"  completely out of stock -> Notify Me
//   "select"  in stock but has variants -> Select Options (go choose one on the product page)
//   "add"     in stock, no variants -> Add to Cart
export function getStockAction(product) {
  if (product?.in_stock === false) return "notify";
  if (product?.has_variants) return "select";
  return "add";
}
