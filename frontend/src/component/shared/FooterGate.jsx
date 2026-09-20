"use client";

import { usePathname } from "next/navigation";

// Routes that render as standalone full-screen pages, without the site footer.
const HIDDEN_ON = ["/login", "/register"];

export default function FooterGate({ children }) {
  const pathname = usePathname();
  return HIDDEN_ON.includes(pathname) ? null : children;
}
