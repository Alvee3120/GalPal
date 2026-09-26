import { getCurrentUser } from "@/lib/currentUser";
import { backendFetch } from "@/lib/backendAuth";
import AdminUserManagement from "@/component/dashboard/users/AdminUserManagement";

export const metadata = { title: "User Management | GalPal" };

// First page from GET /admin/users/ (IsAdmin; the admin-only layout above guards the route too). Search, filters and
// paging then run client-side through /api/admin/users.
async function getUsers() {
  try {
    const res = await backendFetch("/admin/users/?page_size=10");
    if (!res.ok) return { results: [], count: 0 };
    const data = await res.json();
    return { results: data.results ?? [], count: data.count ?? 0 };
  } catch {
    return { results: [], count: 0 };
  }
}

export default async function AdminUsersPage() {
  const [{ results, count }, me] = await Promise.all([getUsers(), getCurrentUser()]);
  return <AdminUserManagement initialUsers={results} initialCount={count} currentUserId={me?.id ?? null} />;
}
