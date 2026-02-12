/**
 * Shared error utilities for form components.
 *
 * Provides consistent user-facing error messages across all
 * onboarding and persona editor forms.
 */

import { ApiError } from "@/lib/api-client";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Friendly error messages keyed by API error code. */
const FRIENDLY_ERROR_MESSAGES: Readonly<Record<string, string>> = {
	VALIDATION_ERROR: "Please check your input and try again.",
};

/** Fallback error message for unexpected errors. */
export const GENERIC_ERROR_MESSAGE = "Failed to save. Please try again.";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Map an ApiError to a user-friendly message. */
export function toFriendlyError(err: unknown): string {
	if (err instanceof ApiError) {
		return FRIENDLY_ERROR_MESSAGES[err.code] ?? GENERIC_ERROR_MESSAGE;
	}
	return GENERIC_ERROR_MESSAGE;
}
