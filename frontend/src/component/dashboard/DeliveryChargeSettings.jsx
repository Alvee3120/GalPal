"use client";

import { useState } from "react";
import { FiAlertCircle, FiPlus, FiRefreshCw, FiTruck, FiX } from "react-icons/fi";
import { notify } from "@/lib/notify";
import formatPrice from "@/lib/formatPrice";
import { errorText } from "@/lib/productAdmin";

// The three zones the storefront uses (apps.shipping seed + migration 0003), in checkout's order. Any other zone the
// Admin has added shows after them.
const ORDER = ["inside-dhaka", "dhaka-outer-zones", "outside-dhaka"];
const WHERE = {
  "inside-dhaka": "Dhaka city — the Dhaka Sadar zone at checkout.",
  "dhaka-outer-zones": "The Dhaka areas listed below — each shows as a zone at checkout.",
  "outside-dhaka": "Every city outside Dhaka.",
};
const MONEY = /^\d+(\.\d{1,2})?$/;

async function shippingFetch(path, { method = "GET", body } = {}) {
  try {
    const res = await fetch(`/api/admin/shipping/${path}`, {
      method,
      cache: "no-store",
      body: body === undefined ? undefined : JSON.stringify(body),
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    });
    return { ok: res.ok, status: res.status, data: await res.json().catch(() => null) };
  } catch {
    return { ok: false, status: 0, data: null };
  }
}

const OUTER = "dhaka-outer-zones";
const DHAKA = "Dhaka";
const SADAR = "Dhaka Sadar"; // checkout's "rest of Dhaka" choice (priced by Inside Dhaka), so never an outer area

// The Dhaka areas of the outer zone, and Dhaka's district id (from any zone's coverage, as the admin API reports it).
const outerAreasOf = (zones) => zones?.find((z) => z.slug === OUTER)?.coverage?.find((c) => c.district_name === DHAKA)?.areas ?? [];
const dhakaIdOf = (zones) => zones?.flatMap((z) => z.coverage ?? []).find((c) => c.district_name === DHAKA)?.district_id ?? null;
const sameList = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);

const sortZones = (zones) =>
  [...zones].sort((a, b) => {
    const ia = ORDER.indexOf(a.slug);
    const ib = ORDER.indexOf(b.slug);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib) || a.sort_order - b.sort_order;
  });

// Admin -> Delivery Charges: edit each delivery zone's charge. The zones ARE the delivery-charge system (apps.shipping):
// checkout's backend prices every order from them and stores the charge on the order, the storefront shows them, and a
// change applies to new orders only — past orders keep the charge they were placed with. Saving calls the existing
// PATCH /admin/shipping/zones/<id>/charge/ for each changed zone (validated and logged in the zone's charge history).
// The Dhaka Outer Zones card also edits that zone's Dhaka areas (PATCH zones/<id>/ with `coverage`); checkout's Dhaka
// zone list is "Dhaka Sadar" plus exactly these areas (lib/useDhakaZones.js), so adding or removing one here shows there.
export default function DeliveryChargeSettings({ initialZones, currencySymbol }) {
  const [zones, setZones] = useState(() => (initialZones ? sortZones(initialZones) : null));
  const [values, setValues] = useState(() => Object.fromEntries((initialZones ?? []).map((z) => [z.id, String(Number(z.charge))])));
  const [areas, setAreas] = useState(() => outerAreasOf(initialZones));
  const [newArea, setNewArea] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);

  const outerZone = zones?.find((z) => z.slug === OUTER);
  const savedAreas = outerAreasOf(zones);
  const areasChanged = !sameList(areas, savedAreas);

  function addArea() {
    const name = newArea.trim().replace(/\s+/g, " ");
    if (!name) return;
    if (name.toLowerCase() === SADAR.toLowerCase()) return notify.error(`"${SADAR}" is the rest of Dhaka (Inside Dhaka), not an outer zone.`);
    if (areas.some((a) => a.toLowerCase() === name.toLowerCase())) return notify.error(`"${name}" is already listed.`);
    setAreas((list) => [...list, name]);
    setNewArea("");
  }
  async function reload() {
    setLoading(true);
    const res = await shippingFetch("zones?page_size=100&ordering=sort_order");
    setLoading(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to load delivery charges. Please try again."));
    const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
    setZones(sortZones(list));
    setValues(Object.fromEntries(list.map((z) => [z.id, String(Number(z.charge))])));
    setAreas(outerAreasOf(list));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (saving || !zones) return;
    for (const zone of zones) {
      const value = (values[zone.id] ?? "").trim();
      if (!value) return notify.error(`${zone.name}: enter a delivery charge (0 for free delivery).`);
      if (!MONEY.test(value)) return notify.error(`${zone.name}: enter a valid amount of 0 or more, e.g. 70.`);
    }
    const changed = zones.filter((z) => Number(values[z.id]) !== Number(z.charge));
    if (changed.length === 0 && !areasChanged) return notify.success("Delivery charges updated successfully.");

    setSaving(true);
    if (areasChanged && outerZone) {
      // Replace only the zone's Dhaka entry (any other district it covers stays). No areas left -> no Dhaka entry at all:
      // an entry with an empty list would mean "all of Dhaka", which Inside Dhaka already covers.
      const dhakaId = dhakaIdOf(zones);
      const others = (outerZone.coverage ?? []).filter((c) => c.district_name !== DHAKA).map((c) => ({ district_id: c.district_id, areas: c.areas }));
      const coverage = areas.length && dhakaId ? [...others, { district_id: dhakaId, areas }] : others;
      const res = await shippingFetch(`zones/${outerZone.id}`, { method: "PATCH", body: { coverage } });
      if (!res.ok) {
        setSaving(false);
        notify.error(`${outerZone.name}: ${errorText(res, "the areas couldn't be saved.")}`);
        return reload();
      }
      setZones((list) => list.map((z) => (z.id === outerZone.id ? { ...z, coverage: res.data.coverage } : z)));
    }
    for (const zone of changed) {
      const res = await shippingFetch(`zones/${zone.id}/charge`, { method: "PATCH", body: { charge: values[zone.id].trim() } });
      if (!res.ok) {
        setSaving(false);
        notify.error(`${zone.name}: ${errorText(res, "the charge couldn't be saved.")}`);
        return reload(); // show what is actually saved now
      }
      setZones((list) => list.map((z) => (z.id === zone.id ? { ...z, charge: res.data.charge } : z)));
    }
    setSaving(false);
    notify.success("Delivery charges updated successfully.");
  }

  if (!zones) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="custom-font text-2xl sm:text-3xl">Delivery Charges</h1>
        <div className="dashboard-card flex flex-col items-center gap-3 rounded-2xl px-6 py-14 text-center">
          <FiAlertCircle className="showcase-muted h-8 w-8" aria-hidden="true" />
          <p className="custom-font text-xl">Unable to load delivery charges</p>
          <button type="button" onClick={reload} disabled={loading} className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-5 py-2 text-sm font-medium">
            <FiRefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
            {loading ? "Retrying..." : "Retry"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-6">
      <div>
        <h1 className="custom-font text-2xl sm:text-3xl">Delivery Charges</h1>
        <p className="showcase-muted mt-1 text-sm">
          What customers pay for delivery, by area. Changes apply to new orders straight away; existing orders keep the charge they were placed with.
        </p>
      </div>

      <section className={`dashboard-card rounded-2xl p-5 sm:p-6 ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
        {zones.length === 0 ? (
          <p className="showcase-muted text-sm">No delivery zones are set up yet.</p>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {zones.map((zone) => {
              const changed = Number(values[zone.id]) !== Number(zone.charge);
              return (
                <div key={zone.id} className="delivery-zone flex min-w-0 flex-col gap-3 rounded-xl p-4">
                  <div className="flex items-start gap-3">
                    <span className="dashboard-card__icon flex h-9 w-9 shrink-0 items-center justify-center rounded-full">
                      <FiTruck className="h-4 w-4" aria-hidden="true" />
                    </span>
                    <div className="min-w-0">
                      <label htmlFor={`dc-${zone.id}`} className="block text-sm font-semibold">
                        {zone.name}
                      </label>
                      <p className="showcase-muted text-xs">{WHERE[zone.slug] ?? zone.description}</p>
                    </div>
                  </div>
                  <div className="relative">
                    <span className="showcase-muted pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm" aria-hidden="true">
                      {currencySymbol}
                    </span>
                    <input
                      id={`dc-${zone.id}`}
                      type="number"
                      inputMode="decimal"
                      min="0"
                      step="1"
                      value={values[zone.id] ?? ""}
                      onChange={(e) => setValues((v) => ({ ...v, [zone.id]: e.target.value }))}
                      className="checkout-input rounded-lg py-2.5 pl-8 pr-3 text-sm"
                    />
                  </div>
                  {zone.slug === OUTER && (
                    <div className="flex flex-col gap-2 border-t pt-3">
                      <span className="text-xs font-medium">Areas ({areas.length})</span>
                      {areas.length === 0 ? (
                        <p className="showcase-muted text-xs">No outer areas — all of Dhaka is charged as Inside Dhaka.</p>
                      ) : (
                        <ul className="flex flex-wrap gap-1.5">
                          {areas.map((area) => (
                            <li key={area} className="area-chip inline-flex items-center gap-1 rounded-full py-1 pl-3 pr-1 text-xs font-medium">
                              {area}
                              <button
                                type="button"
                                onClick={() => setAreas((list) => list.filter((a) => a !== area))}
                                title={`Remove ${area}`}
                                aria-label={`Remove ${area}`}
                                className="area-chip__remove flex h-5 w-5 items-center justify-center rounded-full"
                              >
                                <FiX className="h-3 w-3" aria-hidden="true" />
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                      <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-2">
                        <input
                          type="text"
                          value={newArea}
                          maxLength={100}
                          onChange={(e) => setNewArea(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              addArea();
                            }
                          }}
                          placeholder="Add an area, e.g. Ashulia"
                          aria-label="New Dhaka outer area"
                          className="checkout-input rounded-lg px-3 py-2 text-sm"
                        />
                        <button type="button" onClick={addArea} disabled={!newArea.trim()} className="auth-btn auth-btn--outline inline-flex items-center gap-1 rounded-lg px-3 py-2 text-xs font-medium">
                          <FiPlus className="h-3.5 w-3.5" aria-hidden="true" /> Add
                        </button>
                      </div>
                      {areasChanged && <p className="delivery-zone__changed text-xs font-medium">Area changes are unsaved.</p>}
                    </div>
                  )}
                  <p className="showcase-muted text-xs">
                    Current: <span className="font-medium">{Number(zone.charge) === 0 ? "Free" : formatPrice(zone.charge, currencySymbol)}</span>
                    {changed && <span className="delivery-zone__changed ml-1.5 font-medium">· unsaved</span>}
                    {!zone.is_active && " · inactive"}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <div className="flex justify-end">
        <button type="submit" disabled={saving || zones.length === 0} aria-busy={saving} className="auth-btn auth-btn--primary rounded-full px-6 py-2.5 text-sm font-medium">
          {saving ? "Saving..." : "Save Changes"}
        </button>
      </div>
    </form>
  );
}
