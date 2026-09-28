"use client";

import { useState } from "react";
import InvoiceView from "./InvoiceView";

// A guest (or a customer looking at an order placed while logged out) proves the order is theirs the same way
// order tracking does: the phone number it was placed with. The backend checks it (POST /orders/track/invoice/,
// throttled) and answers the same 404 for a wrong number or phone. The phone is kept only in this component's
// memory for the PDF download — never stored or put in the URL.
export default function GuestInvoiceLookup({ number }) {
  const [phone, setPhone] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`/api/invoice/${encodeURIComponent(number)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone }),
      });
      const body = await res.json().catch(() => null);
      if (res.ok) setData(body);
      else if (res.status === 404) setError("That phone number doesn't match this order.");
      else if (res.status === 429) setError("Too many attempts. Please wait a minute and try again.");
      else setError(body?.error?.message || "Unable to load the invoice. Please try again.");
    } catch {
      setError("We couldn't reach the server. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  if (data) {
    return (
      <InvoiceView
        data={data}
        pdf={{ url: `/api/invoice/${encodeURIComponent(number)}/pdf`, method: "POST", body: { phone } }}
        back={{ href: "/shop", label: "Continue Shopping" }}
      />
    );
  }

  return (
    <form onSubmit={submit} className="dashboard-card mx-auto flex w-full max-w-md flex-col gap-4 rounded-2xl p-6">
      <div>
        <h1 className="custom-font text-2xl">View Invoice</h1>
        <p className="showcase-muted mt-1 text-sm">
          Order <span className="font-semibold">{number}</span>. Enter the phone number you placed the order with.
        </p>
      </div>
      <label className="flex flex-col gap-1.5 text-sm">
        Phone number
        <input
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          required
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          className="checkout-input rounded-lg px-3 py-2.5"
          placeholder="01XXXXXXXXX"
        />
      </label>
      {error && <p className="auth-error text-sm" role="alert">{error}</p>}
      <button type="submit" disabled={loading || !phone.trim()} className="auth-btn auth-btn--primary rounded-full px-6 py-3 text-sm font-medium">
        {loading ? "Checking…" : "View Invoice"}
      </button>
    </form>
  );
}
