"use client";

import { useState } from "react";
import { notify } from "@/lib/notify";
import { messageFor } from "@/lib/apiError";
import { createAddress, deleteAddress, setDefaultAddress, updateAddress } from "@/lib/addresses";
import AddressForm from "./AddressForm";
import ConfirmDialog from "@/component/shared/ConfirmDialog";

function AddressCard({ address, onEdit, onDelete, onSetDefault, settingDefault }) {
  return (
    <li className="dashboard-card flex flex-col gap-2 rounded-2xl p-5">
      <div className="flex items-start justify-between gap-2">
        <p className="font-semibold">{address.label || "Address"}</p>
        {address.is_default ? (
          <span className="product-card__chip rounded-full px-2.5 py-1 text-xs font-medium">Default</span>
        ) : (
          <button
            type="button"
            onClick={() => onSetDefault(address)}
            disabled={settingDefault}
            className="showcase-muted text-xs font-medium underline underline-offset-4 disabled:opacity-50"
          >
            {settingDefault ? "Setting..." : "Set as Default"}
          </button>
        )}
      </div>
      <div className="text-sm leading-relaxed">
        <p>{address.full_name}</p>
        <p className="showcase-muted">{address.phone}</p>
        <p className="showcase-muted mt-1">
          {address.address_line}
          {address.area ? `, ${address.area}` : ""}, {address.district}
        </p>
      </div>
      <div className="mt-2 flex gap-4 text-sm font-medium">
        <button type="button" onClick={() => onEdit(address)} className="auth-link">
          Edit
        </button>
        <button type="button" onClick={() => onDelete(address)} className="auth-error">
          Delete
        </button>
      </div>
    </li>
  );
}

// "My Addresses": full CRUD over the EXISTING account address API (lib/addresses.js -> /api/account proxy ->
// backend AddressViewSet), following the same add/edit-modal + delete-confirm + optimistic-refresh pattern used
// elsewhere in this dashboard. Ownership is enforced entirely server-side (AddressViewSet's queryset is scoped to
// request.user, and IsOwner double-checks on update/delete) — this page never sends or trusts a customer id.
export default function AddressesPageContent({ initialAddresses }) {
  const [addresses, setAddresses] = useState(initialAddresses);
  const [formState, setFormState] = useState({ open: false, address: null });
  // Bumped on every open, so AddressForm gets a fresh `key` and remounts with clean initial values each time —
  // including re-opening the SAME address after a cancel, which reusing the address's own id as the key wouldn't
  // catch (see the project's established "key instead of a state-syncing effect" pattern).
  const [formToken, setFormToken] = useState(0);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [settingDefaultId, setSettingDefaultId] = useState(null);

  function openAdd() {
    setFormState({ open: true, address: null });
    setFormToken((t) => t + 1);
  }
  function openEdit(address) {
    setFormState({ open: true, address });
    setFormToken((t) => t + 1);
  }
  function closeForm() {
    setFormState((s) => ({ ...s, open: false }));
  }

  async function handleSubmit(fields) {
    try {
      if (formState.address) {
        const updated = await updateAddress(formState.address.id, fields);
        setAddresses((list) => normalizeDefault(list.map((a) => (a.id === updated.id ? updated : a)), updated));
        notify.success("Address updated successfully.");
      } else {
        const created = await createAddress(fields);
        setAddresses((list) => normalizeDefault([...list, created], created));
        notify.success("Address added successfully.");
      }
      closeForm();
    } catch (err) {
      notify.error(messageFor(err, formState.address ? "Failed to update address." : "Failed to add address."));
    }
  }

  async function handleSetDefault(address) {
    if (settingDefaultId) return;
    setSettingDefaultId(address.id);
    try {
      const updated = await setDefaultAddress(address.id);
      setAddresses((list) => normalizeDefault(list, updated));
    } catch (err) {
      notify.error(messageFor(err, "Unable to set this as your default address."));
    } finally {
      setSettingDefaultId(null);
    }
  }

  async function confirmDelete() {
    if (!deleteTarget || deleting) return;
    setDeleting(true);
    try {
      await deleteAddress(deleteTarget.id);
      setAddresses((list) => list.filter((a) => a.id !== deleteTarget.id));
      notify.success("Address deleted successfully.");
      setDeleteTarget(null);
    } catch (err) {
      notify.error(messageFor(err, "Failed to delete address."));
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="custom-font text-2xl sm:text-3xl">My Addresses</h1>
        <button type="button" onClick={openAdd} className="auth-btn auth-btn--primary rounded-full px-5 py-2 text-sm font-medium">
          + Add New Address
        </button>
      </div>

      {addresses.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-3 rounded-2xl px-6 py-14 text-center">
          <p className="custom-font text-xl">No saved addresses yet</p>
          <button type="button" onClick={openAdd} className="auth-btn auth-btn--primary rounded-full px-6 py-2.5 text-sm font-medium">
            Add your first address
          </button>
        </div>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {addresses.map((address) => (
            <AddressCard
              key={address.id}
              address={address}
              onEdit={openEdit}
              onDelete={setDeleteTarget}
              onSetDefault={handleSetDefault}
              settingDefault={settingDefaultId === address.id}
            />
          ))}
        </ul>
      )}

      <AddressForm key={formToken} open={formState.open} address={formState.address} onClose={closeForm} onSubmit={handleSubmit} />

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete Address?"
        description="Are you sure you want to delete this address? This can't be undone."
        confirmLabel="Delete"
        busyLabel="Deleting..."
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => !deleting && setDeleteTarget(null)}
      />
    </div>
  );
}

// Only one address is default at a time — mirror that locally after any write, instead of refetching the whole list.
function normalizeDefault(list, changed) {
  if (!changed.is_default) return list;
  return list.map((a) => (a.id === changed.id ? changed : { ...a, is_default: false }));
}
