import Link from "next/link";

// Root-to-page trail shared by PageHero and the product page. `items` is a list of { label, href? };
// the last item is the current page (no href) and rendered as plain text. Links other than the trail's
// current page get the same muted, underlined-on-hover treatment the rest of the app uses.
export default function Breadcrumbs({ items, className = "" }) {
  return (
    <nav aria-label="Breadcrumb" className={`showcase-muted text-sm ${className}`.trim()}>
      {items.map((item, index) => (
        <span key={`${item.href ?? "current"}-${index}`}>
          {index > 0 && (
            <span className="mx-2" aria-hidden="true">
              /
            </span>
          )}
          {item.href ? (
            <Link href={item.href} className="hover:underline">
              {item.label}
            </Link>
          ) : (
            <span aria-current="page">{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}
