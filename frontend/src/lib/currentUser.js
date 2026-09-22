import { cache } from "react";
import { backendFetch } from "./backendAuth";

// The authenticated user, from the EXISTING GET /account/profile/ endpoint (id, full_name, phone, email, avatar,
// role, ...) — the same one checkout's account prefill uses (lib/checkoutAccount.js), just server-side for the
// dashboard's route guards. `cache()` dedupes repeated calls within one request: the dashboard layout and any
// nested role-guard layout each ask for the user, but the backend is only actually called once per request.
// Server Components / layouts / route handlers only (needs next/headers cookies(), via backendFetch).
export const getCurrentUser = cache(async () => {
  try {
    const res = await backendFetch("/account/profile/");
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
});
