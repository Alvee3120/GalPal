import { revalidateTag } from "next/cache";
import { backendFetch } from "@/lib/backendAuth";
import { CONTENT_TAG } from "@/lib/content";

// Proxy to the Content admin API (apps.content.views_admin — IsAdmin: CCE and customers get 403 there), narrowed to
// the routes the dashboard uses. A successful write refreshes the storefront's cached pages/FAQs/announcements.
const ID = /^\d+$/;
const WRITES = {
  pages: ["POST", "PATCH", "DELETE"],
  faqs: ["POST", "PATCH", "DELETE"],
  announcements: ["POST", "PATCH", "DELETE"],
  newsletter: ["PATCH", "DELETE"],
};
const isPath = (p, method) => {
  const [area, id] = p;
  const writes = WRITES[area];
  if (!writes) return false;
  if (p.length === 1) return method === "GET" || (method === "POST" && writes.includes("POST"));
  if (p.length !== 2) return false;
  if (area === "pages" && id === "standard") return method === "GET";
  if (area === "newsletter" && id === "export") return method === "GET";
  return ID.test(id) && (method === "GET" || (method !== "POST" && writes.includes(method)));
};

async function handler(request, { params }) {
  const { path = [] } = await params;
  const method = request.method;
  if (!isPath(path, method)) return Response.json({ error: { message: "Not found." } }, { status: 404 });
  const qs = new URL(request.url).search;
  const body = method === "GET" || method === "DELETE" ? undefined : (await request.text()) || undefined;
  let res;
  try {
    res = await backendFetch(`/admin/content/${path.join("/")}/${qs}`, { method, body });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  if (res.ok && method !== "GET") revalidateTag(CONTENT_TAG, { expire: 0 });
  if (res.status === 204) return new Response(null, { status: 204 });
  if (path[1] === "export" && res.ok) {
    return new Response(await res.arrayBuffer(), {
      status: 200,
      headers: {
        "Content-Type": res.headers.get("Content-Type") ?? "text/csv; charset=utf-8",
        "Content-Disposition": res.headers.get("Content-Disposition") ?? "attachment; filename=newsletter.csv",
        "Cache-Control": "no-store",
      },
    });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export { handler as GET, handler as POST, handler as PATCH, handler as DELETE };
