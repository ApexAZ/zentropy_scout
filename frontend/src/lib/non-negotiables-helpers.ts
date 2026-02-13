/**
 * Shared helpers for non-negotiables forms (onboarding + post-onboarding editor).
 *
 * REQ-012 §7.2.7: Conversion utilities between Persona non-negotiable
 * fields, form values, and request bodies. Also exports the shared
 * Zod validation schema, constants, and default form values.
 */

import { z } from "zod";

import type { Persona } from "@/types/persona";
import {
	COMPANY_SIZE_PREFERENCES,
	MAX_TRAVEL_PERCENTS,
	REMOTE_PREFERENCES,
} from "@/types/persona";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Max commute in minutes (8 hours). */
export const MAX_COMMUTE_MINUTES = 480;

/** Max salary value (prevents integer overflow in DB/downstream). */
export const MAX_SALARY = 999_999_999;

/** Common currency codes for the salary currency selector. */
export const CURRENCIES = [
	"USD",
	"EUR",
	"GBP",
	"CAD",
	"AUD",
	"CHF",
	"JPY",
	"CNY",
	"INR",
] as const;

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

/**
 * Positive-number string validator. Stored as string from the HTML number
 * input. Validates that the value is a positive number. Conversion to
 * number happens in toRequestBody().
 */
export const positiveNumberField = z.string().refine(
	(val) => {
		if (val === "") return true;
		const num = Number(val);
		return !Number.isNaN(num) && num > 0;
	},
	{ message: "Must be a positive number" },
);

/**
 * Commute field: positive number with upper bound.
 */
export const commuteField = positiveNumberField.refine(
	(val) => {
		if (val === "") return true;
		return Number(val) <= MAX_COMMUTE_MINUTES;
	},
	{ message: `Cannot exceed ${MAX_COMMUTE_MINUTES} minutes` },
);

/**
 * Salary field: positive number with upper bound.
 */
export const salaryField = positiveNumberField.refine(
	(val) => {
		if (val === "") return true;
		return Number(val) <= MAX_SALARY;
	},
	{ message: `Cannot exceed ${MAX_SALARY.toLocaleString()}` },
);

/** Zod validation schema for non-negotiables form fields. */
export const nonNegotiablesSchema = z.object({
	// Location
	// REMOTE_PREFERENCES is readonly string[] — double assertion needed
	// because z.enum() requires a mutable [string, ...string[]] tuple.
	remote_preference: z.enum(
		REMOTE_PREFERENCES as unknown as [string, ...string[]],
	),
	commutable_cities: z.array(z.string().trim().max(100)).max(20),
	max_commute_minutes: commuteField,
	relocation_open: z.boolean(),
	relocation_cities: z.array(z.string().trim().max(100)).max(20),

	// Compensation
	prefer_no_salary: z.boolean(),
	minimum_base_salary: salaryField,
	// CURRENCIES is readonly string[] — double assertion needed for z.enum().
	salary_currency: z.enum(CURRENCIES as unknown as [string, ...string[]]),

	// Other filters
	visa_sponsorship_required: z.boolean(),
	industry_exclusions: z.array(z.string().trim().max(100)).max(20),
	company_size_preference: z.enum(
		COMPANY_SIZE_PREFERENCES as unknown as [string, ...string[]],
	),
	max_travel_percent: z.enum(
		MAX_TRAVEL_PERCENTS as unknown as [string, ...string[]],
	),
});

export type NonNegotiablesFormData = z.infer<typeof nonNegotiablesSchema>;

export const NON_NEGOTIABLES_DEFAULT_VALUES: NonNegotiablesFormData = {
	remote_preference: "No Preference",
	commutable_cities: [],
	max_commute_minutes: "",
	relocation_open: false,
	relocation_cities: [],
	prefer_no_salary: true,
	minimum_base_salary: "",
	salary_currency: "USD",
	visa_sponsorship_required: false,
	industry_exclusions: [],
	company_size_preference: "No Preference",
	max_travel_percent: "None",
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Shape of the request body sent to the persona PATCH endpoint. */
export interface NonNegotiablesRequestBody {
	remote_preference: string;
	commutable_cities: string[];
	max_commute_minutes: number | null;
	relocation_open: boolean;
	relocation_cities: string[];
	minimum_base_salary: number | null;
	salary_currency: string;
	visa_sponsorship_required: boolean;
	industry_exclusions: string[];
	company_size_preference: string;
	max_travel_percent: string;
}

// ---------------------------------------------------------------------------
// Conversion functions
// ---------------------------------------------------------------------------

/** Convert Persona non-negotiable fields to form initial values. */
export function toFormValues(persona: Persona): NonNegotiablesFormData {
	return {
		// Location
		remote_preference: persona.remote_preference ?? "No Preference",
		commutable_cities: persona.commutable_cities ?? [],
		max_commute_minutes:
			persona.max_commute_minutes != null
				? String(persona.max_commute_minutes)
				: "",
		relocation_open: persona.relocation_open ?? false,
		relocation_cities: persona.relocation_cities ?? [],

		// Compensation
		prefer_no_salary: persona.minimum_base_salary == null,
		minimum_base_salary:
			persona.minimum_base_salary != null
				? String(persona.minimum_base_salary)
				: "",
		salary_currency: persona.salary_currency ?? "USD",

		// Other filters
		visa_sponsorship_required: persona.visa_sponsorship_required ?? false,
		industry_exclusions: persona.industry_exclusions ?? [],
		company_size_preference: persona.company_size_preference ?? "No Preference",
		max_travel_percent: persona.max_travel_percent ?? "None",
	};
}

/** Build API request body. Clears conditional fields and converts types. */
export function toRequestBody(
	data: NonNegotiablesFormData,
): NonNegotiablesRequestBody {
	const isRemoteOnly = data.remote_preference === "Remote Only";
	const commute = data.max_commute_minutes;
	const salary = data.minimum_base_salary;
	return {
		// Location
		remote_preference: data.remote_preference,
		commutable_cities: isRemoteOnly ? [] : data.commutable_cities,
		max_commute_minutes:
			isRemoteOnly || commute === "" ? null : Number(commute),
		relocation_open: data.relocation_open,
		relocation_cities: data.relocation_open ? data.relocation_cities : [],

		// Compensation
		minimum_base_salary:
			data.prefer_no_salary || salary === "" ? null : Number(salary),
		salary_currency: data.salary_currency,

		// Other filters
		visa_sponsorship_required: data.visa_sponsorship_required,
		industry_exclusions: data.industry_exclusions,
		company_size_preference: data.company_size_preference,
		max_travel_percent: data.max_travel_percent,
	};
}
