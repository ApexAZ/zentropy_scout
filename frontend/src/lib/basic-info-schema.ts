/**
 * Shared Zod schema fields for basic info forms.
 *
 * Used by both the onboarding BasicInfoStep and the persona BasicInfoEditor
 * to validate the 8 common personal fields (full_name, email, phone,
 * linkedin_url, portfolio_url, home_city, home_state, home_country).
 */

import { z } from "zod";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Max length for general text fields. */
export const MAX_TEXT_LENGTH = 200;

/** Max length for email per RFC 5321. */
export const MAX_EMAIL_LENGTH = 254;

/** Max length for phone numbers (international format). */
export const MAX_PHONE_LENGTH = 30;

/** Max length for URL fields (browser practical limit). */
export const MAX_URL_LENGTH = 2083;

// ---------------------------------------------------------------------------
// Reusable schemas
// ---------------------------------------------------------------------------

/** URL schema: must be http(s) and within length limit. */
export const httpUrl = z
	.url({ message: "Invalid URL format" })
	.max(MAX_URL_LENGTH, "URL is too long")
	.refine(
		(val) => val.startsWith("https://") || val.startsWith("http://"),
		"URL must start with http:// or https://",
	);

/**
 * The 8 basic info field schemas shared by step and editor forms.
 *
 * Usage: `z.object({ ...BASIC_INFO_FIELDS, ...extraFields })`
 */
export const BASIC_INFO_FIELDS = {
	full_name: z
		.string()
		.min(1, { message: "Full name is required" })
		.max(MAX_TEXT_LENGTH, { message: "Full name is too long" }),
	email: z
		.string()
		.min(1, { message: "Email is required" })
		.max(MAX_EMAIL_LENGTH, { message: "Email is too long" })
		.check(z.email({ message: "Invalid email format" })),
	phone: z
		.string()
		.min(1, { message: "Phone number is required" })
		.max(MAX_PHONE_LENGTH, { message: "Phone number is too long" }),
	linkedin_url: z.union([httpUrl, z.literal("")]),
	portfolio_url: z.union([httpUrl, z.literal("")]),
	home_city: z
		.string()
		.min(1, { message: "City is required" })
		.max(MAX_TEXT_LENGTH, { message: "City name is too long" }),
	home_state: z
		.string()
		.min(1, { message: "State is required" })
		.max(MAX_TEXT_LENGTH, { message: "State name is too long" }),
	home_country: z
		.string()
		.min(1, { message: "Country is required" })
		.max(MAX_TEXT_LENGTH, { message: "Country name is too long" }),
} as const;
