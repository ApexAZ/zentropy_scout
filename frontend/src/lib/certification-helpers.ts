/**
 * Shared helpers for certification forms (onboarding + post-onboarding editor).
 *
 * REQ-012 §7.2.3: Conversion utilities between API Certification
 * entities, form values, and request bodies.
 */

import type { CertificationFormData } from "@/components/onboarding/steps/certification-form";
import type { Certification } from "@/types/persona";

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
