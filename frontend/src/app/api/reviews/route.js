import { revalidateTag } from "next/cache";
import { backendFetch } from "@/lib/backendAuth";
import { REVIEWS_TAG } from "@/lib/reviewsData";

// Thin proxy to the EXISTING reviews API (GET|POST /reviews/) — the backend URL stays server-side, and a review
// submission is identified from the session token (backendFetch), never from anything the browser claims about
// who's posting. GET is public (used for the "Load more" page beyond the server-rendered first page); only a
// known, narrow set of query params is forwarded.
const ALLOWED_PARAMS = ["product", "page", "page_size", "rating", "ordering"];

export async function GET(request) {
  const incoming = new URL(request.url).searchParams;
  const params = new URLSearchParams();
  for (const key of ALLOWED_PARAMS) {
    if (incoming.has(key)) params.set(key, incoming.get(key));
  }
  let res;
  try {
    res = await backendFetch(`/reviews/?${params}`);
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export async function POST(request) {
  // FormData, not JSON: CreateReviewSerializer's optional `images` are repeated multipart file fields.
  const body = await request.formData();
  let res;
  try {
    res = await backendFetch("/reviews/", { method: "POST", body });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  if (res.ok) revalidateTag(REVIEWS_TAG, { expire: 0 }); // the product page's next render reads fresh review data
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
