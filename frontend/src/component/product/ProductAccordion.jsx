import { FiMinus, FiPlus } from "react-icons/fi";

const label = (value) => String(value).replace(/^./, (c) => c.toUpperCase());

// Details, User Guide and Ingredients are always listed (with "Not available." when the product has no text yet);
// Product Information only appears when the product has that data.
function buildSections(product) {
  const size = product.size_value ? `${Number(product.size_value)} ${product.size_unit}`.trim() : "";
  const info = [
    ["Size", size],
    ["Skin Type", (product.skin_type ?? []).map(label).join(", ")],
    ["Gender", product.gender ? label(product.gender) : ""],
    ["Country of Origin", product.country_of_origin],
    ["Expiry Date", product.expiry_date],
  ].filter(([, value]) => value);

  return [
    { key: "detail", title: "Details", html: product.full_description },
    { key: "how", title: "User Guide", html: product.user_guide },
    {
      key: "ingredients",
      title: "Ingredients",
      highlights: product.key_ingredients ?? [],
      text: product.ingredients,
      empty: !product.ingredients && !product.key_ingredients?.length,
    },
    info.length > 0 && { key: "info", title: "Product Information", rows: info },
  ].filter(Boolean);
}

// Expandable product information (Detail / How To Use / Ingredients / Product Information). Native <details>, so it is
// keyboard and screen-reader accessible with no extra state; every section starts closed.
export default function ProductAccordion({ product }) {
  const sections = buildSections(product);
  if (sections.length === 0) return null;

  return (
    <div className="product-accordion mt-8">
      {sections.map((section) => (
        <details key={section.key} className="group">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 text-sm font-bold [&::-webkit-details-marker]:hidden">
            {section.title}
            <FiPlus className="h-4 w-4 shrink-0 group-open:hidden" aria-hidden="true" />
            <FiMinus className="hidden h-4 w-4 shrink-0 group-open:block" aria-hidden="true" />
          </summary>
          <div className="pb-5 text-sm leading-relaxed">
            {"html" in section &&
              (section.html ? <div className="accordion-text" dangerouslySetInnerHTML={{ __html: section.html }} /> : <p className="accordion-text">Not available.</p>)}
            {section.highlights?.length > 0 && (
              <ul className="mb-3 flex flex-wrap gap-2">
                {section.highlights.map((item) => (
                  <li key={item} className="product-card__chip rounded-full px-3 py-1 text-xs font-medium">
                    {item}
                  </li>
                ))}
              </ul>
            )}
            {section.text && <p className="accordion-text">{section.text}</p>}
            {section.empty && <p className="accordion-text">Not available.</p>}
            {section.rows && (
              <dl className="flex flex-col gap-2">
                {section.rows.map(([name, value]) => (
                  <div key={name} className="flex justify-between gap-4">
                    <dt className="showcase-muted">{name}</dt>
                    <dd className="text-right font-medium">{value}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
        </details>
      ))}
    </div>
  );
}
