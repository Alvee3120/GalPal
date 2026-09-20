import AuthShell from "@/component/auth/AuthShell";
import AuthForm from "@/component/auth/AuthForm";

export const metadata = { title: "Create an account | GalPal" };

export default function RegisterPage() {
  return (
    <AuthShell
      fit
      title="Find a skincare routine that works."
      text="Join GalPal to save your favourites, track your orders and get product picks that suit your skin."
    >
      <AuthForm mode="register" />
    </AuthShell>
  );
}
