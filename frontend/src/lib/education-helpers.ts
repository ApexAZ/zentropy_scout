/**
 * Shared helpers for education forms (onboarding + post-onboarding editor).
 *
 * REQ-012 §7.2.3: Conversion utilities between API Education
 * entities, form values, and request bodies.
 */

import type { EducationFormData } from "@/components/onboarding/steps/education-form";
import type { Education } from "@/types/persona";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Shape of the request body sent to the education API. */
export interface EducationRequestBody {
	institution: string;
	degree: string;
	field_of_study: string;
	graduation_year: number;
	gpa: number | null;
	honors: string | null;
}

// ---------------------------------------------------------------------------
// Conversion functions
// ---------------------------------------------------------------------------

/** Convert an Education entry to form initial values. */
export function toFormValues(entry: Education): Partial<EducationFormData> {
	return {
		institution: entry.institution,
		degree: entry.degree,
		field_of_study: entry.field_of_study,
		graduation_year: String(entry.graduation_year),
		gpa: entry.gpa === null ? "" : String(entry.gpa),
		honors: entry.honors ?? "",
	};
}

/** Convert form data to API request body. */
export function toRequestBody(data: EducationFormData): EducationRequestBody {
	return {
		institution: data.institution,
		degree: data.degree,
		field_of_study: data.field_of_study,
		graduation_year: Number.parseInt(data.graduation_year, 10),
		gpa: data.gpa ? Number.parseFloat(data.gpa) : null,
		honors: data.honors || null,
	};
}
