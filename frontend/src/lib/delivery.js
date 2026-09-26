// Checkout's city/zone vocabulary. Neither the delivery CHARGES nor Dhaka's outer areas are hardcoded here: both live in
// the backend's shipping zones (edited by the Admin on Dashboard -> Delivery Charges), which the storefront reads
// through /api/shipping. The backend works the charge out again when the order is placed, and stores it on the order.
//
//   Dhaka + Dhaka Sadar                                  -> the Inside Dhaka zone (it covers all of Dhaka not named below)
//   Dhaka + an area of the Dhaka Outer Zones zone         -> the Dhaka Outer Zones zone (Dhamrai, Dohar, Savar, …)
//   any city outside Dhaka                                -> the Outside Dhaka zone
export const DHAKA_CITY = "Dhaka";
export const DHAKA_SADAR_ZONE = "Dhaka Sadar"; // "the rest of Dhaka": not an area of any zone, so it prices as Inside Dhaka

export function isDhaka(city) {
  return city === DHAKA_CITY;
}

// Enough of an address to price? A city, and for Dhaka one of its zones (the charge differs by zone).
export function canQuote(city, zone) {
  return Boolean(city) && (!isDhaka(city) || Boolean(zone));
}

// Dhaka's zone choices from the public zones list: "Dhaka Sadar", then every area the Admin has given a zone for Dhaka.
export function dhakaZonesFrom(zones) {
  const areas = (zones ?? []).flatMap((zone) => (zone.areas ?? []).filter((c) => c.district === DHAKA_CITY).flatMap((c) => c.areas));
  return [DHAKA_SADAR_ZONE, ...areas.filter((a) => a.toLowerCase() !== DHAKA_SADAR_ZONE.toLowerCase())];
}

// A saved address's area as a Dhaka zone: kept as written (the list above decides the charge, and a zone the Admin has
// since removed simply prices as the rest of Dhaka). Options always include the current value so it stays visible.
export const zoneFromArea = (city, area) => (isDhaka(city) ? String(area ?? "").trim() : "");
export const withCurrent = (options, value) => (value && !options.some((o) => o === value) ? [...options, value] : options);

// The backend's charge for this address against the current cart: { charge, zone_name, is_free, ... } or null.
export async function fetchDeliveryQuote(city, zone) {
  if (!canQuote(city, zone)) return null;
  try {
    const res = await fetch("/api/shipping/quote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ district: city, area: isDhaka(city) ? zone : "" }),
      cache: "no-store",
    });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}
