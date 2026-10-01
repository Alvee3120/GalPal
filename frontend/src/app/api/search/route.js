import { backendFetch } from "@/lib/backendAuth";

// Proxy to GET /search/ (apps.content — products, categories, brands + autocomplete suggestions).
export async function GET(request) {
  const url = new URL(request.url);
  const params = new URLSearchParams({ q: (url.searchParams.get("q") ?? "").slice(0, 100) });
  const limit = url.searchParams.get("limit");
  if (limit && /^\d{1,2}$/.test(limit)) params.set("limit", limit);
  let res;
  try {
    res = await backendFetch(`/search/?${params}`);
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
