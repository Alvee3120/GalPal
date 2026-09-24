import Link from "next/link";
import CategoryForm from "@/component/dashboard/categories/CategoryForm";

export const metadata = { title: "Add Category | GalPal" };

export default function CceAddCategoryPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/dashboard/CCE/categories" className="showcase-muted text-sm hover:underline">
          &larr; Category Management
        </Link>
        <h1 className="custom-font mt-2 text-2xl sm:text-3xl">Add Category</h1>
      </div>
      <CategoryForm />
    </div>
  );
}
