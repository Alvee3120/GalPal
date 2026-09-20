"use client";

import { useEffect } from "react";
import { notify } from "@/lib/notify";

// Lets a server component raise a toast (e.g. a failed data load): renders nothing, notifies once on mount.
export default function NotifyOnMount({ type = "error", message }) {
  useEffect(() => {
    notify[type](message);
  }, [type, message]);
  return null;
}
