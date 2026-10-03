// The social networks Site Settings can link to (Admin → Site Settings → Social Links), each with its icon — shared
// by the footer and the Contact page. A network shows only when its URL is set.
export function SocialIcon({ children, className = "h-3.5 w-3.5" }) {
  return (
    <svg
      className={className}
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
export const SOCIALS = [
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
