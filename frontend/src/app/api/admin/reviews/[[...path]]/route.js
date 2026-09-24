import { revalidateTag } from "next/cache";
import { backendFetch } from "@/lib/backendAuth";
import { REVIEWS_TAG } from "@/lib/reviewsData";

// Thin proxy to the EXISTING review moderation API (apps.reviews.views_admin.AdminReviewViewSet) for CCE Review
// Management. The backend's IsCatalogStaff (`cce_actions`: list, retrieve, approve, reject, destroy) is the real
// authorization; this only forwards those. After a successful approve/reject/delete it revalidates the public review
// reads (REVIEWS_TAG), so the product page's reviews, rating and count — and the homepage testimonials — update on
// their next render.
const ID = /^\d+$/;
const isPath = (p, method) => {
  if (p.length === 0) return method === "GET"; // list + filters
  if (!ID.test(p[0])) return false;
  if (p.length === 1) return method === "GET" || method === "DELETE";
  return p.length === 2 && method === "POST" && (p[1] === "approve" || p[1] === "reject");
};

async function handler(request, { params }) {
  const { path = [] } = await params;
  const method = request.method;
  if (!isPath(path, method)) return Response.json({ error: { message: "Not found." } }, { status: 404 });

  const qs = new URL(request.url).search;
  let res;
  try {
    res = await backendFetch(`/admin/reviews/${path.join("/")}${path.length ? "/" : ""}${qs}`, { method, body: method === "POST" ? "{}" : undefined });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  if (res.ok && method !== "GET") revalidateTag(REVIEWS_TAG, { expire: 0 });
  if (res.status === 204) return new Response(null, { status: 204 });
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export { handler as GET, handler as POST, handler as DELETE };
