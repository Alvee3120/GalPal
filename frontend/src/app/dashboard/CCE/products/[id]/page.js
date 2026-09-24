import Link from "next/link";
import { notFound } from "next/navigation";
import { backendFetch } from "@/lib/backendAuth";
import ProductForm from "@/component/dashboard/products/ProductForm";

export const metadata = { title: "Edit Product | GalPal" };

// The full product (AdminProductSerializer) plus its variants from the variants endpoint (AdminVariantSerializer):
// the product's own nested `variants` show *effective* prices, while editing needs each variant's stored values
// (an empty price means "use the product's price").
async function load(id) {
  const [productRes, variantsRes] = await Promise.all([
    backendFetch(`/admin/products/${id}/`),
    backendFetch(`/admin/products/${id}/variants/?page_size=100`),
  ]);
  if (productRes.status === 404) return null;
  if (!productRes.ok || !variantsRes.ok) throw new Error(`Unable to load product ${id}`);
  const product = await productRes.json();
  const variants = await variantsRes.json();
  return { product, variants: Array.isArray(variants) ? variants : (variants.results ?? []) };
}

export default async function CceEditProductPage({ params }) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const data = await load(id);
  if (!data) notFound();
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/dashboard/CCE/products" className="showcase-muted text-sm hover:underline">
          &larr; Product Management
        </Link>
        <h1 className="custom-font mt-2 text-2xl sm:text-3xl">Edit Product</h1>
        <p className="showcase-muted mt-1 text-sm">{data.product.name}</p>
      </div>
      {/* keyed by id + updated_at so a refresh after a partial save re-seeds the form from what was saved */}
      <ProductForm key={`${data.product.id}-${data.product.updated_at}`} product={data.product} savedVariants={data.variants} />
    </div>
  );
}
