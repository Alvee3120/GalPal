import Link from "next/link";
import { notFound } from "next/navigation";
import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import ReviewForm from "@/component/dashboard/reviews/ReviewForm";

export const metadata = { title: "Edit Review | GalPal" };

export default async function AdminEditReviewPage({ params }) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const [res, currencySymbol] = await Promise.all([backendFetch(`/admin/reviews/${id}/`), getCurrencySymbol()]);
  if (res.status === 404) notFound();
  if (!res.ok) throw new Error(`Unable to load review ${id}`);
  const review = await res.json();
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/dashboard/admin/reviews" className="showcase-muted text-sm hover:underline">
          &larr; Review Management
        </Link>
        <h1 className="custom-font mt-2 text-2xl sm:text-3xl">Edit Review</h1>
      </div>
      <ReviewForm key={`${review.id}-${review.updated_at}`} review={review} currencySymbol={currencySymbol} />
    </div>
  );
}
