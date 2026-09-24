import Link from "next/link";
import ProductForm from "@/component/dashboard/products/ProductForm";

export const metadata = { title: "Add Product | GalPal" };

export default function CceAddProductPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/dashboard/CCE/products" className="showcase-muted text-sm hover:underline">
          &larr; Product Management
        </Link>
        <h1 className="custom-font mt-2 text-2xl sm:text-3xl">Add Product</h1>
      </div>
      <ProductForm />
    </div>
  );
}
