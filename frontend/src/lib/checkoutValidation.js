import { isDhaka } from "./delivery";
import { isValidBdPhone } from "./phone";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

// First problem with the checkout form as a friendly, toast-ready sentence, or null when it is valid. An
// out-of-stock item does NOT block checkout by itself — the backend leaves it in the cart and orders only the
// available ones (see apps.orders.services.checkout) — only a cart with NO available items at all is blocked,
// matching the backend's own "cart_all_unavailable" error exactly.
export function validateCheckout(values, { itemCount, availableCount }) {
  if (itemCount === 0) return "Your cart is empty.";
  if (availableCount === 0) return "All items in your cart are currently out of stock.";
  if (!values.fullName.trim()) return "Please enter your full name.";
  if (!isValidBdPhone(values.phone)) return "Please enter a valid phone number.";
  const email = values.email.trim();
  if (values.saveDetails && !email) return "Email is required when saving details to track orders.";
  if (email && !EMAIL.test(email)) return "Please enter a valid email address.";
  if (!values.address.trim()) return "Please enter your delivery address.";
  if (!values.city) return "Please select your city.";
  if (isDhaka(values.city) && !values.zone) return "Please select a Dhaka zone.";
  return null;
}
