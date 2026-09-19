import Image from "next/image";
import Link from "next/link";

const navigation = [
  { href: "/shop", label: "Shop" },
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
];

const company = [
  { href: "/contact", label: "Contact" },
  { href: "/privacy-policy", label: "Privacy Policy" },
  { href: "/terms", label: "Terms of Service" },
];

const contact = {
  address: "123 Skin Health Plaza, Suite 400, New York, NY 10001",
  phone: "+1 (555) 012-3456",
  email: "hello@galopal.com",
};

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

const socials = [
  {
    label: "Facebook",
    href: "#",
    icon: <path d="M14 8h3V4h-3a4 4 0 0 0-4 4v3H7v4h3v6h4v-6h3l1-4h-4V8Z" />,
  },
  {
    label: "YouTube",
    href: "#",
    icon: (
      <>
        <rect x="3" y="6" width="18" height="12" rx="4" />
        <path d="m10.5 9.5 4 2.5-4 2.5v-5Z" />
      </>
    ),
  },
  {
    label: "X",
    href: "#",
    icon: <path d="M4 4l16 16M20 4 4 20" />,
  },
  {
    label: "Instagram",
    href: "#",
    icon: (
      <>
        <rect x="4" y="4" width="16" height="16" rx="5" />
        <circle cx="12" cy="12" r="3.5" />
        <circle cx="17" cy="7" r=".6" />
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

export default function Footer() {
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
            <ul className="mt-6 flex items-center gap-2">
              {socials.map((s) => (
                <li key={s.label}>
                  <a
                    href={s.href}
                    aria-label={s.label}
                    className="footer-icon flex h-8 w-8 items-center justify-center rounded-full transition-colors"
                  >
                    <SocialIcon>{s.icon}</SocialIcon>
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <LinkColumn title="Navigation" items={navigation} />
          <LinkColumn title="Company" items={company} />

          <div className="col-span-2 lg:col-span-1">
            <h3 className="text-base font-bold custom-font">Get in Touch</h3>
            <address className="mt-5 space-y-3 text-sm not-italic">
              <p className="max-w-xs leading-relaxed">{contact.address}</p>
              <p>
                <a href={`tel:${contact.phone.replace(/[^\d+]/g, "")}`} className="footer-link">
                  {contact.phone}
                </a>
              </p>
              <p>
                <a href={`mailto:${contact.email}`} className="footer-link">
                  {contact.email}
                </a>
              </p>
            </address>
          </div>
        </div>
      </div>

      {/* Oversized brand wordmark, cropped to its top half and fading out (decorative) */}
      <div
        aria-hidden="true"
        className="footer-wordmark custom-font pointer-events-none mt-8 h-[0.65em] select-none overflow-hidden whitespace-nowrap text-center text-[24vw] leading-[1.2]"
      >
        Galpal
      </div>

      <div className="footer-bottom mx-auto flex w-full max-w-7xl flex-col items-center justify-between gap-2 px-4 py-6 text-sm sm:flex-row sm:px-6 lg:px-8">
        <p>Skincare made with care</p>
        <p>© {new Date().getFullYear()} Galpal. All rights reserved.</p>
      </div>
    </footer>
  );
}
