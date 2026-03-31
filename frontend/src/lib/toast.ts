/**
 * Toast notification facade with variant-specific durations.
 *
 * REQ-012 §13.5: Wraps Sonner's toast API with project-standard
 * duration defaults — errors persist, success auto-dismisses at 3 s.
 *
 * @module lib/toast
 * @coordinates-with api-client (error/401 toasts),
 *   embedding-staleness (status toasts),
 *   app/layout.tsx (mounts Sonner Toaster via components/ui/sonner)
 */

import { type ExternalToast, toast } from "sonner";

/**
 * REQ-012 §13.5 — Default durations per toast variant.
 *
 * - Success: 3 s auto-dismiss
 * - Error:   persistent (must be manually dismissed)
 * - Warning: 5 s auto-dismiss
 * - Info:    5 s auto-dismiss
 */
const DURATION = {
	success: 3000,
	error: Infinity,
	warning: 5000,
	info: 5000,
} as const;

function success(message: string, options?: ExternalToast) {
	return toast.success(message, { duration: DURATION.success, ...options });
}

function error(message: string, options?: ExternalToast) {
	return toast.error(message, { duration: DURATION.error, ...options });
}

function warning(message: string, options?: ExternalToast) {
	return toast.warning(message, { duration: DURATION.warning, ...options });
}

function info(message: string, options?: ExternalToast) {
	return toast.info(message, { duration: DURATION.info, ...options });
}

function dismiss(toastId?: string | number) {
	toast.dismiss(toastId);
}

export const showToast = { success, error, warning, info, dismiss };
