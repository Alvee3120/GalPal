import { backendFetch } from "@/lib/backendAuth";
import VideoCardManagement from "@/component/dashboard/videos/VideoCardManagement";

export const metadata = { title: "Video Cards | GalPal" };

// First page from the EXISTING GET /admin/videos/ (Admin and CCE; also served at /dashboard/admin/video-cards).
async function getVideos() {
  try {
    const res = await backendFetch("/admin/videos/?page_size=10");
    if (!res.ok) return { results: [], count: 0 };
    const data = await res.json();
    return { results: data.results ?? [], count: data.count ?? 0 };
  } catch {
    return { results: [], count: 0 };
  }
}

export default async function VideoCardsPage() {
  const { results, count } = await getVideos();
  return <VideoCardManagement initialVideos={results} initialCount={count} />;
}
