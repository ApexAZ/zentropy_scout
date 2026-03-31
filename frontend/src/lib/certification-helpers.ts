/**
 * Shared helpers for certification forms (onboarding + post-onboarding editor).
 *
 * REQ-012 §7.2.3: Conversion utilities between API Certification
 * entities, form values, and request bodies. Also owns the Zod
 * validation schema and CertificationFormData type so that lib/
 * never imports from components/.
 */

import { z } from "zod";

import type { Certification } from "@/types/persona";

// ---------------------------------------------------------------------------
// Constants (schema-only — not used in JSX)
// ---------------------------------------------------------------------------

/** Max length for certification name. */
const MAX_CERT_NAME_LENGTH = 255;

/** Max length for issuing organization. */
const MAX_ISSUER_LENGTH = 255;

/** Max length for credential ID. */
const MAX_CREDENTIAL_ID_LENGTH = 100;

/** Max length for verification URL. */
const MAX_URL_LENGTH = 2083;

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

export const certificationFormSchema = z.object({
	certification_name: z
		.string()
		.min(1, { message: "Certification name is required" })
		.max(MAX_CERT_NAME_LENGTH, { message: "Certification name is too long" }),
	issuing_organization: z
		.string()
		.min(1, { message: "Issuing organization is required" })
		.max(MAX_ISSUER_LENGTH, { message: "Issuing organization is too long" }),
	date_obtained: z.string().min(1, { message: "Date obtained is required" }),
	does_not_expire: z.boolean(),
	expiration_date: z.string().optional().or(z.literal("")),
	credential_id: z
		.string()
		.max(MAX_CREDENTIAL_ID_LENGTH, { message: "Credential ID is too long" })
		.optional()
		.or(z.literal("")),
	verification_url: z
		.string()
		.max(MAX_URL_LENGTH, { message: "URL is too long" })
		.optional()
		.or(z.literal(""))
		.refine(
			(val) => {
				if (!val || val === "") return true;
				try {
					const url = new URL(val);
					return url.protocol === "https:" || url.protocol === "http:";
				} catch {
					return false;
				}
			},
			{ message: "Enter a valid URL (http:// or https://)" },
		),
});

export type CertificationFormData = z.infer<typeof certificationFormSchema>;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Shape of the request body sent to the certification API. */
export interface CertificationRequestBody {
	certification_name: string;
	issuing_organization: string;
	date_obtained: string;
	expiration_date: string | null;
	credential_id: string | null;
	verification_url: string | null;
}

// ---------------------------------------------------------------------------
// Conversion functions
// ---------------------------------------------------------------------------

/** Convert a Certification entry to form initial values. */
export function toFormValues(
	entry: Certification,
): Partial<CertificationFormData> {
	return {
		certification_name: entry.certification_name,
		issuing_organization: entry.issuing_organization,
		date_obtained: entry.date_obtained,
		does_not_expire: entry.expiration_date === null,
		expiration_date: entry.expiration_date ?? "",
		credential_id: entry.credential_id ?? "",
		verification_url: entry.verification_url ?? "",
	};
}

/** Convert form data to API request body. */
export function toRequestBody(
	data: CertificationFormData,
): CertificationRequestBody {
	return {
		certification_name: data.certification_name,
		issuing_organization: data.issuing_organization,
		date_obtained: data.date_obtained,
		expiration_date: data.does_not_expire ? null : data.expiration_date || null,
		credential_id: data.credential_id || null,
		verification_url: data.verification_url || null,
	};
}
