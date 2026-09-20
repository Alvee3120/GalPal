const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";
const REVALIDATE_SECONDS = 60;
export const DEFAULT_CURRENCY_SYMBOL = "৳";

// Currency comes from the site settings so it is never hardcoded; falls back to the default symbol.
export async function getCurrencySymbol() {
  try {
    const res = await fetch(`${API_BASE_URL}/site-settings/`, { next: { revalidate: REVALIDATE_SECONDS } });
    if (!res.ok) return DEFAULT_CURRENCY_SYMBOL;
    const data = await res.json();
    return data.currency_symbol || DEFAULT_CURRENCY_SYMBOL;
  } catch {
    return DEFAULT_CURRENCY_SYMBOL;
  }
}
