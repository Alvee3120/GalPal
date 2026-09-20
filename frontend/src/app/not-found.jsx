import NotFoundPage from "@/component/shared/NotFoundPage";

export const metadata = { title: "Page not found | GalPal" };

// App Router renders this (with an HTTP 404) for any unmatched route.
export default function NotFound() {
  return <NotFoundPage />;
}
