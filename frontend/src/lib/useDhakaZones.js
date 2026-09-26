"use client";

import { useEffect, useState } from "react";
import { DHAKA_SADAR_ZONE, dhakaZonesFrom } from "./delivery";

// The same list, loaded once per page (shared by every form on it). Until it arrives only "Dhaka Sadar" is offered.
let zonesRequest = null;
function loadZones() {
  zonesRequest ??= fetch("/api/shipping/zones", { cache: "no-store" })
    .then((res) => (res.ok ? res.json() : []))
    .catch(() => [])
    .then((data) => {
      if (!Array.isArray(data) || data.length === 0) zonesRequest = null; // let a later form retry
      return Array.isArray(data) ? data : [];
    });
  return zonesRequest;
}

export default function useDhakaZones() {
  const [zones, setZones] = useState([DHAKA_SADAR_ZONE]);
  useEffect(() => {
    let cancelled = false;
    loadZones().then((data) => !cancelled && setZones(dhakaZonesFrom(data)));
    return () => {
      cancelled = true;
    };
  }, []);
  return zones;
}

