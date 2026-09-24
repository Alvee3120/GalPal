import { backendFetch } from "@/lib/backendAuth";
import CceReviewManagement from "@/component/dashboard/reviews/CceReviewManagement";

export const metadata = { title: "Review Management | GalPal" };

// First page of PENDING reviews server-side (the EXISTING /admin/reviews/ list); filters/paging run client-side.
async function getPending() {
  try {
    const res = await backendFetch("/admin/reviews/?status=pending&page_size=10");
    if (!res.ok) return { results: [], count: 0 };
    const data = await res.json();
    return { results: data.results ?? [], count: data.count ?? 0 };
  } catch {
    return { results: [], count: 0 };
  }
}

export default async function CceReviewsPage() {
  const { results, count } = await getPending();
  return <CceReviewManagement initialReviews={results} initialCount={count} />;
}
