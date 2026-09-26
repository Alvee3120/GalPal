"use client";

import Link from "next/link";
import { useStaffHref } from "@/lib/staffPaths";

// A Link to a staff page written in its /dashboard/CCE/… form, served under the viewer's own section (see lib/staffPaths).
// For Server Components, which can't read the current path themselves.
export default function StaffLink({ href, ...props }) {
  const to = useStaffHref();
  return <Link href={to(href)} {...props} />;
}
