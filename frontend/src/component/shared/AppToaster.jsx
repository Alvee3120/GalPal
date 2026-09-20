"use client";

import { Toaster } from "sonner";
import { FiAlertCircle, FiCheckCircle, FiX } from "react-icons/fi";

// The single global toast container (mounted once in the root layout). Position, spacing, durations,
// icons and close button are configured here; colors come from the --color-toast-* tokens in globals.css.
export default function AppToaster() {
  return (
    <Toaster
      position="top-right"
      // sit just below the 4rem sticky navbar so toasts never cover the account/cart icons
      offset={{ top: "4.75rem", right: "1rem" }}
      mobileOffset={{ top: "4.5rem", right: "0.75rem", left: "0.75rem" }}
      closeButton
      visibleToasts={3}
      duration={3000}
      gap={10}
      theme="light"
      icons={{
        success: <FiCheckCircle className="h-5 w-5" aria-hidden="true" />,
        error: <FiAlertCircle className="h-5 w-5" aria-hidden="true" />,
        close: <FiX className="h-4 w-4" aria-hidden="true" />,
      }}
      toastOptions={{
        classNames: {
          toast: "app-toast",
          success: "app-toast--success",
          error: "app-toast--error",
          title: "app-toast__title",
          icon: "app-toast__icon",
          closeButton: "app-toast__close",
          actionButton: "app-toast__action",
        },
      }}
    />
  );
}
