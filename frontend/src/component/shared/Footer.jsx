import Image from "next/image";
import Link from "next/link";
import { getContactDetails } from "@/lib/siteSettings";
import FooterWordmark from "./FooterWordmark";

const navigation = [
  { href: "/shop", label: "Shop" },
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
];

const company = [
  { href: "/return&cancellation-policy", label: "Return & Cancellation Policy" },
  { href: "/privacy-policy", label: "Privacy Policy" },
  { href: "/terms", label: "Terms of Service" },
];

function SocialIcon({ children }) {
  return (
    <svg
      className="h-3.5 w-3.5"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

// Icon per Site Settings social link field; the links themselves come from Admin → Site Settings (an empty field hides
// its icon).
const socials = [
  {
    key: "facebook_url",
    label: "Facebook",
    icon: <path d="M14 8h3V4h-3a4 4 0 0 0-4 4v3H7v4h3v6h4v-6h3l1-4h-4V8Z" />,
  },
  {
    key: "instagram_url",
    label: "Instagram",
    icon: (
      <>
        <rect x="4" y="4" width="16" height="16" rx="5" />
        <circle cx="12" cy="12" r="3.5" />
        <circle cx="17" cy="7" r=".6" />
      </>
    ),
  },
  {
    key: "youtube_url",
    label: "YouTube",
    icon: (
      <>
        <rect x="3" y="6" width="18" height="12" rx="4" />
        <path d="m10.5 9.5 4 2.5-4 2.5v-5Z" />
      </>
    ),
  },
  {
    key: "tiktok_url",
    label: "TikTok",
    icon: <path d="M14 4v10.5a3.5 3.5 0 1 1-3.5-3.5M14 4c.6 2.6 2.4 4.2 5 4.5" />,
  },
  {
    key: "x_url",
    label: "X",
    icon: <path d="M4 4l16 16M20 4 4 20" />,
  },
  {
    key: "linkedin_url",
    label: "LinkedIn",
    icon: (
      <>
        <rect x="4" y="4" width="16" height="16" rx="3" />
        <path d="M8 11v5M8 8v.01M12 16v-5M12 13a2 2 0 0 1 4 0v3" />
      </>
    ),
  },
];

function LinkColumn({ title, items }) {
  return (
    <div>
      <h3 className="text-base font-bold custom-font">{title}</h3>
      <ul className="mt-5 space-y-3 text-sm">
        {items.map((item) => (
          <li key={item.label}>
            <Link href={item.href} className="footer-link">
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Contact details, support hours and social links come from Site Settings (Admin → Site Settings); anything that
// isn't filled in isn't shown.
export default async function Footer() {
  const contact = await getContactDetails();
  const hasContact = Boolean(contact.address || contact.phone || contact.email || contact.supportHours);
  const socialLinks = socials.filter((s) => contact.socials[s.key]);
  return (
    <footer className="footer mt-auto w-full overflow-hidden">
      <div className="mx-auto w-full max-w-7xl px-4 pt-14 sm:px-6 lg:px-8 lg:pt-16">
        <div className="grid grid-cols-2 gap-x-6 gap-y-10 lg:grid-cols-[1.6fr_1fr_1fr_1.4fr] lg:gap-x-10">
          <div className="col-span-2 lg:col-span-1">
            <Link href="/" className="inline-block">
              <Image
                src="/assets/galpal/galpal-logo.svg"
                alt="Galpal"
                width={1012}
                height={196}
                className="h-12 w-auto"
              />
            </Link>
            <p className="footer-muted mt-4 max-w-sm text-sm leading-relaxed">
              High-performance skincare focused on barrier repair, clinical
              safety, and visible results.
            </p>
            {socialLinks.length > 0 && (
              <ul className="mt-6 flex items-center gap-2">
                {socialLinks.map((s) => (
                  <li key={s.key}>
                    <a
                      href={contact.socials[s.key]}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label={s.label}
                      className="footer-icon flex h-8 w-8 items-center justify-center rounded-full transition-colors"
                    >
                      <SocialIcon>{s.icon}</SocialIcon>
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <LinkColumn title="Navigation" items={navigation} />
          <LinkColumn title="Company" items={company} />

          {hasContact && (
            <div className="col-span-2 lg:col-span-1">
              <h3 className="text-base font-bold custom-font">Get in Touch</h3>
              <address className="mt-5 space-y-3 text-sm not-italic">
                {contact.address && <p className="max-w-xs whitespace-pre-line leading-relaxed">{contact.address}</p>}
                {contact.phone && (
                  <p>
                    <a href={`tel:${contact.phone.replace(/[^\d+]/g, "")}`} className="footer-link">
                      {contact.phone}
                    </a>
                  </p>
                )}
                {contact.email && (
                  <p>
                    <a href={`mailto:${contact.email}`} className="footer-link">
                      {contact.email}
                    </a>
                  </p>
                )}
                {contact.supportHours && <p className="footer-muted">{contact.supportHours}</p>}
              </address>
            </div>
          )}
        </div>
      </div>

      {/* Oversized brand wordmark: rises from the bottom when scrolled into view */}
      <FooterWordmark />

      <div className="footer-bottom mx-auto flex w-full max-w-7xl flex-col items-center justify-between gap-2 px-4 py-6 text-sm sm:flex-row sm:px-6 lg:px-8">
        <p className="text-gray-400">Developed by Shordindu Development Team</p>
        <p className="text-gray-400">© {new Date().getFullYear()} Galpal. All rights reserved.</p>
      </div>
    </footer>
  );
}
