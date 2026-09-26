import StaffLink from "@/component/dashboard/StaffLink";
import { getCurrencySymbol } from "@/lib/siteSettings";
import VideoCardForm from "@/component/dashboard/videos/VideoCardForm";

export const metadata = { title: "Add Video Card | GalPal" };

export default async function AddVideoCardPage() {
  const currencySymbol = await getCurrencySymbol();
  return (
    <div className="flex flex-col gap-6">
      <div>
        <StaffLink href="/dashboard/CCE/video-cards" className="showcase-muted text-sm hover:underline">
          &larr; Video Cards
        </StaffLink>
        <h1 className="custom-font mt-2 text-2xl sm:text-3xl">Add Video Card</h1>
      </div>
      <VideoCardForm currencySymbol={currencySymbol} />
    </div>
  );
}
