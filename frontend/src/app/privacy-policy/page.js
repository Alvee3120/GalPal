import LegalPage from "@/component/shared/LegalPage";
import CmsPage, { cmsMetadata } from "@/component/content/CmsPage";
import { getContentPage } from "@/lib/content";

const FALLBACK_METADATA = {
  title: "Privacy Policy | GalPal",
  description: "What information Gal Pal may collect when you shop or communicate with us, how we use it, and how we protect it.",
};

// Admin → Content Pages can replace this text with a "privacy-policy" page; until then the built-in text below shows.
export async function generateMetadata() {
  return cmsMetadata(await getContentPage("privacy-policy"), FALLBACK_METADATA);
}

export default async function PrivacyPolicyPage() {
  const page = await getContentPage("privacy-policy");
  if (page) return <CmsPage page={page} />;
  return (
    <LegalPage
      title="Privacy Policy"
      intro="At Gal Pal, we respect your privacy and are committed to protecting the information you provide when you shop with us or communicate with us."
      updated="4 October 2026"
    >
      <p>This Privacy Policy explains what information we may collect, how we use it, and how we protect it.</p>

      <section>
        <h2>Information We Collect</h2>
        <p>When you place an order, contact us, or use our website, we may collect information such as:</p>
        <ul>
          <li>Name</li>
          <li>Phone number</li>
          <li>Email address</li>
          <li>Delivery and billing address</li>
          <li>Order and purchase information</li>
          <li>Payment related information, where applicable</li>
          <li>Information you provide when contacting our customer service team</li>
          <li>Information submitted through our website, social media pages, or other communication channels</li>
        </ul>
        <p>
          Our website may also automatically collect certain technical information, such as device type, browser information,
          IP address, and website usage information, depending on the technologies and analytics tools used on the website.
        </p>
      </section>
    </LegalPage>
  );
}
