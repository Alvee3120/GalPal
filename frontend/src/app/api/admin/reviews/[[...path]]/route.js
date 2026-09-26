import { revalidateTag } from "next/cache";
import { backendFetch } from "@/lib/backendAuth";
import { REVIEWS_TAG } from "@/lib/reviewsData";

// Thin proxy to the EXISTING review API (apps.reviews.views_admin.AdminReviewViewSet) for Review Management. The
// backend is the real authorization: CCE may list, retrieve, approve, reject and delete (IsCatalogStaff `cce_actions`);
// adding a review (POST /) and editing one (PATCH /<id>/) are Admin only (IsAdmin). After a successful approve/reject/delete it revalidates the public review
// reads (REVIEWS_TAG), so the product page's reviews, rating and count — and the homepage testimonials — update on
// their next render.
const ID = /^\d+$/;
const isPath = (p, method) => {
  if (p.length === 0) return method === "GET" || method === "POST"; // list + filters / add a review
  if (!ID.test(p[0])) return false;
  if (p.length === 1) return ["GET", "PATCH", "DELETE"].includes(method);
  return p.length === 2 && method === "POST" && (p[1] === "approve" || p[1] === "reject");
};

async function handler(request, { params }) {
  const { path = [] } = await params;
  const method = request.method;
  if (!isPath(path, method)) return Response.json({ error: { message: "Not found." } }, { status: 404 });

  const qs = new URL(request.url).search;
  let body;
  if (method === "POST" && path.length === 2) body = "{}"; // approve / reject carry no data
  else if (method === "POST" || method === "PATCH") {
    // A new review's photos go up as multipart: re-send the parsed FormData so fetch writes its own boundary.
    const isForm = (request.headers.get("content-type") ?? "").startsWith("multipart/form-data");
    body = isForm ? await request.formData() : await request.text();
  }
  let res;
  try {
    res = await backendFetch(`/admin/reviews/${path.join("/")}${path.length ? "/" : ""}${qs}`, { method, body });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  if (res.ok && method !== "GET") revalidateTag(REVIEWS_TAG, { expire: 0 });
  if (res.status === 204) return new Response(null, { status: 204 });
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export { handler as GET, handler as POST, handler as PATCH, handler as DELETE };
