"use client";

import { useEffect, useState } from "react";
import { useSession } from "./useAuthed";
import { normalizeBdPhone } from "./phone";
import { BD_CITIES } from "./bdLocations";
import { DHAKA_ZONES, isDhaka } from "./delivery";

// Everything checkout needs from the customer's EXISTING account, via the /api/account proxy:
//   GET /account/profile/    -> { full_name, phone, email, ... }
//   GET /account/addresses/  -> saved addresses (one is_default), { full_name, phone, district, area, address_line }
//   POST /account/addresses/ , POST /account/addresses/{id}/set-default/  -> remember the address used for an order
// Saved details are only DEFAULTS for the form; the values typed in the form are what the order uses.

async function accountApi(path, options = {}) {
  const res = await fetch(`/api/account/${path}`, { ...options, headers: { "Content-Type": "application/json" }, cache: "no-store" });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw Object.assign(new Error("account request failed"), { status: res.status });
  return data;
}

const listOf = (data) => (Array.isArray(data) ? data : (data?.results ?? []));

// { status: "loading" | "guest" | "authed", profile, addresses }. "guest" vs "authed" comes ONLY from the existing
// session check (useSession -> /api/session, the same one the navbar uses). Fresh on every mount, so re-opening
// checkout always shows the latest saved details.
export function useCheckoutAccount() {
  const { authed, ready } = useSession();
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (!ready || !authed) return;
    let cancelled = false;
    // One after the other, not in parallel: when the short-lived access token has lapsed, the first call renews the
    // session, and the backend burns the old refresh token on renewal — two simultaneous renewals would make one fail.
    accountApi("profile")
      .then(async (profile) => {
        const addresses = await accountApi("addresses").catch(() => []);
        return { profile, addresses: listOf(addresses) };
      })
      .then((data) => !cancelled && setResult(data))
      // Whether the account details could be read never decides guest vs logged in — only the session does. A failure
      // just means nothing is prefilled; the customer must still never be offered "create an account".
      .catch(() => !cancelled && setResult({ profile: {}, addresses: [] }));
    return () => {
      cancelled = true;
    };
  }, [ready, authed]);

  if (!ready) return { status: "loading", profile: null, addresses: [] };
  if (!authed) return { status: "guest", profile: null, addresses: [] };
  if (result === null) return { status: "loading", profile: null, addresses: [] };
  return { status: "authed", profile: result.profile, addresses: result.addresses };
}

// One saved address -> checkout form fields. A saved city/zone that isn't in the checkout lists is left blank
// (the customer picks it), never guessed.
export function addressToValues(address, profile) {
  const city = BD_CITIES.find((c) => c.toLowerCase() === String(address?.district ?? "").toLowerCase()) ?? "";
  const zone = isDhaka(city) ? (DHAKA_ZONES.find((z) => z.toLowerCase() === String(address?.area ?? "").toLowerCase()) ?? "") : "";
  return {
    fullName: address?.full_name || profile?.full_name || "",
    phone: address?.phone || profile?.phone || "",
    address: address?.address_line ?? "",
    city,
    zone,
  };
}

// Initial form values for a logged-in customer: their default address (else the newest), with the profile filling gaps.
export function initialValuesFor(profile, addresses) {
  const preferred = addresses.find((a) => a.is_default) ?? addresses[0];
  return { ...addressToValues(preferred, profile), email: profile?.email ?? "", note: "", saveDetails: false };
}

// After a successful order: make the address just used the customer's default for next time. It is added as a NEW
// saved address (older ones are kept), unless an identical one already exists — then that one just becomes the default.
// Best effort: the order has already succeeded, so a failure here is ignored rather than reported as an order failure.
export async function rememberCheckoutAddress(values, addresses) {
  const fields = {
    full_name: values.fullName.trim(),
    phone: normalizeBdPhone(values.phone),
    district: values.city,
    area: isDhaka(values.city) ? values.zone : "",
    address_line: values.address.trim(),
  };
  try {
    const same = addresses.find(
      (a) =>
        a.address_line === fields.address_line &&
        a.district === fields.district &&
        (a.area ?? "") === fields.area &&
        a.full_name === fields.full_name &&
        a.phone === fields.phone,
    );
    if (same) {
      if (!same.is_default) await accountApi(`addresses/${same.id}/set-default`, { method: "POST", body: "{}" });
    } else {
      await accountApi("addresses", { method: "POST", body: JSON.stringify({ ...fields, is_default: true }) });
    }
  } catch {
    // ignore
  }
}
