// Mirrors the backend's Bangladesh mobile validation (apps/core/validators.py normalize_bd_phone):
// accepts 01712345678, 8801712345678, +8801712345678, with spaces/dashes/brackets, canonical form
// is the 11-digit local number 01XXXXXXXXX (operator prefixes 013-019).
const BD_MOBILE = /^01[3-9]\d{8}$/;

export function normalizeBdPhone(value) {
  let digits = String(value ?? "").replace(/[\s\-()]/g, "");
  if (digits.startsWith("+880")) digits = "0" + digits.slice(4);
  else if (digits.startsWith("880") && digits.length === 13) digits = "0" + digits.slice(3);
  return digits;
}

export function isValidBdPhone(value) {
  return BD_MOBILE.test(normalizeBdPhone(value));
}
