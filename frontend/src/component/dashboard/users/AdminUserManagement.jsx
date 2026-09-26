"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FiEdit2, FiPlus, FiSearch, FiTrash2 } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { errorText } from "@/lib/productAdmin";
import { USER_ROLES, USER_ROLE_LABEL, userFetch } from "@/lib/userAdmin";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import UserAvatar from "./UserAvatar";
import DashboardPagination from "../DashboardPagination";

const PAGE_SIZE = 10;
const SEARCH_DELAY_MS = 350;

function ActiveBadge({ active }) {
  return (
    <span className="product-status-badge rounded-full px-2.5 py-1 text-xs font-medium" data-status={active ? "active" : "inactive"}>
      {active ? "Active" : "Inactive"}
    </span>
  );
}

function RoleBadge({ role }) {
  return (
    <span className="role-badge rounded-full px-2.5 py-1 text-xs font-semibold uppercase tracking-wide" data-role={role}>
      {USER_ROLE_LABEL[role] ?? role}
    </span>
  );
}

function Actions({ user, isSelf, onDelete }) {
  return (
    <div className="flex items-center gap-1.5">
      <Link
        href={`/dashboard/admin/users/${user.id}`}
        title="Edit user"
        aria-label={`Edit user ${user.full_name || user.phone}`}
        className="icon-action flex h-9 w-9 items-center justify-center rounded-full"
      >
        <FiEdit2 className="h-4 w-4" aria-hidden="true" />
      </Link>
      <button
        type="button"
        onClick={() => onDelete(user)}
        disabled={isSelf}
        title={isSelf ? "You can't delete your own account" : "Delete user"}
        aria-label={isSelf ? "You can't delete your own account" : `Delete user ${user.full_name || user.phone}`}
        className="icon-action icon-action--danger flex h-9 w-9 items-center justify-center rounded-full disabled:cursor-not-allowed disabled:opacity-40"
      >
        <FiTrash2 className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}

// Admin User Management over GET/DELETE /admin/users/ (apps.accounts.views.UserViewSet — IsAdmin). Search (name,
// phone in any format, email), the role and active filters and pagination all run on the server. Deleting follows the
// backend's rules (not yourself, never the last active admin) and shows its message if it refuses.
export default function AdminUserManagement({ initialUsers, initialCount, currentUserId }) {
  const [users, setUsers] = useState(initialUsers);
  const [count, setCount] = useState(initialCount);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [active, setActive] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const requestId = useRef(0);
  const firstRender = useRef(true);

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const filtered = Boolean(search.trim() || role || active);

  async function load({ nextSearch = search, nextRole = role, nextActive = active, nextPage = 1 } = {}) {
    const id = ++requestId.current;
    setLoading(true);
    const params = new URLSearchParams({ page_size: String(PAGE_SIZE), page: String(nextPage) });
    if (nextSearch.trim()) params.set("search", nextSearch.trim());
    if (nextRole) params.set("role", nextRole);
    if (nextActive) params.set("is_active", nextActive);
    const res = await userFetch(`?${params.toString()}`);
    if (id !== requestId.current) return;
    setLoading(false);
    if (!res.ok) {
      if (res.status === 404 && nextPage > 1) return load({ nextSearch, nextRole, nextActive, nextPage: nextPage - 1 });
      notify.error(errorText(res, "Unable to load users. Please try again."));
      return;
    }
    setUsers(res.data.results ?? []);
    setCount(res.data.count ?? 0);
    setPage(nextPage);
  }

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    const timer = setTimeout(() => load({ nextSearch: search }), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  function clearFilters() {
    setSearch("");
    setRole("");
    setActive("");
    load({ nextSearch: "", nextRole: "", nextActive: "" });
  }

  async function confirmDelete() {
    if (!pendingDelete || deleting) return;
    setDeleting(true);
    const res = await userFetch(`/${pendingDelete.id}`, { method: "DELETE" });
    setDeleting(false);
    if (!res.ok) {
      notify.error(errorText(res, "Unable to delete the user. Please try again."));
      setPendingDelete(null);
      return;
    }
    notify.success("User deleted successfully.");
    setPendingDelete(null);
    load({ nextPage: page });
  }

  const who = (u) => (u.full_name ? `${u.full_name} (${u.phone})` : u.phone);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="custom-font text-2xl sm:text-3xl">User Management</h1>
          <p className="showcase-muted mt-1 text-sm">
            {count} user{count === 1 ? "" : "s"}
          </p>
        </div>
        <Link href="/dashboard/admin/users/new" className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium">
          <FiPlus className="h-4 w-4" aria-hidden="true" />
          Add User
        </Link>
      </div>

      {/* A grid, not flex: .checkout-input is width:100%, so the grid (not a w-* class) sizes each control. */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,10rem)_minmax(0,10rem)]">
        <div className="relative col-span-2 min-w-0 sm:col-span-1">
          <label htmlFor="um-search" className="sr-only">
            Search users
          </label>
          <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
          <input
            id="um-search"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search users..."
            className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
          />
        </div>
        <label htmlFor="um-role" className="sr-only">
          Filter by role
        </label>
        <select
          id="um-role"
          value={role}
          onChange={(e) => {
            setRole(e.target.value);
            load({ nextRole: e.target.value });
          }}
          className="checkout-input rounded-lg px-3 py-2.5 text-sm"
        >
          <option value="">All roles</option>
          {USER_ROLES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
        <label htmlFor="um-active" className="sr-only">
          Filter by status
        </label>
        <select
          id="um-active"
          value={active}
          onChange={(e) => {
            setActive(e.target.value);
            load({ nextActive: e.target.value });
          }}
          className="checkout-input rounded-lg px-3 py-2.5 text-sm"
        >
          <option value="">All statuses</option>
          <option value="true">Active</option>
          <option value="false">Inactive</option>
        </select>
      </div>

      {users.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-3 rounded-2xl px-6 py-14 text-center">
          <p className="custom-font text-xl">{loading ? "Loading..." : "No users found."}</p>
          {!loading && filtered && (
            <button type="button" onClick={clearFilters} className="auth-btn auth-btn--outline rounded-full px-5 py-2 text-sm font-medium">
              Clear filters
            </button>
          )}
        </div>
      ) : (
        <div className={`transition-opacity ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
          <div className="dashboard-card hidden overflow-x-auto rounded-2xl md:block">
            <table className="product-table w-full min-w-[820px] text-left text-sm">
              <thead>
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">Avatar</th>
                  <th scope="col" className="px-4 py-3 font-medium">Phone Number</th>
                  <th scope="col" className="px-4 py-3 font-medium">Full Name</th>
                  <th scope="col" className="px-4 py-3 font-medium">Role</th>
                  <th scope="col" className="px-4 py-3 font-medium">Is Active</th>
                  <th scope="col" className="px-4 py-3 font-medium">Created via Checkout</th>
                  <th scope="col" className="px-4 py-3 font-medium">Edit</th>
                  <th scope="col" className="px-4 py-3 font-medium">Delete</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const isSelf = u.id === currentUserId;
                  return (
                    <tr key={u.id}>
                      <td className="px-4 py-3">
                        <UserAvatar user={u} />
                      </td>
                      <td className="px-4 py-3 tabular-nums">{u.phone}</td>
                      <td className="px-4 py-3">
                        {u.full_name || <span className="showcase-muted">—</span>}
                        {isSelf && <span className="showcase-muted ml-1.5 text-xs">(you)</span>}
                      </td>
                      <td className="px-4 py-3">
                        <RoleBadge role={u.role} />
                      </td>
                      <td className="px-4 py-3">
                        <ActiveBadge active={u.is_active} />
                      </td>
                      <td className="px-4 py-3">{u.created_via_checkout ? "Yes" : "No"}</td>
                      <td className="px-4 py-3">
                        <Link
                          href={`/dashboard/admin/users/${u.id}`}
                          title="Edit user"
                          aria-label={`Edit user ${who(u)}`}
                          className="icon-action flex h-9 w-9 items-center justify-center rounded-full"
                        >
                          <FiEdit2 className="h-4 w-4" aria-hidden="true" />
                        </Link>
                      </td>
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          onClick={() => setPendingDelete(u)}
                          disabled={isSelf}
                          title={isSelf ? "You can't delete your own account" : "Delete user"}
                          aria-label={isSelf ? "You can't delete your own account" : `Delete user ${who(u)}`}
                          className="icon-action icon-action--danger flex h-9 w-9 items-center justify-center rounded-full disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          <FiTrash2 className="h-4 w-4" aria-hidden="true" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <ul className="flex flex-col gap-3 md:hidden">
            {users.map((u) => (
              <li key={u.id} className="dashboard-card flex flex-col gap-3 rounded-2xl p-4">
                <div className="flex items-start justify-between gap-3">
                  <UserAvatar user={u} size="h-10 w-10 text-sm" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {u.full_name || "—"}
                      {u.id === currentUserId && <span className="showcase-muted ml-1.5 text-xs">(you)</span>}
                    </p>
                    <p className="showcase-muted text-xs tabular-nums">{u.phone}</p>
                  </div>
                  <RoleBadge role={u.role} />
                </div>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <ActiveBadge active={u.is_active} />
                    <span className="showcase-muted">Created via checkout: {u.created_via_checkout ? "Yes" : "No"}</span>
                  </div>
                  <Actions user={u} isSelf={u.id === currentUserId} onDelete={setPendingDelete} />
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <DashboardPagination page={page} totalPages={totalPages} onPageChange={(next) => next !== page && load({ nextPage: next })} disabled={loading} />

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete User?"
        description={
          pendingDelete
            ? `Are you sure you want to delete ${who(pendingDelete)}? Their orders and reviews are kept, but the account and its saved addresses are removed.`
            : ""
        }
        confirmLabel="Delete"
        busyLabel="Deleting..."
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => !deleting && setPendingDelete(null)}
      />
    </div>
  );
}
