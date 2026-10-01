import LegalPage from "@/component/shared/LegalPage";

export const metadata = {
  title: "Privacy Policy | GalPal",
  description: "What personal information GalPal collects, how it's used and protected, and the choices you have.",
};

export default function PrivacyPolicyPage() {
  return (
    <LegalPage
      title="Privacy Policy"
      intro="Your privacy matters to us. This policy explains what information we collect when you use our website, why we collect it, and how we keep it safe."
    >
      <section>
        <h2>Information We Collect</h2>
        <ul>
          <li>
            <strong>Order details</strong>: your name, phone number, email (optional), delivery address and the products
            you order.
          </li>
          <li>
            <strong>Account details</strong>: if you create an account, your name, phone number, email and a securely
            encrypted password. We never store your password in readable form.
          </li>
          <li>
            <strong>Payment details</strong>: the payment method and, for online payments, the transaction reference. We
            don&apos;t store card numbers or mobile banking PINs.
          </li>
          <li>
            <strong>Reviews and requests</strong>: product reviews you submit, and &ldquo;Notify Me&rdquo; requests for
            out-of-stock products.
          </li>
          <li>
            <strong>Technical information</strong>: basic data such as your IP address and browser, used to keep the site
            secure and prevent fraud.
          </li>
        </ul>
      </section>

      <section>
        <h2>How We Use Your Information</h2>
        <ul>
          <li>To process, deliver and support your orders, including sharing delivery details with our courier partners.</li>
          <li>To contact you about your order, for example to confirm it or arrange delivery.</li>
          <li>To manage your account, including sending one-time verification codes by SMS or email.</li>
          <li>To let you know when a product you asked about is back in stock.</li>
          <li>To prevent fraud, keep the website secure and improve our products and service.</li>
        </ul>
        <p>We do not sell your personal information.</p>
      </section>

      <section>
        <h2>Cookies</h2>
        <p>We use a small number of cookies that the website needs to work:</p>
        <ul>
          <li>
            <strong>Login cookies</strong>, which keep you signed in to your account securely.
          </li>
          <li>
            <strong>A cart cookie</strong>, which remembers the items in your cart, even before you log in.
          </li>
        </ul>
        <p>
          We may also use analytics and advertising tools (such as Google Analytics, the Meta Pixel or the TikTok Pixel)
          to understand how the site is used and to measure our ads. These tools may set their own cookies. You can block
          or delete cookies in your browser settings, but parts of the site, like logging in and the cart, may stop
          working.
        </p>
      </section>

      <section>
        <h2>Sharing Your Information</h2>
        <p>We share your information only when it&apos;s needed to serve you or required by law:</p>
        <ul>
          <li>with courier and delivery partners, to deliver your order;</li>
          <li>with SMS, email and payment service providers, to send messages and process payments;</li>
          <li>with analytics and advertising providers, as described above;</li>
          <li>with authorities, when we are legally required to.</li>
        </ul>
      </section>

      <section>
        <h2>Keeping Your Information Safe</h2>
        <p>
          We use secure connections, encrypted passwords and restricted staff access to protect your information. Only
          authorised team members can view order details, and only to do their job. No online service can be perfectly
          secure, but we work hard to protect your data.
        </p>
      </section>

      <section>
        <h2>Your Choices</h2>
        <ul>
          <li>You can view and update your account details and saved addresses at any time from your account.</li>
          <li>You can ask us to correct or delete your personal information by contacting us below.</li>
          <li>
            We keep order records for as long as needed for delivery, returns, accounting and legal reasons, even if an
            account is closed.
          </li>
        </ul>
      </section>

      <section>
        <h2>Changes to This Policy</h2>
        <p>
          We may update this policy from time to time. When we do, we&apos;ll change the &ldquo;Last updated&rdquo; date
          above. Continuing to use the website means you accept the updated policy.
        </p>
      </section>
    </LegalPage>
  );
}
