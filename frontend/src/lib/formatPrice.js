// Whole numbers drop the decimals ("2200.00" -> "2,200"); fractional prices keep two.
export default function formatPrice(value, symbol = "") {
  const n = Number(value);
  if (!Number.isFinite(n)) return "";
  const text = n.toLocaleString("en-US", {
    minimumFractionDigits: Number.isInteger(n) ? 0 : 2,
    maximumFractionDigits: 2,
  });
  return `${symbol}${text}`;
}
