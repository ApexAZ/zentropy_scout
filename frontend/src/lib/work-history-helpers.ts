/**
 * @fileoverview Shared helpers for work history forms (onboarding + post-onboarding editor).
 *
 * Layer: lib/utility
 * Feature: persona
 *
 * REQ-012 §7.2.2: Conversion utilities between API WorkHistory
 * entities, form values, and request bodies. Also owns the Zod
 * validation schema, WorkHistoryFormData type, and toMonthValue
 * utility so that lib/ never imports from components/.
 *
 * Coordinates with:
 * - types/persona.ts: WorkHistory, WorkModel — API entity shapes
 *
 * Called by / Used by:
 * - components/onboarding/steps/work-history-form.tsx: onboarding form UI
 * - components/onboarding/steps/work-history-step.tsx: onboarding step wrapper
 * - components/persona/work-history-editor.tsx: post-onboarding editor
 */

import { z } from "zod";

import type { WorkHistory, WorkModel } from "@/types/persona";

// ---------------------------------------------------------------------------
// Constants (schema-only — not used in JSX)
// ---------------------------------------------------------------------------

/** Max length for text fields. */
const MAX_TEXT_LENGTH = 255;

/** Max length for industry field. */
const MAX_INDUSTRY_LENGTH = 100;

/** Max length for description. */
const MAX_DESCRIPTION_LENGTH = 5000;

/** Expected format for month input values. */
const MONTH_PATTERN = /^\d{4}-(0[1-9]|1[0-2])$/;

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

export const workHistoryFormSchema = z
	.object({
		job_title: z
			.string()
			.min(1, { message: "Job title is required" })
			.max(MAX_TEXT_LENGTH, { message: "Job title is too long" }),
		company_name: z
			.string()
			.min(1, { message: "Company name is required" })
			.max(MAX_TEXT_LENGTH, { message: "Company name is too long" }),
		company_industry: z
			.string()
			.max(MAX_INDUSTRY_LENGTH, { message: "Industry is too long" })
			.optional()
			.or(z.literal("")),
		location: z
			.string()
			.min(1, { message: "Location is required" })
			.max(MAX_TEXT_LENGTH, { message: "Location is too long" }),
		work_model: z.enum(["Remote", "Hybrid", "Onsite"] as const, {
			message: "Work model is required",
		}),
		start_date: z
			.string()
			.min(1, { message: "Start date is required" })
			.regex(MONTH_PATTERN, { message: "Invalid date format" }),
		end_date: z
			.string()
			.regex(MONTH_PATTERN, { message: "Invalid date format" })
			.optional()
			.or(z.literal("")),
		is_current: z.boolean(),
		description: z
			.string()
			.max(MAX_DESCRIPTION_LENGTH, { message: "Description is too long" })
			.optional()
			.or(z.literal("")),
	})
	.refine(
		(data) => data.is_current || (data.end_date && data.end_date.length > 0),
		{ message: "End date is required when not current", path: ["end_date"] },
	);

export type WorkHistoryFormData = z.infer<typeof workHistoryFormSchema>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Convert YYYY-MM-DD to YYYY-MM for the month input. */
export function toMonthValue(isoDate: string | null | undefined): string {
	if (!isoDate) return "";
	return isoDate.slice(0, 7); // "2020-01-01" → "2020-01"
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Shape of the request body sent to the work history API. */
export interface WorkHistoryRequestBody {
	job_title: string;
	company_name: string;
	company_industry: string | null;
	location: string;
	work_model: WorkModel;
	start_date: string;
	end_date: string | null;
	is_current: boolean;
	description: string | null;
}

/** Convert month input value (YYYY-MM) to ISO date (YYYY-MM-01). */
export function toIsoDate(monthValue: string): string {
	return monthValue ? `${monthValue}-01` : "";
}

/** Convert a WorkHistory entry to form initial values. */
export function toFormValues(entry: WorkHistory): Partial<WorkHistoryFormData> {
	return {
		job_title: entry.job_title,
		company_name: entry.company_name,
		company_industry: entry.company_industry ?? "",
		location: entry.location,
		work_model: entry.work_model,
		start_date: toMonthValue(entry.start_date),
		end_date: toMonthValue(entry.end_date),
		is_current: entry.is_current,
		description: entry.description ?? "",
	};
}

/** Convert form data to API request body. */
export function toRequestBody(
	data: WorkHistoryFormData,
): WorkHistoryRequestBody {
	return {
		job_title: data.job_title,
		company_name: data.company_name,
		company_industry: data.company_industry || null,
		location: data.location,
		work_model: data.work_model,
		start_date: toIsoDate(data.start_date),
		end_date: data.is_current ? null : toIsoDate(data.end_date ?? ""),
		is_current: data.is_current,
		description: data.description || null,
	};
}
