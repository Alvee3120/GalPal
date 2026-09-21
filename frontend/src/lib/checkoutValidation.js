import { isDhaka, DHAKA_ZONES } from "./delivery";
import { isValidBdPhone } from "./phone";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

// First problem with the checkout form as a friendly, toast-ready sentence, or null when it is valid.
export function validateCheckout(values, { itemCount, hasUnavailable }) {
  if (itemCount === 0) return "Your cart is empty.";
  if (hasUnavailable) return "Some items in your cart are unavailable. Please review your cart.";
  if (!values.fullName.trim()) return "Please enter your full name.";
  if (!isValidBdPhone(values.phone)) return "Please enter a valid phone number.";
  const email = values.email.trim();
  if (values.saveDetails && !email) return "Email is required when saving details to track orders.";
  if (email && !EMAIL.test(email)) return "Please enter a valid email address.";
  if (!values.address.trim()) return "Please enter your delivery address.";
  if (!values.city) return "Please select your city.";
  if (isDhaka(values.city) && !DHAKA_ZONES.includes(values.zone)) return "Please select a Dhaka zone.";
  return null;
}
