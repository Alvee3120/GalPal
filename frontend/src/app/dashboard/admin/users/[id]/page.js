import Link from "next/link";
import { notFound } from "next/navigation";
import { backendFetch } from "@/lib/backendAuth";
import { getCurrentUser } from "@/lib/currentUser";
import UserForm from "@/component/dashboard/users/UserForm";

export const metadata = { title: "Edit User | GalPal" };

// GET /admin/users/<id>/ — the user's details only; the password (and its hash) is never part of the response.
export default async function AdminEditUserPage({ params }) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const [res, me] = await Promise.all([backendFetch(`/admin/users/${id}/`), getCurrentUser()]);
  if (res.status === 404) notFound();
  if (!res.ok) throw new Error(`Unable to load user ${id}`);
  const user = await res.json();
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/dashboard/admin/users" className="showcase-muted text-sm hover:underline">
          &larr; User Management
        </Link>
        <h1 className="custom-font mt-2 text-2xl sm:text-3xl">Edit User</h1>
        <p className="showcase-muted mt-1 text-sm">
          {user.full_name || user.phone}
          {user.created_via_checkout ? " · created via checkout" : ""}
        </p>
      </div>
      <UserForm key={`${user.id}-${user.is_active}-${user.role}`} user={user} isSelf={me?.id === user.id} />
    </div>
  );
}
