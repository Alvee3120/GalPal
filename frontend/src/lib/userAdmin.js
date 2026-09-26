// User Management constants. Roles mirror apps.accounts.models.User.Role exactly (value -> label); the backend
// validates every value, so these only drive the controls.
export const USER_ROLES = [
  { value: "customer", label: "Customer" },
  { value: "cce", label: "CCE" },
  { value: "admin", label: "Admin" },
];
export const USER_ROLE_LABEL = Object.fromEntries(USER_ROLES.map((r) => [r.value, r.label]));

// The rules Django's AUTH_PASSWORD_VALIDATORS enforce (config/settings/base.py), worded as Django words them. The
// backend checks every password; this list is only shown to the admin.
export const PASSWORD_RULES = [
  "Your password can't be too similar to your other personal information.",
  "Your password must contain at least 8 characters.",
  "Your password can't be a commonly used password.",
  "Your password can't be entirely numeric.",
];

// A strong temporary password for "Reset Password", made in the browser with crypto.getRandomValues so it only ever
// travels in the request that sets it — the backend never sends a password back. Mixed case, digits and symbols, so it
// passes Django's validators (length, not numeric, not common). Never logged.
export function generateTemporaryPassword(length = 14) {
  const sets = ["ABCDEFGHJKLMNPQRSTUVWXYZ", "abcdefghijkmnpqrstuvwxyz", "23456789", "!@#$%*?-"];
  const all = sets.join("");
  const pick = (chars) => chars[crypto.getRandomValues(new Uint32Array(1))[0] % chars.length];
  const chars = [...sets.map(pick), ...Array.from({ length: length - sets.length }, () => pick(all))];
  for (let i = chars.length - 1; i > 0; i -= 1) {
    const j = crypto.getRandomValues(new Uint32Array(1))[0] % (i + 1);
    [chars[i], chars[j]] = [chars[j], chars[i]];
  }
  return chars.join("");
}

export async function userFetch(path = "", { method = "GET", body } = {}) {
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  try {
    const res = await fetch(`/api/admin/users${path}`, {
      method,
      cache: "no-store",
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
      headers: body === undefined || isForm ? undefined : { "Content-Type": "application/json" },
    });
    const data = res.status === 204 ? null : await res.json().catch(() => null);
    return { ok: res.ok, status: res.status, data };
  } catch {
    return { ok: false, status: 0, data: null };
  }
}
