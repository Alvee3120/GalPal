import { revalidateTag } from "next/cache";
import { backendFetch } from "@/lib/backendAuth";

const VIDEOS_TAG = "videos"; // the tag ShoppableVideoCarousel reads with

// Proxy to Video Card Management (apps.videos.views_admin.AdminVideoCardViewSet — Admin and CCE via IsCatalogStaff,
// the real authorization). Uploads (video, thumbnail) arrive as multipart and are re-sent as FormData. After any change
// the homepage's shoppable videos (fetched with the "videos" cache tag) are revalidated, so they update on the next render.
const ID = /^\d+$/;
const isPath = (p, method) => {
  if (p.length === 0) return method === "GET" || method === "POST";
  return p.length === 1 && ID.test(p[0]) && ["GET", "PATCH", "DELETE"].includes(method);
};

async function handler(request, { params }) {
  const { path = [] } = await params;
  const method = request.method;
  if (!isPath(path, method)) return Response.json({ error: { message: "Not found." } }, { status: 404 });
  const qs = new URL(request.url).search;
  let body;
  if (method === "POST" || method === "PATCH") {
    const isForm = (request.headers.get("content-type") ?? "").startsWith("multipart/form-data");
    body = isForm ? await request.formData() : await request.text();
  }
  let res;
  try {
    res = await backendFetch(`/admin/videos/${path.length ? `${path[0]}/` : ""}${qs}`, { method, body });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  if (res.ok && method !== "GET") revalidateTag(VIDEOS_TAG, { expire: 0 });
  if (res.status === 204) return new Response(null, { status: 204 });
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export { handler as GET, handler as POST, handler as PATCH, handler as DELETE };
