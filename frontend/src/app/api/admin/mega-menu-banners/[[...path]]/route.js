import { revalidateTag } from "next/cache";
import { backendFetch } from "@/lib/backendAuth";
import { MEGA_MENU_TAG } from "@/lib/megaMenu";

// Proxy to the mega menu banner admin API (apps.banners.views_admin.AdminMegaMenuBannerViewSet — IsAdmin, so CCE and
// customers get 403 there; the model allows one banner per slot: square_1, square_2, wide). Image uploads arrive as
// multipart and are re-sent as FormData. After any change the storefront mega menu (fetched with the "mega-menu"
// cache tag) is revalidated.
const ID = /^\d+$/;
const isPath = (p, method) => {
  if (p.length === 0) return method === "GET" || method === "POST"; // list / create
  return p.length === 1 && ID.test(p[0]) && ["PATCH", "DELETE"].includes(method);
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
    res = await backendFetch(`/admin/mega-menu-banners/${path.length ? `${path[0]}/` : ""}${qs}`, { method, body });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  if (res.ok && method !== "GET") revalidateTag(MEGA_MENU_TAG, { expire: 0 });
  if (res.status === 204) return new Response(null, { status: 204 });
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export { handler as GET, handler as POST, handler as PATCH, handler as DELETE };
