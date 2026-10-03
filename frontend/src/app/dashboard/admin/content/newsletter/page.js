import { backendFetch } from "@/lib/backendAuth";
import NewsletterSubscribers from "@/component/dashboard/content/NewsletterSubscribers";

export const metadata = { title: "Newsletter | GalPal" };

// Newsletter sign-ups (Admin only: this admin layout guards the route, and the backend's content API is IsAdmin).
async function getJson(path) {
  try {
    const res = await backendFetch(path);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export default async function Page() {
  return <NewsletterSubscribers initial={await getJson("/admin/content/newsletter/?page_size=20")} />;
}
