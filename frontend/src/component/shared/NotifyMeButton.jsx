"use client";

import { useState } from "react";
import { IoIosNotifications } from "react-icons/io";
import { notify } from "@/lib/notify";
import { useAuthed } from "@/lib/useAuthed";
import { requestStockNotification } from "@/lib/notifyStock";
import NotifyMeModal from "./NotifyMeModal";

// The "Notify Me" action, shared by the product card and the product detail page.
//   Logged in  -> no modal: subscribe immediately (product/variant + the session's own identity,
//                 via the auth cookie the /api/stock-notifications proxy forwards — never asks the
//                 user to re-type anything already known).
//   Logged out -> open the phone-number modal.
export default function NotifyMeButton({ productId, productName, variantId, className, ariaLabel, compact = false }) {
  const authed = useAuthed();
  const [submitting, setSubmitting] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

  async function handleClick() {
    if (!authed) {
      setModalOpen(true);
      return;
    }
    if (submitting) return;
    setSubmitting(true);
    const result = await requestStockNotification({ productId, variantId });
    setSubmitting(false);
    if (result.ok) {
      notify.success("You'll be notified when this product is back in stock.");
    } else {
      notify.error(result.message);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={handleClick}
        disabled={submitting}
        aria-label={ariaLabel}
        title={ariaLabel}
        className={className}
      >
        {compact ? <IoIosNotifications className="h-5 w-5" aria-hidden="true" /> : submitting ? "Adding..." : "Notify Me"}
      </button>
      {!authed && (
        <NotifyMeModal open={modalOpen} onClose={() => setModalOpen(false)} productId={productId} productName={productName} variantId={variantId} />
      )}
    </>
  );
}
