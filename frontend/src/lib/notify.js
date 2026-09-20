import { toast } from "sonner";

// The ONE way to show feedback anywhere in the app (client components only).
//   notify.success("Login successful!")   notify.error("Unable to add product to cart.")
// The toast id is the message itself, so firing the same message repeatedly (double clicks, re-renders,
// repeated callbacks) updates the existing toast instead of stacking duplicates.
const DURATION = { success: 3000, error: 4500 };

export const notify = {
  success: (message, options) => toast.success(message, { id: `success:${message}`, duration: DURATION.success, ...options }),
  error: (message, options) => toast.error(message, { id: `error:${message}`, duration: DURATION.error, ...options }),
};
