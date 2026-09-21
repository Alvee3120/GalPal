"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCart } from "@/component/cart/CartProvider";
import ProductImage from "@/component/shared/ProductImage";
import SelectField from "@/component/shared/SelectField";
import { notify } from "@/lib/notify";
import { messageFor } from "@/lib/apiError";
import formatPrice from "@/lib/formatPrice";
import { variantLabel } from "@/lib/cartItem";
import { normalizeBdPhone } from "@/lib/phone";
import { BD_CITIES } from "@/lib/bdLocations";
import { calculateDeliveryCharge, DHAKA_ZONES, isDhaka } from "@/lib/delivery";
import { validateCheckout } from "@/lib/checkoutValidation";
import { addressToValues, initialValuesFor, rememberCheckoutAddress, useCheckoutAccount } from "@/lib/checkoutAccount";

const SHOP_ROUTE = "/shop";
const PLACE_ORDER_ERROR = "Unable to place your order. Please try again.";
const INITIAL = { fullName: "", phone: "", email: "", address: "", city: "", zone: "", note: "", saveDetails: true };

function Field({ id, label, required, optional, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
        {required && <span aria-hidden="true"> *</span>}
        {optional && <span className="showcase-muted font-normal"> (Optional)</span>}
      </label>
      {children}
    </div>
  );
}

function Skeleton() {
  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_26rem]">
      <div className="checkout-card rounded-2xl p-5 sm:p-6">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="product-skeleton__line mb-4 h-11 w-full animate-pulse rounded-lg" />
        ))}
      </div>
      <div className="order-summary rounded-2xl p-5 sm:p-6">
        <div className="product-skeleton__line h-32 w-full animate-pulse rounded-2xl" />
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="shop-empty flex flex-col items-center gap-3 rounded-2xl px-6 py-16 text-center">
      <p className="custom-font text-2xl">Your cart is empty</p>
      <p className="showcase-muted text-sm">Add something to your cart before checking out.</p>
      <Link href={SHOP_ROUTE} className="auth-btn auth-btn--primary mt-2 rounded-full px-8 py-3 text-sm font-medium">
        Continue Shopping
      </Link>
    </div>
  );
}

const OTHER_ADDRESS = "+ Use another address";

// Labels for the saved-address picker; a duplicate label gets a number so each option stays distinct.
function addressOptions(addresses) {
  const seen = new Map();
  return addresses.map((a) => {
    const base = `${a.label ? `${a.label} - ` : ""}${a.address_line}`;
    const count = (seen.get(base) ?? 0) + 1;
    seen.set(base, count);
    return { address: a, label: count > 1 ? `${base} (${count})` : base };
  });
}

// The /checkout page. Guest vs logged-in is decided here:
//   guest      -> empty form + "Save details to track orders" (on by default; makes the email required)
//   logged in  -> the form is prefilled from the customer's saved details (existing /account/profile + default
//                 address), with no save checkbox and no account-creation text; every field stays editable.
export default function CheckoutContent() {
  const { items, loading } = useCart();
  const account = useCheckoutAccount();

  if (loading || account.status === "loading") return <Skeleton />;
  if (items.length === 0) return <EmptyState />;
  return <CheckoutForm account={account.status === "authed" ? account : null} />;
}

// Contact + delivery form (left) and the order summary built from the SAME cart state as the drawer and the cart page
// (useCart) (right; below the form on mobile). The delivery charge comes only from calculateDeliveryCharge(); what is
// sent to the server is the form's city + zone, never an amount, and never a saved address the customer didn't pick.
function CheckoutForm({ account }) {
  const router = useRouter();
  const { items, itemCount, subtotal, discount, currencySymbol, refreshCart } = useCart();
  const loggedIn = account !== null;
  const [values, setValues] = useState(() => (loggedIn ? initialValuesFor(account.profile, account.addresses) : INITIAL));
  const options = loggedIn ? addressOptions(account.addresses) : [];
  const [savedChoice, setSavedChoice] = useState(() => {
    const preferred = options.find((o) => o.address.is_default) ?? options[0];
    return preferred ? preferred.label : "";
  });
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false); // blocks a double-click before React re-renders the disabled button
  const emailLocked = loggedIn && Boolean(account.profile.email); // the account's own email is not a new-account field

  const set = (name) => (e) => setValues((v) => ({ ...v, [name]: e.target.value }));

  // Leaving Dhaka clears the zone (it is hidden and must not linger); entering Dhaka starts with no zone chosen.
  function changeCity(city) {
    setValues((v) => ({ ...v, city, zone: "" }));
  }

  // Picking a saved address fills the address fields as a starting point (still editable); "use another address" clears them.
  function chooseSaved(label) {
    setSavedChoice(label);
    const picked = options.find((o) => o.label === label);
    setValues((v) =>
      picked ? { ...v, ...addressToValues(picked.address, account.profile) } : { ...v, address: "", city: "", zone: "" },
    );
  }

  const deliveryCharge = calculateDeliveryCharge(values.city, values.zone);
  const orderTotal = Number(subtotal) - Number(discount) + (deliveryCharge ?? 0);
  const hasDiscount = Number(discount) > 0;
  const hasUnavailable = items.some((item) => item.is_available === false);
  const dhaka = isDhaka(values.city);

  async function handleSubmit(e) {
    e.preventDefault();
    if (submittingRef.current) return;

    // A logged-in customer already has the account, so "save details" never applies (and never forces an email).
    const problem = validateCheckout({ ...values, saveDetails: loggedIn ? false : values.saveDetails }, { itemCount, hasUnavailable });
    if (problem) {
      notify.error(problem);
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);
    try {
      const res = await fetch("/api/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: values.fullName.trim(),
          phone: normalizeBdPhone(values.phone),
          email: values.email.trim() || null,
          address: values.address.trim(),
          district: values.city,
          area: dhaka ? values.zone : "",
          note: values.note.trim() || null,
          // Only a guest chooses this; a logged-in customer is identified by their session, not by anything sent here.
          ...(loggedIn ? {} : { save_details: values.saveDetails }),
        }),
        cache: "no-store",
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        notify.error(messageFor({ status: res.status, details: data?.error?.details }, PLACE_ORDER_ERROR));
        return;
      }
      notify.success("Order placed successfully!");
      if (loggedIn) await rememberCheckoutAddress(values, account.addresses);
      await refreshCart();
      router.push(`/order-confirmation${data?.order_number ? `?number=${encodeURIComponent(data.order_number)}` : ""}`);
    } catch {
      notify.error(PLACE_ORDER_ERROR);
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_26rem] lg:items-start">
      <form id="checkout-form" onSubmit={handleSubmit} noValidate className="checkout-card rounded-2xl p-5 sm:p-6">
        <h2 className="custom-font text-xl">Contact &amp; Delivery Information</h2>

        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <Field id="checkout-name" label="Full Name" required>
            <input id="checkout-name" name="name" type="text" autoComplete="name" placeholder="Enter your full name" value={values.fullName} onChange={set("fullName")} className="checkout-input rounded-lg px-3 py-2.5 text-sm" />
          </Field>
          <Field id="checkout-phone" label="Phone Number" required>
            <input id="checkout-phone" name="tel" type="tel" inputMode="tel" autoComplete="tel" placeholder="Enter your phone number" value={values.phone} onChange={set("phone")} className="checkout-input rounded-lg px-3 py-2.5 text-sm" />
          </Field>
          <div className="sm:col-span-2">
            <Field id="checkout-email" label="Email" required={!loggedIn && values.saveDetails} optional={!loggedIn ? !values.saveDetails : !emailLocked}>
              <input
                id="checkout-email"
                name="email"
                type="email"
                autoComplete="email"
                placeholder="Enter your email address"
                value={values.email}
                onChange={set("email")}
                readOnly={emailLocked}
                className="checkout-input rounded-lg px-3 py-2.5 text-sm read-only:cursor-default read-only:opacity-70"
              />
            </Field>
          </div>
          {options.length > 0 && (
            <div className="sm:col-span-2">
              <Field id="checkout-saved-address" label="Saved Address">
                <SelectField id="checkout-saved-address" value={savedChoice} onChange={chooseSaved} options={[...options.map((o) => o.label), OTHER_ADDRESS]} placeholder="Choose a saved address" />
              </Field>
            </div>
          )}
          <div className="sm:col-span-2">
            <Field id="checkout-address" label="Address" required>
              <input id="checkout-address" name="street-address" type="text" autoComplete="street-address" placeholder="Enter your full delivery address" value={values.address} onChange={set("address")} className="checkout-input rounded-lg px-3 py-2.5 text-sm" />
            </Field>
          </div>
          <Field id="checkout-city" label="City" required>
            <SelectField id="checkout-city" name="city" value={values.city} onChange={changeCity} options={BD_CITIES} placeholder="Select City" />
          </Field>
          {dhaka && (
            <Field id="checkout-zone" label="Zone" required>
              <SelectField id="checkout-zone" name="zone" value={values.zone} onChange={(zone) => setValues((v) => ({ ...v, zone }))} options={DHAKA_ZONES} placeholder="Select Zone" />
            </Field>
          )}
          <div className="sm:col-span-2">
            <Field id="checkout-note" label="Order Note" optional>
              <textarea id="checkout-note" name="note" rows={3} placeholder="Add a note about your order (optional)" value={values.note} onChange={set("note")} className="checkout-input resize-y rounded-lg px-3 py-2.5 text-sm" />
            </Field>
          </div>
        </div>

        {!loggedIn && (
          <label htmlFor="checkout-save" className="mt-6 flex cursor-pointer items-start gap-3">
            <input
              id="checkout-save"
              type="checkbox"
              checked={values.saveDetails}
              onChange={(e) => setValues((v) => ({ ...v, saveDetails: e.target.checked }))}
              className="shop-checkbox mt-1 h-4 w-4 shrink-0"
            />
            <span>
              <span className="block text-sm font-medium">Save details to track orders</span>
              <span className="showcase-muted block text-xs">We&apos;ll create an account using your email to make your next order faster.</span>
            </span>
          </label>
        )}
      </form>

      <aside className="order-summary rounded-2xl p-5 sm:p-6 lg:sticky lg:top-24">
        <h2 className="custom-font text-xl">Order Summary</h2>

        <ul className="checkout-lines mt-4 flex flex-col">
          {items.map((item) => (
            <li key={item.id} className="flex items-start gap-3 py-3">
              <div className="cart-thumb relative h-16 w-16 shrink-0 overflow-hidden">
                <ProductImage src={item.product.feature_image} alt="" tight />
              </div>
              <div className="min-w-0 flex-1">
                <p className="line-clamp-2 text-sm font-medium leading-snug">{item.product.name}</p>
                {item.variant && <p className="showcase-muted mt-0.5 text-xs">{variantLabel(item.variant)}</p>}
                <p className="showcase-muted mt-0.5 text-xs">
                  {item.quantity} × {formatPrice(item.unit_price, currencySymbol)}
                </p>
              </div>
              <p className="shrink-0 text-sm font-medium">{formatPrice(item.line_total, currencySymbol)}</p>
            </li>
          ))}
        </ul>

        <dl className="mt-3 flex flex-col gap-2 border-t pt-4 text-sm">
          <div className="flex items-center justify-between">
            <dt>Subtotal</dt>
            <dd className="font-medium">{formatPrice(subtotal, currencySymbol)}</dd>
          </div>
          {hasDiscount && (
            <div className="flex items-center justify-between">
              <dt>Discount</dt>
              <dd className="font-medium">-{formatPrice(discount, currencySymbol)}</dd>
            </div>
          )}
          <div className="flex items-center justify-between">
            <dt>Delivery Charge</dt>
            <dd className="font-medium" data-testid="delivery-charge">
              {deliveryCharge === null ? <span className="showcase-muted font-normal">{dhaka ? "Select zone" : "Select city"}</span> : formatPrice(deliveryCharge, currencySymbol)}
            </dd>
          </div>
        </dl>

        <div className="mt-4 flex items-baseline justify-between border-t pt-4">
          <span className="text-base font-semibold">Total</span>
          <span className="text-xl font-semibold" data-testid="order-total">
            {formatPrice(orderTotal, currencySymbol)}
          </span>
        </div>

        <button
          type="submit"
          form="checkout-form"
          disabled={submitting}
          className="auth-btn auth-btn--primary mt-5 block w-full rounded-full py-3 text-center text-sm font-medium"
        >
          {submitting ? "Placing Order..." : "Place Order"}
        </button>
      </aside>
    </div>
  );
}
