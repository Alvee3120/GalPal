import { notFound } from "next/navigation";
import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import StaffLink from "@/component/dashboard/StaffLink";
import VideoCardForm from "@/component/dashboard/videos/VideoCardForm";

export const metadata = { title: "Edit Video Card | GalPal" };

export default async function EditVideoCardPage({ params }) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const [res, currencySymbol] = await Promise.all([backendFetch(`/admin/videos/${id}/`), getCurrencySymbol()]);
  if (res.status === 404) notFound();
  if (!res.ok) throw new Error(`Unable to load video card ${id}`);
  const video = await res.json();
  return (
    <div className="flex flex-col gap-6">
      <div>
        <StaffLink href="/dashboard/CCE/video-cards" className="showcase-muted text-sm hover:underline">
          &larr; Video Cards
        </StaffLink>
        <h1 className="custom-font mt-2 text-2xl sm:text-3xl">Edit Video Card</h1>
        <p className="showcase-muted mt-1 text-sm">{video.title}</p>
      </div>
      <VideoCardForm key={`${video.id}-${video.updated_at}`} video={video} currencySymbol={currencySymbol} />
    </div>
  );
}
