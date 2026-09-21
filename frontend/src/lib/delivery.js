// The ONE place delivery charges are defined and calculated. The checkout UI, the order summary and the
// order-submission validation all call calculateDeliveryCharge(); nothing else hardcodes a fee.
//
//   Dhaka + Dhaka Sadar                                  -> 70
//   Dhaka + Dhamrai | Dohar | Keraniganj | Nawabganj | Savar -> 100
//   any city outside Dhaka                               -> 120
//
// The charge is display/validation only: it is never sent to the server as an amount. The order request
// carries just city + zone, and the server must derive the charge from those itself.
export const DHAKA_CITY = "Dhaka";
export const DHAKA_SADAR_ZONE = "Dhaka Sadar";
export const DHAKA_ZONES = [DHAKA_SADAR_ZONE, "Dhamrai", "Dohar", "Keraniganj", "Nawabganj", "Savar"];

export const DELIVERY_CHARGES = { dhakaSadar: 70, dhakaOuterZones: 100, outsideDhaka: 120 };

export function isDhaka(city) {
  return city === DHAKA_CITY;
}

// Returns the charge in BDT, or null while the selection is incomplete (no city, or Dhaka without a valid zone).
export function calculateDeliveryCharge(city, zone) {
  if (!city) return null;
  if (!isDhaka(city)) return DELIVERY_CHARGES.outsideDhaka;
  if (!DHAKA_ZONES.includes(zone)) return null;
  return zone === DHAKA_SADAR_ZONE ? DELIVERY_CHARGES.dhakaSadar : DELIVERY_CHARGES.dhakaOuterZones;
}
