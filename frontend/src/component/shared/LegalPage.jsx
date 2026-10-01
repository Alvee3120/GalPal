import Link from "next/link";
import PageHero from "./PageHero";
import { getContactDetails, getSiteSettings } from "@/lib/siteSettings";
import { POLICY } from "@/lib/policies";

// Shared layout for the About and policy pages: the site's PageHero, a readable column, the "Last updated" date
// (lib/policies.js) and a contact block whose phone/email/address come from Site Settings (Admin → Site Settings),
// so they're never hard-coded. Sections are plain <section><h2>… children styled by .legal-page in globals.css.
export default async function LegalPage({ title, intro, showUpdated = true, children }) {
  const [contact, settings] = await Promise.all([getContactDetails(), getSiteSettings()]);
  const storeName = settings?.site_name || "GalPal";

  return (
    <main>
      <PageHero title={title} />
      <article className="legal-page mx-auto w-full max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
        {showUpdated && <p className="legal-page__updated">Last updated: {POLICY.lastUpdated}</p>}
        {intro && <p className="legal-page__intro">{intro}</p>}
        {children}

        <section aria-labelledby="legal-contact">
          <h2 id="legal-contact">Contact Us</h2>
          <p>Questions about this page or an order? {storeName} is happy to help.</p>
          {contact.phone || contact.email || contact.address ? (
            <ul className="legal-page__contact">
              {contact.phone && (
                <li>
                  Phone: <a href={`tel:${contact.phone.replace(/[^\d+]/g, "")}`}>{contact.phone}</a>
                </li>
              )}
              {contact.email && (
                <li>
                  Email: <a href={`mailto:${contact.email}`}>{contact.email}</a>
                </li>
              )}
              {contact.address && <li className="whitespace-pre-line">Address: {contact.address}</li>}
              {contact.supportHours && <li>Support hours: {contact.supportHours}</li>}
            </ul>
          ) : (
            <p>
              You can reach us through the links in the site footer, or browse the <Link href="/shop">shop</Link>.
            </p>
          )}
        </section>
      </article>
    </main>
  );
}
