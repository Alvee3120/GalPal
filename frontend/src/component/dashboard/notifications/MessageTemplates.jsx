"use client";

import { useState } from "react";
import { FiEdit2, FiRotateCcw } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { errorText } from "@/lib/productAdmin";
import { CHANNEL_LABEL, notificationsFetch } from "@/lib/notificationsAdmin";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import Modal from "@/component/shared/Modal";

const INPUT = "checkout-input w-full rounded-lg px-3 py-2.5 text-sm";
const key = (t) => `${t.event}/${t.channel}`;

function TemplateForm({ template, onSaved, onClose }) {
  const [subject, setSubject] = useState(template.subject);
  const [body, setBody] = useState(template.body);
  const [isActive, setIsActive] = useState(template.is_active || !template.is_custom);
  const [saving, setSaving] = useState(false);
  const isEmail = template.channel === "email";

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    const res = await notificationsFetch(`templates/${template.event}/${template.channel}`, {
      method: "PUT",
      body: { subject: isEmail ? subject : "", body, is_active: isActive },
    });
    setSaving(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to save the template."));
    notify.success("Template saved.");
    onSaved(res.data);
  }

  return (
    <form onSubmit={save} className="flex flex-col gap-4">
      {isEmail && (
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Subject</span>
          <input value={subject} required maxLength={200} onChange={(e) => setSubject(e.target.value)} className={INPUT} />
        </label>
      )}
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium">Message</span>
        <textarea value={body} required rows={isEmail ? 10 : 4} maxLength={5000} onChange={(e) => setBody(e.target.value)} className={INPUT} />
        {!isEmail && <span className="showcase-muted text-xs">{body.length} characters (one SMS is about 160)</span>}
      </label>
      <div className="text-xs">
        <p className="font-medium">Placeholders</p>
        <ul className="mt-1.5 flex flex-wrap gap-1.5">
          {template.placeholders.map((p) => (
            <li key={p}>
              <code className="product-card__chip rounded-full px-2.5 py-0.5">{`{${p}}`}</code>
            </li>
          ))}
        </ul>
        {template.secret_placeholder && (
          <p className="showcase-muted mt-2">
            Must include {`{${template.secret_placeholder}}`}. It&apos;s sent to the customer but masked in the notification log.
          </p>
        )}
      </div>
      <label className="inline-flex items-center gap-2 text-sm">
        <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
        Send this message
      </label>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onClose} className="auth-btn auth-btn--outline rounded-full px-5 py-2.5 text-sm font-medium">
          Cancel
        </button>
        <button type="submit" disabled={saving} className="auth-btn auth-btn--primary rounded-full px-6 py-2.5 text-sm font-medium">
          {saving ? "Saving…" : "Save Template"}
        </button>
      </div>
    </form>
  );
}

// Admin → Message Templates (Module 16): the text of every email/SMS, per event and channel. Built-in text is used
// until the Admin saves their own; "Reset" goes back to it. A message can be switched off entirely.
export default function MessageTemplates({ initial = [] }) {
  const [templates, setTemplates] = useState(initial);
  const [editing, setEditing] = useState(null);
  const [pendingReset, setPendingReset] = useState(null);
  const [busy, setBusy] = useState(false);
  const events = [...new Map(templates.map((t) => [t.event, t.event_label])).entries()];

  const replace = (t) => setTemplates((list) => list.map((x) => (key(x) === key(t) ? t : x)));

  async function toggle(t) {
    const res = await notificationsFetch(`templates/${t.event}/${t.channel}`, { method: "PUT", body: { subject: t.subject, body: t.body, is_active: !t.is_active } });
    if (!res.ok) return notify.error(errorText(res, "Unable to update the template."));
    replace(res.data);
  }

  async function confirmReset() {
    const t = pendingReset;
    setBusy(true);
    const res = await notificationsFetch(`templates/${t.event}/${t.channel}`, { method: "DELETE" });
    setBusy(false);
    setPendingReset(null);
    if (!res.ok) return notify.error(errorText(res, "Unable to reset the template."));
    replace(res.data);
    notify.success("Back to the built-in text.");
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="custom-font text-2xl sm:text-3xl">Message Templates</h1>
        <p className="showcase-muted mt-1 text-sm">The emails and SMS the shop sends. A message with no recipient (no email or phone) is skipped.</p>
      </div>

      {events.map(([event, label]) => (
        <section key={event} className="dashboard-card rounded-2xl p-5 sm:p-6">
          <h2 className="custom-font text-lg font-bold">{label}</h2>
          <ul className="mt-3 flex flex-col divide-y">
            {templates
              .filter((t) => t.event === event)
              .map((t) => {
                const empty = !t.body;
                return (
                  <li key={key(t)} className="flex flex-wrap items-center gap-3 py-3 text-sm">
                    <span className="w-14 font-medium">{CHANNEL_LABEL[t.channel]}</span>
                    <p className="showcase-muted min-w-0 flex-1 truncate">{empty ? "Not set up — write a message to start sending it." : t.subject || t.body}</p>
                    {t.is_custom && <span className="showcase-muted text-xs">Custom</span>}
                    {!empty && (
                      <button
                        type="button"
                        onClick={() => toggle(t)}
                        className="product-status-badge rounded-full px-2.5 py-0.5 text-xs font-medium"
                        data-status={t.is_active ? "active" : "archived"}
                        title={t.is_active ? "Click to stop sending" : "Click to send"}
                      >
                        {t.is_active ? "On" : "Off"}
                      </button>
                    )}
                    <button type="button" onClick={() => setEditing(t)} aria-label={`Edit ${label} ${t.channel}`} title="Edit" className="icon-action flex h-9 w-9 items-center justify-center rounded-full">
                      <FiEdit2 className="h-4 w-4" aria-hidden="true" />
                    </button>
                    {t.is_custom && (
                      <button type="button" onClick={() => setPendingReset(t)} aria-label="Reset to built-in text" title="Reset to built-in text" className="icon-action flex h-9 w-9 items-center justify-center rounded-full">
                        <FiRotateCcw className="h-4 w-4" aria-hidden="true" />
                      </button>
                    )}
                  </li>
                );
              })}
          </ul>
        </section>
      ))}

      <Modal open={Boolean(editing)} title={editing ? `${editing.event_label} · ${CHANNEL_LABEL[editing.channel]}` : ""} onClose={() => setEditing(null)} wide>
        {editing && (
          <TemplateForm
            key={key(editing)}
            template={editing}
            onSaved={(t) => {
              replace(t);
              setEditing(null);
            }}
            onClose={() => setEditing(null)}
          />
        )}
      </Modal>

      <ConfirmDialog
        open={Boolean(pendingReset)}
        title="Reset Template?"
        description="Your text is removed and the built-in message is used again."
        confirmLabel="Reset"
        busyLabel="Resetting..."
        busy={busy}
        onConfirm={confirmReset}
        onCancel={() => !busy && setPendingReset(null)}
      />
    </div>
  );
}
