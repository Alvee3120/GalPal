import AuthShell from "@/component/auth/AuthShell";
import AuthForm from "@/component/auth/AuthForm";

export const metadata = { title: "Log in | GalPal" };

export default function LoginPage() {
  return (
    <AuthShell
      fit
      title="Good to see you again."
      text="Log in to pick up your routine, review past orders and keep shopping the products you love."
    >
      <AuthForm mode="login" />
    </AuthShell>
  );
}
