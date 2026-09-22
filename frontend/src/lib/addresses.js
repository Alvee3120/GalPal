// Address CRUD, via the EXISTING /api/account proxy -> the backend's AddressViewSet (GET/POST/PATCH/DELETE
// /account/addresses/, POST /account/addresses/{id}/set-default/). Same proxy checkout's saved-address picker
// already uses (lib/checkoutAccount.js) — this just gives the standalone address-management page named, reusable
// calls instead of scattering fetch() through its components.
async function addressApi(path, options = {}) {
  const res = await fetch(`/api/account/addresses${path}`, {
    ...options,
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw Object.assign(new Error("address request failed"), { status: res.status, details: data?.error?.details });
  return data;
}

export async function getAddresses() {
  const data = await addressApi("");
  return Array.isArray(data) ? data : (data?.results ?? []);
}

export function createAddress(fields) {
  return addressApi("", { method: "POST", body: JSON.stringify(fields) });
}

export function updateAddress(id, fields) {
  return addressApi(`/${id}`, { method: "PATCH", body: JSON.stringify(fields) });
}

export function deleteAddress(id) {
  return addressApi(`/${id}`, { method: "DELETE" });
}

export function setDefaultAddress(id) {
  return addressApi(`/${id}/set-default`, { method: "POST", body: "{}" });
}
