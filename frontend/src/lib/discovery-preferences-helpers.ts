/**
 * Shared helpers for discovery preferences editor.
 *
 * REQ-012 §7.2.9: Schema, defaults, and conversion functions for
 * minimum fit threshold (slider 0-100), auto-draft threshold
 * (slider 0-100), and polling frequency (select).
 */

import { z } from "zod";

import type { Persona } from "@/types/persona";
import { POLLING_FREQUENCIES } from "@/types/persona";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Explanation text displayed alongside each control. */
export const EXPLANATION_TEXT = {
	minimum_fit_threshold: (n: number) =>
		`Jobs scoring below ${n} will be hidden from your feed`,
	auto_draft_threshold: (n: number) =>
		`I'll automatically draft materials for jobs scoring ${n} or above`,
	polling_frequency: "How often should I check for new jobs?",
} as const;

/** Cross-field validation warning message. */
export const THRESHOLD_WARNING =
	"Auto-draft threshold is below your fit threshold — you may get drafts for jobs that are hidden from your feed.";

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

/** Zod validation schema for discovery preferences form fields. */
export const discoveryPreferencesSchema = z.object({
	minimum_fit_threshold: z.number().int().min(0).max(100),
	auto_draft_threshold: z.number().int().min(0).max(100),
	polling_frequency: z.enum(
		POLLING_FREQUENCIES as unknown as [string, ...string[]],
	),
});

export type DiscoveryPreferencesFormData = z.infer<
	typeof discoveryPreferencesSchema
>;

export const DISCOVERY_PREFERENCES_DEFAULT_VALUES: DiscoveryPreferencesFormData =
	{
		minimum_fit_threshold: 50,
		auto_draft_threshold: 90,
		polling_frequency: "Daily",
	};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Shape of the request body sent to the persona PATCH endpoint. */
export interface DiscoveryPreferencesRequestBody {
	minimum_fit_threshold: number;
	auto_draft_threshold: number;
	polling_frequency: string;
}

// ---------------------------------------------------------------------------
// Conversion functions
// ---------------------------------------------------------------------------

/** Convert Persona discovery preference fields to form initial values. */
export function toFormValues(persona: Persona): DiscoveryPreferencesFormData {
	return {
		minimum_fit_threshold: persona.minimum_fit_threshold ?? 50,
		auto_draft_threshold: persona.auto_draft_threshold ?? 90,
		polling_frequency: persona.polling_frequency ?? "Daily",
	};
}

/** Build API request body from form data. */
export function toRequestBody(
	data: DiscoveryPreferencesFormData,
): DiscoveryPreferencesRequestBody {
	return {
		minimum_fit_threshold: data.minimum_fit_threshold,
		auto_draft_threshold: data.auto_draft_threshold,
		polling_frequency: data.polling_frequency,
	};
}
