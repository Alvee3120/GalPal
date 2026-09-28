import { backendFetch } from "@/lib/backendAuth";

// Route handlers only: forward one backend invoice call and pass its answer back unchanged — JSON invoice data, or
// the backend-rendered PDF as raw bytes with its filename. Who may see which invoice is decided entirely by the
// backend (owner / order number + phone / IsAdminOrCCE); nothing here checks or widens access.
export async function relayInvoice(path, init) {
  let res;
  try {
    res = await backendFetch(path, init);
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const type = res.headers.get("Content-Type") || "";
  if (res.ok && type.includes("application/pdf")) {
    return new Response(await res.arrayBuffer(), {
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": res.headers.get("Content-Disposition") || 'attachment; filename="invoice.pdf"',
        "Cache-Control": "no-store",
      },
    });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
