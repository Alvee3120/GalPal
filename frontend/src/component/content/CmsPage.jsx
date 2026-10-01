import LegalPage from "@/component/shared/LegalPage";
import { formatUpdated } from "@/lib/content";
import RichText from "./RichText";

// A page whose text comes from Admin → Content Pages (apps.content Page), in the same layout as the built-in policy
// pages: hero, "Last updated" (the page's own save date) and the Site Settings contact block.
export default function CmsPage({ page }) {
  return (
    <LegalPage title={page.title} updated={formatUpdated(page.updated_at)}>
      <RichText text={page.content} sectioned />
    </LegalPage>
  );
}

// generateMetadata helper: the page's SEO fields, else its title, else the built-in page's metadata.
export function cmsMetadata(page, fallback) {
  if (!page) return fallback;
  return {
    title: page.meta_title || `${page.title} | GalPal`,
    description: page.meta_description || fallback?.description,
  };
}
