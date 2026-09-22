import { ROLE_LABEL } from "@/lib/dashboardNav";

// The Admin/CCE /dashboard landing. Deliberately minimal: this project has no admin-facing management pages
// (Products, Customers, Reports, ...) built in the frontend yet, only backend endpoints — so this shows the
// signed-in staff member's real identity and nothing invented (no fake stats, no links to pages that don't exist).
export default function StaffDashboardHome({ user }) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="custom-font text-2xl sm:text-3xl">Welcome, {user.full_name}</h1>
        <p className="showcase-muted mt-1 text-sm">Signed in as {ROLE_LABEL[user.role] ?? user.role}.</p>
      </div>
      <div className="dashboard-card rounded-2xl p-6">
        <p className="text-sm leading-relaxed">
          Management pages for this role (products, orders, customers, reports) aren&apos;t built yet — this dashboard currently only
          covers sign-in and account access.
        </p>
      </div>
    </div>
  );
}
