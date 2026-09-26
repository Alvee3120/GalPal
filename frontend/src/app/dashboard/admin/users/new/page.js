import Link from "next/link";
import UserForm from "@/component/dashboard/users/UserForm";

export const metadata = { title: "Add User | GalPal" };

export default function AdminAddUserPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/dashboard/admin/users" className="showcase-muted text-sm hover:underline">
          &larr; User Management
        </Link>
        <h1 className="custom-font mt-2 text-2xl sm:text-3xl">Add User</h1>
      </div>
      <UserForm />
    </div>
  );
}
