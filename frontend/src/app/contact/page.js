import Link from "next/link";
import { FiClock, FiMail, FiMapPin, FiMessageCircle, FiPhone } from "react-icons/fi";
import PageHero from "@/component/shared/PageHero";
import { SOCIALS, SocialIcon } from "@/component/shared/socialLinks";
import { getContactDetails } from "@/lib/siteSettings";
import ContactForm from "@/component/contact/ContactForm";
import RichText from "@/component/content/RichText";
import { getFaqs } from "@/lib/content";

export const metadata = {
  title: "Contact Us | GalPal",
  description: "Call, email, WhatsApp or visit GalPal — we're happy to help with orders, products and returns.",
};

// Contact: every channel comes from Site Settings (Admin → Site Settings); a card only shows when its detail is set,
// and each one is a direct action (call, email, WhatsApp chat, map). Below them: the contact form (to Admin -> Support
// Inbox, apps.care) on the left and common questions (Admin -> FAQs) on the right; stacked on small screens.
const FAQ_LIMIT = 6; // the rest are on /faq

export default async function ContactPage() {
  const [contact, faqs] = await Promise.all([getContactDetails(), getFaqs()]);
  const topFaqs = faqs.slice(0, FAQ_LIMIT);
  const socials = SOCIALS.filter((s) => contact.socials[s.key]);

  const cards = [
    contact.phone && {
      key: "phone",
      icon: FiPhone,
      title: "Call Us",
      text: "Talk to our team about an order or a product.",
      value: contact.phone,
      href: `tel:${contact.phone.replace(/[^\d+]/g, "")}`,
    },
    contact.whatsapp && {
      key: "whatsapp",
      icon: FiMessageCircle,
      title: "WhatsApp",
      text: "Chat with us — the quickest way to get help.",
      value: `+${contact.whatsapp}`,
      href: `https://wa.me/${contact.whatsapp}`,
      external: true,
    },
    contact.email && {
      key: "email",
      icon: FiMail,
      title: "Email Us",
      text: "We'll get back to you as soon as we can.",
      value: contact.email,
      href: `mailto:${contact.email}`,
    },
    contact.address && {
      key: "address",
      icon: FiMapPin,
      title: "Visit Us",
      text: contact.address,
      value: "Open in Google Maps",
      href: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(contact.address)}`,
      external: true,
      multiline: true,
    },
    contact.supportHours && {
      key: "hours",
      icon: FiClock,
      title: "Support Hours",
      text: contact.supportHours,
    },
  ].filter(Boolean);

  return (
    <main>
      <PageHero title="Contact Us" />
      <div className="mx-auto w-full max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
        <p className="showcase-muted mx-auto max-w-2xl text-center text-base">
          Questions about an order, a product or a return? Reach us any way you like — we&apos;re happy to help.
        </p>

        {cards.length > 0 ? (
          <ul className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {cards.map(({ key, icon: Icon, title, text, value, href, external, multiline }) => (
              <li key={key} className="contact-card flex flex-col gap-3 rounded-2xl p-6">
                <span className="contact-card__icon flex h-11 w-11 items-center justify-center rounded-full">
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </span>
                <h2 className="custom-font text-xl">{title}</h2>
                <p className={`showcase-muted text-sm leading-relaxed ${multiline ? "whitespace-pre-line" : ""}`}>{text}</p>
                {href && (
                  <a
                    href={href}
                    {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                    className="contact-card__link mt-auto w-fit break-all text-sm font-semibold"
                  >
                    {value}
                  </a>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="showcase-muted mt-10 text-center text-sm">Our contact details will appear here soon.</p>
        )}

        <div className={`mt-12 grid grid-cols-1 items-start gap-6 ${topFaqs.length ? "lg:grid-cols-2 lg:gap-8" : ""}`}>
          <ContactForm />

          {topFaqs.length > 0 && (
            <section className="contact-card min-w-0 rounded-2xl p-6 sm:p-8" aria-labelledby="contact-faq-title">
              <h2 id="contact-faq-title" className="custom-font text-2xl">
                Frequently Asked Questions
              </h2>
              <p className="showcase-muted mt-1 text-sm">Your answer might already be here.</p>
              <div className="mt-5 flex flex-col gap-3">
                {topFaqs.map((faq) => (
                  <details key={faq.id} className="faq-item contact-faq rounded-xl px-4 py-3">
                    <summary className="cursor-pointer text-sm font-semibold">{faq.question}</summary>
                    <div className="legal-page mt-2 text-sm">
                      <RichText text={faq.answer} />
                    </div>
                  </details>
                ))}
              </div>
              {faqs.length > FAQ_LIMIT && (
                <Link href="/faq" className="contact-card__link mt-5 inline-block text-sm font-semibold">
                  View all questions →
                </Link>
              )}
            </section>
          )}
        </div>

        {socials.length > 0 && (
          <section className="mt-12 text-center" aria-labelledby="contact-follow">
            <h2 id="contact-follow" className="custom-font text-xl">
              Follow Us
            </h2>
            <ul className="mt-4 flex flex-wrap justify-center gap-3">
              {socials.map((s) => (
                <li key={s.key}>
                  <a
                    href={contact.socials[s.key]}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={s.label}
                    className="footer-icon flex h-11 w-11 items-center justify-center rounded-full transition-colors"
                  >
                    <SocialIcon className="h-5 w-5">{s.icon}</SocialIcon>
                  </a>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="contact-help mt-12 rounded-2xl p-6 text-center sm:p-8" aria-labelledby="contact-help">
          <h2 id="contact-help" className="custom-font text-xl">
            Looking for something else?
          </h2>
          <p className="showcase-muted mx-auto mt-2 max-w-xl text-sm">
            Check your orders in your account, or read how cancellations and returns work.
          </p>
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            <Link href="/dashboard" className="auth-btn auth-btn--primary rounded-full px-6 py-2.5 text-sm font-medium">
              My Orders
            </Link>
            <Link href="/return-and-cancellation-policy" className="auth-btn auth-btn--outline rounded-full px-6 py-2.5 text-sm font-medium">
              Return &amp; Cancellation Policy
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
