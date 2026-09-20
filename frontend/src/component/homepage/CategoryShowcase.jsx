import CategoryRow from "./CategoryRow";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";
const REVALIDATE_SECONDS = 60;

// Fetches every page of {API_BASE_URL}/categories/?top_level=true and keeps only parent categories
// (`parent` is null for top-level categories; sub-categories carry their parent's slug).
async function getParentCategories() {
  const categories = [];
  let url = `${API_BASE_URL}/categories/?top_level=true`;

  try {
    while (url) {
      const res = await fetch(url, { next: { revalidate: REVALIDATE_SECONDS } });
      if (!res.ok) throw new Error(`Categories API responded ${res.status}`);
      const data = await res.json();
      categories.push(...(data.results ?? []).filter((c) => c.parent === null));
      url = data.next;
    }
  } catch (error) {
    console.error("Failed to load categories:", error);
    return [];
  }

  return categories;
}

function Heading() {
  return (
    <>
      <p className="showcase-muted text-xs font-medium uppercase tracking-widest">Shop by category</p>
      <h2 className="custom-font mt-2 text-3xl leading-tight md:text-4xl">Find your ritual</h2>
    </>
  );
}

// Same card footprint as the real row, so the page does not jump when data arrives.
export function CategoryShowcaseSkeleton() {
  return (
    <section aria-label="Shop by category" aria-busy="true" className="mx-auto w-full max-w-7xl px-4 py-12 sm:px-6 md:py-16 lg:px-8">
      <div className="mb-6 md:mb-8">
        <Heading />
      </div>
      <div className="flex gap-4 overflow-hidden md:gap-5">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className={`category-skeleton aspect-[3/4] w-[78%] shrink-0 animate-pulse sm:w-[46%] lg:w-[31%] xl:w-[23.5%] ${i > 1 ? "hidden sm:block" : ""}`}
          />
        ))}
      </div>
    </section>
  );
}

// If the API fails or there are no parent categories, the section is simply omitted.
export default async function CategoryShowcase() {
  const categories = await getParentCategories();
  if (categories.length === 0) return null;

  return (
    <section aria-label="Shop by category" className="mx-auto w-full max-w-7xl px-4 py-12 sm:px-6 md:py-16 lg:px-8">
      <CategoryRow categories={categories} heading={<Heading />} />
    </section>
  );
}
