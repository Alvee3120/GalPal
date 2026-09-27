import AuthShell from "@/component/auth/AuthShell";
import ForgotPasswordFlow from "@/component/auth/ForgotPasswordFlow";

export const metadata = { title: "Forgot Password | GalPal" };

export default function ForgotPasswordPage() {
  return (
    <AuthShell fit title="Let's get you back in." text="Reset your password with a one-time code sent to your email or phone, then log in as usual.">
      <ForgotPasswordFlow />
    </AuthShell>
  );
}
