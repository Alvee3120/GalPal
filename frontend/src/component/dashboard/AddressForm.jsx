"use client";

import { useEffect, useRef, useState } from "react";
import { FiX } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { isValidBdPhone, normalizeBdPhone } from "@/lib/phone";
import { BD_CITIES } from "@/lib/bdLocations";
import { isDhaka, withCurrent, zoneFromArea } from "@/lib/delivery";
import useDhakaZones from "@/lib/useDhakaZones";
import SelectField from "@/component/shared/SelectField";

const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"]), input:not([disabled]), select:not([disabled])';

function valuesFrom(address) {
  const city = BD_CITIES.find((c) => c.toLowerCase() === String(address?.district ?? "").toLowerCase()) ?? "";
  const zone = zoneFromArea(city, address?.area);
  return {
    label: address?.label ?? "",
    fullName: address?.full_name ?? "",
    phone: address?.phone ?? "",
    address: address?.address_line ?? "",
    city,
    zone,
    isDefault: address?.is_default ?? false,
  };
}

// Same required fields and Dhaka-zone rule as checkout (lib/checkoutValidation.js's address/city/zone checks) —
// not a second, possibly-diverging delivery rule.
function validate(values) {
  if (!values.fullName.trim()) return "Please enter the recipient's full name.";
  if (!isValidBdPhone(values.phone)) return "Please enter a valid phone number.";
  if (!values.address.trim()) return "Please enter the address.";
  if (!values.city) return "Please select a city.";
  if (isDhaka(values.city) && !values.zone) return "Please select a Dhaka zone.";
  return null;
}

// Add/Edit Address modal. `address` null = add; an address object = edit (prefilled, same form, PATCHes that id
// instead of POSTing a new one). Reuses the same modal mechanics as NotifyMeModal/ConfirmDialog (.stock-modal*)
// and the same SelectField/city/zone dataset checkout uses, so the two never drift into different location lists.
export default function AddressForm({ open, address, onClose, onSubmit }) {
  const isEdit = Boolean(address);
  const [values, setValues] = useState(() => valuesFrom(address));
  const dhakaZones = useDhakaZones();
  const [saving, setSaving] = useState(false);
  const panelRef = useRef(null);
  const firstFieldRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const raf = requestAnimationFrame(() => firstFieldRef.current?.focus());
    const onKeyDown = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "Tab") {
        const nodes = [...(panelRef.current?.querySelectorAll(FOCUSABLE) ?? [])];
        if (!nodes.length) return;
        const first = nodes[0];
        const last = nodes[nodes.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      cancelAnimationFrame(raf);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  function changeCity(city) {
    setValues((v) => ({ ...v, city, zone: "" }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (saving) return;
    const problem = validate(values);
    if (problem) {
      notify.error(problem);
      return;
    }
    setSaving(true);
    try {
      await onSubmit({
        label: values.label.trim(),
        full_name: values.fullName.trim(),
        phone: normalizeBdPhone(values.phone),
        district: values.city,
        area: isDhaka(values.city) ? values.zone : "",
        address_line: values.address.trim(),
        is_default: values.isDefault,
      });
    } finally {
      setSaving(false);
    }
  }

  const dhaka = isDhaka(values.city);

  return (
    <div className="stock-modal fixed inset-0 z-90" data-open={open} inert={!open}>
      <div className="stock-modal__backdrop absolute inset-0" aria-hidden="true" />
      <div className="fixed inset-0 flex items-center justify-center p-4" onClick={(e) => e.target === e.currentTarget && onClose()}>
        <div
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby="address-form-title"
          className="stock-modal__panel relative w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-(--radius-card) p-5 sm:p-6"
        >
          <button type="button" onClick={onClose} aria-label="Close" className="cart-close absolute right-3 top-3 flex h-9 w-9 items-center justify-center rounded-full">
            <FiX className="h-5 w-5" aria-hidden="true" />
          </button>

          <h2 id="address-form-title" className="custom-font pr-8 text-xl">
            {isEdit ? "Edit Address" : "Add New Address"}
          </h2>

          <form onSubmit={handleSubmit} noValidate className="mt-5 grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="addr-label" className="text-sm font-medium">
                Label <span className="showcase-muted font-normal">(Optional)</span>
              </label>
              <input
                ref={firstFieldRef}
                id="addr-label"
                type="text"
                placeholder="Home, Office, ..."
                value={values.label}
                onChange={(e) => setValues((v) => ({ ...v, label: e.target.value }))}
                className="checkout-input rounded-lg px-3 py-2.5 text-sm"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="addr-name" className="text-sm font-medium">
                Full Name <span aria-hidden="true">*</span>
              </label>
              <input
                id="addr-name"
                type="text"
                autoComplete="name"
                placeholder="Enter the recipient's full name"
                value={values.fullName}
                onChange={(e) => setValues((v) => ({ ...v, fullName: e.target.value }))}
                className="checkout-input rounded-lg px-3 py-2.5 text-sm"
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="addr-phone" className="text-sm font-medium">
                Phone Number <span aria-hidden="true">*</span>
              </label>
              <input
                id="addr-phone"
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                placeholder="Enter phone number"
                value={values.phone}
                onChange={(e) => setValues((v) => ({ ...v, phone: e.target.value }))}
                className="checkout-input rounded-lg px-3 py-2.5 text-sm"
              />
            </div>

            <div className="sm:col-span-2">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="addr-address" className="text-sm font-medium">
                  Address <span aria-hidden="true">*</span>
                </label>
                <input
                  id="addr-address"
                  type="text"
                  autoComplete="street-address"
                  placeholder="House, road, area"
                  value={values.address}
                  onChange={(e) => setValues((v) => ({ ...v, address: e.target.value }))}
                  className="checkout-input rounded-lg px-3 py-2.5 text-sm"
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="addr-city" className="text-sm font-medium">
                City <span aria-hidden="true">*</span>
              </label>
              <SelectField id="addr-city" value={values.city} onChange={changeCity} options={BD_CITIES} placeholder="Select City" />
            </div>

            {dhaka && (
              <div className="flex flex-col gap-1.5">
                <label htmlFor="addr-zone" className="text-sm font-medium">
                  Zone <span aria-hidden="true">*</span>
                </label>
                <SelectField id="addr-zone" value={values.zone} onChange={(zone) => setValues((v) => ({ ...v, zone }))} options={withCurrent(dhakaZones, values.zone)} placeholder="Select Zone" />
              </div>
            )}

            <div className="sm:col-span-2">
              <label htmlFor="addr-default" className="flex cursor-pointer items-center gap-2.5">
                <input
                  id="addr-default"
                  type="checkbox"
                  checked={values.isDefault}
                  onChange={(e) => setValues((v) => ({ ...v, isDefault: e.target.checked }))}
                  className="shop-checkbox h-4 w-4 shrink-0"
                />
                <span className="text-sm">Set as default address</span>
              </label>
            </div>

            <div className="sm:col-span-2">
              <button type="submit" disabled={saving} className="auth-btn auth-btn--primary w-full rounded-full py-3 text-sm font-medium sm:w-auto sm:px-8">
                {saving ? "Saving..." : "Save Address"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
