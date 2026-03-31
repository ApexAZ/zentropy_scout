/**
 * @fileoverview Shared helpers for education forms (onboarding + post-onboarding editor).
 *
 * Layer: lib/utility
 * Feature: persona
 *
 * REQ-012 §7.2.3: Conversion utilities between API Education
 * entities, form values, and request bodies. Also owns the Zod
 * validation schema and EducationFormData type so that lib/
 * never imports from components/.
 *
 * Coordinates with:
 * - types/persona.ts: Education — API entity shape
 *
 * Called by / Used by:
 * - components/onboarding/steps/education-form.tsx: onboarding form UI
 * - components/onboarding/steps/education-step.tsx: onboarding step wrapper
 * - components/persona/education-editor.tsx: post-onboarding editor
 */

import { z } from "zod";

import type { Education } from "@/types/persona";

// ---------------------------------------------------------------------------
// Constants (schema-only — not used in JSX)
// ---------------------------------------------------------------------------

/** Max length for institution name. */
const MAX_INSTITUTION_LENGTH = 255;

/** Max length for degree. */
const MAX_DEGREE_LENGTH = 100;

/** Max length for field of study. */
const MAX_FIELD_LENGTH = 255;

/** Max length for honors. */
const MAX_HONORS_LENGTH = 255;

/** Earliest allowed graduation year. */
const MIN_GRADUATION_YEAR = 1950;

/** Latest allowed graduation year. */
const MAX_GRADUATION_YEAR = 2100;

/** Maximum GPA value. */
const MAX_GPA = 4;

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

/**
 * Numeric fields stored as strings in the form (HTML inputs return strings).
 * Conversion to numbers happens in toRequestBody() at the step level.
 */
export const educationFormSchema = z.object({
	institution: z
		.string()
		.min(1, { message: "Institution is required" })
		.max(MAX_INSTITUTION_LENGTH, { message: "Institution name is too long" }),
	degree: z
		.string()
		.min(1, { message: "Degree is required" })
		.max(MAX_DEGREE_LENGTH, { message: "Degree is too long" }),
	field_of_study: z
		.string()
		.min(1, { message: "Field of study is required" })
		.max(MAX_FIELD_LENGTH, { message: "Field of study is too long" }),
	graduation_year: z
		.string()
		.min(1, { message: "Graduation year is required" })
		.refine((val) => /^\d{4}$/.test(val), {
			message: "Enter a valid 4-digit year",
		})
		.refine(
			(val) => {
				const year = Number.parseInt(val, 10);
				return year >= MIN_GRADUATION_YEAR;
			},
			{ message: `Year must be ${MIN_GRADUATION_YEAR} or later` },
		)
		.refine(
			(val) => {
				const year = Number.parseInt(val, 10);
				return year <= MAX_GRADUATION_YEAR;
			},
			{ message: `Year must be ${MAX_GRADUATION_YEAR} or earlier` },
		),
	gpa: z
		.string()
		.optional()
		.or(z.literal(""))
		.refine(
			(val) => {
				if (!val || val === "") return true;
				const num = Number.parseFloat(val);
				return !Number.isNaN(num) && num >= 0 && num <= MAX_GPA;
			},
			{ message: `GPA must be between 0 and ${MAX_GPA}` },
		),
	honors: z
		.string()
		.max(MAX_HONORS_LENGTH, "Honors is too long")
		.optional()
		.or(z.literal("")),
});

export type EducationFormData = z.infer<typeof educationFormSchema>;

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
