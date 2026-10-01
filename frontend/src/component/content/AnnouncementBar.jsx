import Link from "next/link";
import { getAnnouncements } from "@/lib/content";
import AnnouncementRotator from "./AnnouncementRotator";

// The thin bar above the navbar (Admin → Announcements). Renders nothing when no announcement is live. Several live
// announcements take turns; links are a site path or an http(s) URL (validated backend-side).
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
    <div className="announcement-bar w-full px-4 py-2 text-center text-xs font-medium sm:text-sm" role="region" aria-label="Announcements">
      <AnnouncementRotator>{rendered}</AnnouncementRotator>
    </div>
  );
}
