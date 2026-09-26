"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FiMinus, FiPlus, FiX } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { messageFor } from "@/lib/apiError";
import { isValidBdPhone, normalizeBdPhone } from "@/lib/phone";
import { BD_CITIES } from "@/lib/bdLocations";
import { DHAKA_ZONES, isDhaka } from "@/lib/delivery";
import formatPrice from "@/lib/formatPrice";
import SelectField from "@/component/shared/SelectField";
import ProductImage from "@/component/shared/ProductImage";
import ProductSearchPicker from "./ProductSearchPicker";
import { ORDER_SOURCE_LABEL, PAYMENT_METHOD_LABEL } from "@/lib/orderStatus";
import { useStaffHref } from "@/lib/staffPaths";

// "website" is reserved for real storefront checkout (apps.orders.models.OrderSource docstring) — staff pick
// from everything else.
const SOURCE_OPTIONS = Object.keys(ORDER_SOURCE_LABEL).filter((s) => s !== "website");
const PAYMENT_OPTIONS = Object.keys(PAYMENT_METHOD_LABEL);

const lineKey = (productId, variantId) => `${productId}:${variantId ?? "base"}`;

// Add Order: a CCE/Admin placing an order on a customer's behalf. Creation goes through the EXISTING
// POST /admin/orders/ (apps.orders.services.create_manual_order) — the backend validates and locks stock,
// resolves the delivery charge from the address, and computes every price; nothing here is trusted beyond what
// products/quantities were picked. `create_manual_order` always lands the order as "pending" (a deliberate,
// tested backend guarantee — see apps/orders/tests/test_admin_api.py's
// test_a_cce_cannot_type_a_shipping_charge), so getting to "Confirmed" per this task's spec is a second, explicit
// call to the same status-change action the order detail page uses (POST /admin/orders/<id>/status/) — not a
// new status path invented on the frontend.
export default function AddOrderForm({ currencySymbol }) {
  const to = useStaffHref();
  const router = useRouter();

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [city, setCity] = useState("");
  const [zone, setZone] = useState("");
  const [addressLine, setAddressLine] = useState("");
  const [postalCode, setPostalCode] = useState("");
  const [note, setNote] = useState("");
  const [source, setSource] = useState("facebook");
  const [paymentMethod, setPaymentMethod] = useState("cod");
  const [couponCode, setCouponCode] = useState("");
  const [customerId, setCustomerId] = useState(null);
  const [savedAddresses, setSavedAddresses] = useState([]);
  const [lookingUp, setLookingUp] = useState(false);

  const [products, setProducts] = useState([]); // [{key, product_id, variant_id, name, variant_label, image, unit_price, quantity, stock}]
  const [shipping, setShipping] = useState(null); // { charge, zone_name, free_shipping_reason } | null
  const [shippingLoading, setShippingLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const dhaka = isDhaka(city);
  const subtotal = products.reduce((sum, p) => sum + Number(p.unit_price) * p.quantity, 0);
  const total = subtotal + Number(shipping?.charge ?? 0);

  async function refreshShipping(nextCity, nextZone, nextSubtotal) {
    // Quote as soon as a city is picked, even before any product is added (subtotal 0), so the CCE can tell
    // the customer the delivery charge up front; adding products re-quotes for free-shipping thresholds.
    if (!nextCity) {
      setShipping(null);
      return;
    }
    setShippingLoading(true);
    try {
      const params = new URLSearchParams({ district: nextCity, area: isDhaka(nextCity) ? nextZone : "", subtotal: String(nextSubtotal) });
      const res = await fetch(`/api/admin/orders/helpers/shipping?${params.toString()}`, { cache: "no-store" });
      const data = await res.json().catch(() => null);
      setShipping(res.ok ? data : null);
    } catch {
      setShipping(null);
    } finally {
      setShippingLoading(false);
    }
  }

  function changeCity(nextCity) {
    setCity(nextCity);
    setZone("");
    refreshShipping(nextCity, "", subtotal);
  }

  function changeZone(nextZone) {
    setZone(nextZone);
    refreshShipping(city, nextZone, subtotal);
  }

  async function findCustomer() {
    if (!isValidBdPhone(phone)) {
      notify.error("Please enter a valid phone number to search.");
      return;
    }
    setLookingUp(true);
    try {
      const res = await fetch(`/api/admin/orders/helpers/customers?phone=${encodeURIComponent(normalizeBdPhone(phone))}`, { cache: "no-store" });
      if (res.status === 404) {
        notify.error("No customer found with this phone number. This will be a guest order.");
        setCustomerId(null);
        setSavedAddresses([]);
        return;
      }
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        notify.error("Unable to look up this customer right now.");
        return;
      }
      setCustomerId(data.id);
      if (!name.trim()) setName(data.full_name);
      setSavedAddresses(data.addresses ?? []);
      notify.success(`Found ${data.full_name} — ${data.addresses?.length ?? 0} saved address${data.addresses?.length === 1 ? "" : "es"}.`);
    } catch {
      notify.error("Unable to look up this customer right now.");
    } finally {
      setLookingUp(false);
    }
  }

  function applySavedAddress(addr) {
    setAddressLine(addr.address_line);
    setPostalCode(addr.postal_code ?? "");
    const matchedCity = BD_CITIES.find((c) => c.toLowerCase() === String(addr.district ?? "").toLowerCase()) ?? "";
    setCity(matchedCity);
    const matchedZone = isDhaka(matchedCity) ? (DHAKA_ZONES.find((z) => z.toLowerCase() === String(addr.area ?? "").toLowerCase()) ?? "") : "";
    setZone(matchedZone);
    refreshShipping(matchedCity, matchedZone, subtotal);
  }

  function handleAddProduct(row, quantity) {
    const key = lineKey(row.product_id, row.variant_id);
    let nextProducts;
    const existing = products.find((p) => p.key === key);
    if (existing) {
      const cap = row.stock ?? existing.stock;
      const nextQty = cap !== null && cap !== undefined ? Math.min(existing.quantity + quantity, cap) : existing.quantity + quantity;
      nextProducts = products.map((p) => (p.key === key ? { ...p, quantity: nextQty, stock: cap } : p));
    } else {
      nextProducts = [
        ...products,
        {
          key,
          product_id: row.product_id,
          variant_id: row.variant_id,
          name: row.name,
          variant_label: row.variant_label,
          image: row.image,
          unit_price: row.price,
          quantity,
          stock: row.stock,
        },
      ];
    }
    setProducts(nextProducts);
    notify.success("Product added to order.");
    refreshShipping(city, zone, nextProducts.reduce((sum, p) => sum + Number(p.unit_price) * p.quantity, 0));
  }

  function changeQuantity(key, delta) {
    const nextProducts = products
      .map((p) => {
        if (p.key !== key) return p;
        const nextQty = p.quantity + delta;
        if (nextQty < 1) return p;
        if (p.stock !== null && p.stock !== undefined && nextQty > p.stock) return p;
        return { ...p, quantity: nextQty };
      })
      .filter(Boolean);
    setProducts(nextProducts);
    refreshShipping(city, zone, nextProducts.reduce((sum, p) => sum + Number(p.unit_price) * p.quantity, 0));
  }

  function removeProduct(key) {
    const nextProducts = products.filter((p) => p.key !== key);
    setProducts(nextProducts);
    refreshShipping(city, zone, nextProducts.reduce((sum, p) => sum + Number(p.unit_price) * p.quantity, 0));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting) return;
    if (!name.trim()) return notify.error("Please enter the customer's name.");
    if (!isValidBdPhone(phone)) return notify.error("Please enter a valid phone number.");
    if (!city) return notify.error("Please select a city.");
    if (dhaka && !zone) return notify.error("Please select a Dhaka zone.");
    if (!addressLine.trim()) return notify.error("Please enter the delivery address.");
    if (products.length === 0) return notify.error("Please add at least one product.");

    setSubmitting(true);
    try {
      const res = await fetch("/api/admin/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          phone: normalizeBdPhone(phone),
          email: email.trim(),
          district: city,
          area: dhaka ? zone : "",
          address_line: addressLine.trim(),
          postal_code: postalCode.trim(),
          note: note.trim(),
          source,
          payment_method: paymentMethod,
          coupon: couponCode.trim(),
          customer_id: customerId ?? undefined,
          items: products.map((p) => ({ product_id: p.product_id, variant_id: p.variant_id ?? undefined, quantity: p.quantity })),
        }),
        cache: "no-store",
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        notify.error(messageFor({ status: res.status, details: data?.error?.details }, "Unable to create order. Please try again."));
        return;
      }

      const order = data.order;
      notify.success("Order created successfully.");

      try {
        const confirmRes = await fetch(`/api/admin/orders/${order.id}/status`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "confirmed" }),
          cache: "no-store",
        });
        if (confirmRes.ok) notify.success("Order confirmed successfully.");
        else notify.error("Order created, but couldn't be confirmed automatically. Please confirm it from the order page.");
      } catch {
        notify.error("Order created, but couldn't be confirmed automatically. Please confirm it from the order page.");
      }

      router.push(to(`/dashboard/CCE/orders/${order.id}`));
    } catch {
      notify.error("Unable to create order. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-6">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-start">
        <div className="flex flex-col gap-6">
          <section className="dashboard-card rounded-2xl p-5 sm:p-6">
            <h2 className="custom-font text-lg">Customer Information</h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="ao-name" className="text-sm font-medium">
                  Name <span aria-hidden="true">*</span>
                </label>
                <input id="ao-name" type="text" value={name} onChange={(e) => setName(e.target.value)} className="checkout-input rounded-lg px-3 py-2.5 text-sm" />
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="ao-phone" className="text-sm font-medium">
                  Phone Number <span aria-hidden="true">*</span>
                </label>
                <div className="flex gap-2">
                  <input
                    id="ao-phone"
                    type="tel"
                    inputMode="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="checkout-input min-w-0 flex-1 rounded-lg px-3 py-2.5 text-sm"
                  />
                  <button
                    type="button"
                    onClick={findCustomer}
                    disabled={lookingUp}
                    className="auth-btn auth-btn--outline shrink-0 rounded-lg px-3 py-2.5 text-xs font-medium"
                  >
                    {lookingUp ? "Searching..." : "Find Customer"}
                  </button>
                </div>
              </div>

              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <label htmlFor="ao-email" className="text-sm font-medium">
                  Email <span className="showcase-muted font-normal">(Optional)</span>
                </label>
                <input id="ao-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="checkout-input rounded-lg px-3 py-2.5 text-sm" />
              </div>

              {savedAddresses.length > 0 && (
                <div className="flex flex-col gap-1.5 sm:col-span-2">
                  <span className="text-sm font-medium">Saved Addresses</span>
                  <div className="flex flex-wrap gap-2">
                    {savedAddresses.map((addr) => (
                      <button
                        key={addr.id}
                        type="button"
                        onClick={() => applySavedAddress(addr)}
                        className="product-card__chip rounded-full px-3 py-1.5 text-xs font-medium"
                      >
                        {addr.label || addr.district} &middot; {addr.address_line}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex flex-col gap-1.5">
                <label htmlFor="ao-city" className="text-sm font-medium">
                  City <span aria-hidden="true">*</span>
                </label>
                <SelectField id="ao-city" value={city} onChange={changeCity} options={BD_CITIES} placeholder="Select City" />
              </div>

              {dhaka && (
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="ao-zone" className="text-sm font-medium">
                    Zone <span aria-hidden="true">*</span>
                  </label>
                  <SelectField id="ao-zone" value={zone} onChange={changeZone} options={DHAKA_ZONES} placeholder="Select Zone" />
                </div>
              )}

              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <label htmlFor="ao-address" className="text-sm font-medium">
                  Address <span aria-hidden="true">*</span>
                </label>
                <input
                  id="ao-address"
                  type="text"
                  value={addressLine}
                  onChange={(e) => setAddressLine(e.target.value)}
                  placeholder="House, road, area"
                  className="checkout-input rounded-lg px-3 py-2.5 text-sm"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="ao-postal" className="text-sm font-medium">
                  Postal Code <span className="showcase-muted font-normal">(Optional)</span>
                </label>
                <input id="ao-postal" type="text" value={postalCode} onChange={(e) => setPostalCode(e.target.value)} className="checkout-input rounded-lg px-3 py-2.5 text-sm" />
              </div>

              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <label htmlFor="ao-note" className="text-sm font-medium">
                  Note <span className="showcase-muted font-normal">(Optional)</span>
                </label>
                <textarea id="ao-note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} className="checkout-input rounded-lg px-3 py-2.5 text-sm" />
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="ao-source" className="text-sm font-medium">
                  Order Source <span aria-hidden="true">*</span>
                </label>
                <select id="ao-source" value={source} onChange={(e) => setSource(e.target.value)} className="checkout-input rounded-lg px-3 py-2.5 text-sm">
                  {SOURCE_OPTIONS.map((s) => (
                    <option key={s} value={s}>
                      {ORDER_SOURCE_LABEL[s]}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="ao-payment" className="text-sm font-medium">
                  Payment Method
                </label>
                <select id="ao-payment" value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)} className="checkout-input rounded-lg px-3 py-2.5 text-sm">
                  {PAYMENT_OPTIONS.map((p) => (
                    <option key={p} value={p}>
                      {PAYMENT_METHOD_LABEL[p]}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </section>

          <section className="dashboard-card rounded-2xl p-5 sm:p-6">
            <h2 className="custom-font text-lg">Add Product</h2>
            <div className="mt-4">
              <ProductSearchPicker currencySymbol={currencySymbol} onAdd={handleAddProduct} />
            </div>
          </section>

          {products.length > 0 && (
            <section className="dashboard-card rounded-2xl p-5 sm:p-6">
              <h2 className="custom-font text-lg">Order Products</h2>
              <ul className="checkout-lines mt-4 flex flex-col">
                {products.map((p) => (
                  <li key={p.key} className="flex items-start gap-3 py-3 first:pt-0">
                    <div className="cart-thumb relative h-14 w-14 shrink-0 overflow-hidden">
                      <ProductImage src={p.image} alt="" tight />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium leading-snug">{p.name}</p>
                      {p.variant_label && <p className="showcase-muted mt-0.5 text-xs">{p.variant_label}</p>}
                      <p className="showcase-muted mt-0.5 text-xs">{formatPrice(p.unit_price, currencySymbol)} each</p>
                      <div className="mt-2 flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => changeQuantity(p.key, -1)}
                          disabled={p.quantity <= 1}
                          aria-label={`Decrease quantity of ${p.name}`}
                          className="cart-qty__btn flex h-7 w-7 items-center justify-center rounded-full"
                        >
                          <FiMinus className="h-3 w-3" aria-hidden="true" />
                        </button>
                        <span className="w-7 text-center text-sm tabular-nums">{p.quantity}</span>
                        <button
                          type="button"
                          onClick={() => changeQuantity(p.key, 1)}
                          disabled={p.stock !== null && p.stock !== undefined && p.quantity >= p.stock}
                          aria-label={`Increase quantity of ${p.name}`}
                          className="cart-qty__btn flex h-7 w-7 items-center justify-center rounded-full"
                        >
                          <FiPlus className="h-3 w-3" aria-hidden="true" />
                        </button>
                      </div>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-2">
                      <p className="text-sm font-medium">{formatPrice(Number(p.unit_price) * p.quantity, currencySymbol)}</p>
                      <button type="button" onClick={() => removeProduct(p.key)} aria-label={`Remove ${p.name}`} className="auth-error">
                        <FiX className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>

        <aside className="order-summary flex flex-col gap-4 rounded-2xl p-5 sm:p-6 lg:sticky lg:top-24">
          <h2 className="custom-font text-lg">Order Summary</h2>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="ao-coupon" className="text-sm font-medium">
              Coupon Code <span className="showcase-muted font-normal">(Optional)</span>
            </label>
            <input
              id="ao-coupon"
              type="text"
              value={couponCode}
              onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
              className="checkout-input rounded-lg px-3 py-2.5 text-sm"
            />
          </div>

          <dl className="flex flex-col gap-2 border-t pt-4 text-sm">
            <div className="flex items-center justify-between">
              <dt>Subtotal</dt>
              <dd className="font-medium">{formatPrice(subtotal, currencySymbol)}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt>Delivery Charge</dt>
              <dd className="font-medium">{shippingLoading ? "..." : shipping ? formatPrice(shipping.charge, currencySymbol) : "—"}</dd>
            </div>
          </dl>

          <div className="flex items-baseline justify-between border-t pt-4">
            <span className="text-base font-semibold">Total</span>
            <span className="text-xl font-semibold">{formatPrice(total, currencySymbol)}</span>
          </div>
          <p className="showcase-muted text-xs">Discount, tax and the final total are calculated by the server when the order is created.</p>

          <button type="submit" disabled={submitting} className="auth-btn auth-btn--primary rounded-full py-3 text-sm font-medium">
            {submitting ? "Creating Order..." : "Create Order"}
          </button>
        </aside>
      </div>
    </form>
  );
}
