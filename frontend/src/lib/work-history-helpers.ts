/**
 * Shared helpers for work history forms (onboarding + post-onboarding editor).
 *
 * REQ-012 §7.2.2: Conversion utilities between API WorkHistory
 * entities, form values, and request bodies.
 */

import { toMonthValue } from "@/components/onboarding/steps/work-history-form";
import type { WorkHistoryFormData } from "@/components/onboarding/steps/work-history-form";
import type { WorkHistory, WorkModel } from "@/types/persona";

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
