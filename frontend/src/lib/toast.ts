/**
 * Standardized toast helpers wrapping sonner.
 * Provides consistent patterns for success, error, promise, and action toasts.
 */
import { toast as sonner } from "sonner";
import { normalizeApiError } from "@/lib/api/errors";

export const notify = {
  success(message: string, description?: string) {
    sonner.success(message, { description });
  },

  error(message: string, description?: string) {
    sonner.error(message, { description });
  },

  /** Extract a user-friendly message from any error shape. */
  apiError(error: unknown, fallback = "Something went wrong") {
    const normalized = normalizeApiError(error);
    sonner.error(normalized.message || fallback);
  },

  info(message: string, description?: string) {
    sonner.info(message, { description });
  },

  /**
   * Wrap a promise with loading → success → error toasts.
   *
   *   notify.promise(saveData(), {
   *     loading: "Saving…",
   *     success: "Saved!",
   *     error: "Save failed",
   *   });
   */
  promise<T>(
    promise: Promise<T>,
    messages: { loading: string; success: string; error: string }
  ) {
    return sonner.promise(promise, messages);
  },

  /** Toast with an undo/action button. */
  action(
    message: string,
    opts: { label: string; onClick: () => void; description?: string }
  ) {
    sonner(message, {
      description: opts.description,
      action: { label: opts.label, onClick: opts.onClick },
    });
  },

  dismiss(id?: string | number) {
    sonner.dismiss(id);
  },
};
