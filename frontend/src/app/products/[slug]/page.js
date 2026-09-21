import { notFound } from "next/navigation";
import PageHero from "@/component/shared/PageHero";
import ProductDetailContent from "@/component/product/ProductDetailContent";
import { getCurrencySymbol } from "@/lib/siteSettings";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";

async function getProduct(slug) {
  try {
    const res = await fetch(`${API_BASE_URL}/products/${slug}/`, { next: { revalidate: 60 } });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`Product API responded ${res.status}`);
    return await res.json();
  } catch (error) {
    console.error("Failed to load product:", error);
    return null;
  }
}

export async function generateMetadata({ params }) {
  const { slug } = await params;
  const product = await getProduct(slug);
  return { title: product ? `${product.name} | GalPal` : "Product | GalPal" };
}

// /products/[slug] — product detail with a variant picker; the Product Card's "Select Options" lands here.
export default async function ProductDetailPage({ params }) {
  const { slug } = await params;
  const [product, currencySymbol] = await Promise.all([getProduct(slug), getCurrencySymbol()]);
  if (!product) notFound();

  return (
    <main>
      {/* <PageHero title={product.name} /> */}
      <div className="mx-auto w-full max-w-6xl px-4 pb-16 sm:px-6 lg:px-8">
        <ProductDetailContent product={product} currencySymbol={currencySymbol} />
      </div>
    </main>
  );
}
