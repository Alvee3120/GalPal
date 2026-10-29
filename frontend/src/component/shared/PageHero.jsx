import Breadcrumbs from "./Breadcrumbs";

// Breadcrumb + page title band, shared by /shop, /cart and any future top-level page. Matches the muted
// section other pages (e.g. the category showcase) already use.
export default function PageHero({ title }) {
  return (
    <div className="shop-hero w-full py-10 text-center sm:py-14 mb-5">
      <h1 className="custom-font text-3xl sm:text-4xl">{title}</h1>
      <Breadcrumbs className="mt-2" items={[{ label: "Home", href: "/" }, { label: title }]} />
    </div>
  );
}
