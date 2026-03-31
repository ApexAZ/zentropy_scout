/**
 * Shared error utilities for form components.
 *
 * REQ-012 §13.2: Provides consistent user-facing error messages
 * across all onboarding and persona editor forms. Maps API error
 * codes to friendly strings so components stay presentation-only.
 *
 * @module lib/form-errors
 * @coordinates-with api-client (ApiError class used for instanceof check),
 *   all onboarding step and persona editor forms (import toFriendlyError),
 *   hooks/use-crud-step (centralised error handling for onboarding steps)
 */

import { ApiError } from "@/lib/api-client";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Friendly error messages keyed by API error code. */
const FRIENDLY_ERROR_MESSAGES: Readonly<Record<string, string>> = {
	VALIDATION_ERROR: "Please check your input and try again.",
	DUPLICATE_EMAIL: "This email address is already in use.",
	DUPLICATE_NAME:
		"A resume with this name already exists. Please choose a different name.",
	EXTRACTION_FAILED:
		"Couldn't extract job details. Try pasting more of the description.",
	DUPLICATE_JOB: "This job is already in your list.",
	TOKEN_EXPIRED: "Preview expired. Please resubmit.",
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
