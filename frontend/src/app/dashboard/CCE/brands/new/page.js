import Link from "next/link";
import BrandForm from "@/component/dashboard/brands/BrandForm";

export const metadata = { title: "Add Brand | GalPal" };

export default function CceAddBrandPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/dashboard/CCE/brands" className="showcase-muted text-sm hover:underline">
          &larr; Brand Management
        </Link>
        <h1 className="custom-font mt-2 text-2xl sm:text-3xl">Add Brand</h1>
      </div>
      <BrandForm />
    </div>
  );
}
