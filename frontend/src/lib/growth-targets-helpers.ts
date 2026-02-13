/**
 * Shared helpers for growth targets forms (onboarding + post-onboarding editor).
 *
 * REQ-012 §7.2.8: Conversion utilities between Persona growth target
 * fields, form values, and request bodies. Also exports the shared
 * Zod validation schema, constants, and default form values.
 */

import { z } from "zod";

import type { Persona } from "@/types/persona";
import { STRETCH_APPETITES } from "@/types/persona";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Stretch appetite option descriptions shown below each radio. */
export const STRETCH_DESCRIPTIONS: Readonly<Record<string, string>> = {
	Low: "Show me roles I'm already qualified for",
	Medium: "Mix of comfortable and stretch roles",
	High: "Challenge me — I want to grow into new areas",
};

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

/** Zod validation schema for growth targets form fields. */
export const growthTargetsSchema = z.object({
	target_roles: z.array(z.string().trim().min(1).max(100)).max(20),
	target_skills: z.array(z.string().trim().min(1).max(100)).max(20),
	stretch_appetite: z.enum(
		STRETCH_APPETITES as unknown as [string, ...string[]],
	),
});

export type GrowthTargetsFormData = z.infer<typeof growthTargetsSchema>;

export const GROWTH_TARGETS_DEFAULT_VALUES: GrowthTargetsFormData = {
	target_roles: [],
	target_skills: [],
	stretch_appetite: "Medium",
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Shape of the request body sent to the persona PATCH endpoint. */
export interface GrowthTargetsRequestBody {
	target_roles: string[];
	target_skills: string[];
	stretch_appetite: string;
}

// ---------------------------------------------------------------------------
// Conversion functions
// ---------------------------------------------------------------------------

/** Convert Persona growth target fields to form initial values. */
export function toFormValues(persona: Persona): GrowthTargetsFormData {
	return {
		target_roles: persona.target_roles ?? [],
		target_skills: persona.target_skills ?? [],
		stretch_appetite: persona.stretch_appetite ?? "Medium",
	};
}

/** Build API request body from form data. */
export function toRequestBody(
	data: GrowthTargetsFormData,
): GrowthTargetsRequestBody {
	return {
		target_roles: data.target_roles,
		target_skills: data.target_skills,
		stretch_appetite: data.stretch_appetite,
	};
}
