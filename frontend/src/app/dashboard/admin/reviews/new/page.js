import Link from "next/link";
import { getCurrencySymbol } from "@/lib/siteSettings";
import ReviewForm from "@/component/dashboard/reviews/ReviewForm";

export const metadata = { title: "Add Review | GalPal" };

// Admin only (app/dashboard/admin/layout.js; the backend's create is IsAdmin too).
export default async function AdminAddReviewPage() {
  const currencySymbol = await getCurrencySymbol();
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/dashboard/admin/reviews" className="showcase-muted text-sm hover:underline">
          &larr; Review Management
        </Link>
        <h1 className="custom-font mt-2 text-2xl sm:text-3xl">Add Review</h1>
      </div>
      <ReviewForm currencySymbol={currencySymbol} />
    </div>
  );
}
