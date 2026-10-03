import { notFound, redirect } from "next/navigation";
import CmsPage, { cmsMetadata } from "@/component/content/CmsPage";
import { getContentPage } from "@/lib/content";
import { STANDARD_PAGE_PATH } from "@/lib/contentAdmin";

// Any other page made in Admin → Content Pages, at /pages/<slug>. Standard pages live at their own routes.
export async function generateMetadata({ params }) {
  const { slug } = await params;
  return cmsMetadata(await getContentPage(slug), { title: "Page not found | GalPal" });
}

export default async function ContentPage({ params }) {
  const { slug } = await params;
  if (STANDARD_PAGE_PATH[slug]) redirect(STANDARD_PAGE_PATH[slug]);
  const page = await getContentPage(slug);
  if (!page) notFound();
  return <CmsPage page={page} />;
}
