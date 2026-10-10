import Link from "next/link";
import { getAnnouncements } from "@/lib/content";
import AnnouncementMarquee from "./AnnouncementMarquee";

// The thin bar above the navbar (Admin → Announcements). Renders nothing when no announcement is live; one shows as
// centred text, several scroll by in a marquee. Links are a site path or an http(s) URL (validated backend-side).
export default async function AnnouncementBar() {
  const items = await getAnnouncements();
  if (items.length === 0) return null;
  const rendered = items.map((item) =>
    item.link_url ? (
      item.link_url.startsWith("/") ? (
        <Link key={item.id} href={item.link_url} className="announcement-bar__link">
          {item.text}
        </Link>
      ) : (
        <a key={item.id} href={item.link_url} target="_blank" rel="noopener noreferrer" className="announcement-bar__link">
          {item.text}
        </a>
      )
    ) : (
      <span key={item.id}>{item.text}</span>
    ),
  );
  return (
    <div
      className={`announcement-bar w-full py-2 text-xs font-medium sm:text-sm ${rendered.length > 1 ? "overflow-hidden" : "px-4 text-center"}`}
      role="region"
      aria-label="Announcements"
    >
      {rendered.length > 1 ? <AnnouncementMarquee>{rendered}</AnnouncementMarquee> : rendered[0]}
    </div>
  );
}
