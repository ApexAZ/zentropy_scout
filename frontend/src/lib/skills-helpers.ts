/**
 * Shared helpers for skill forms (onboarding + post-onboarding editor).
 *
 * REQ-012 §7.2.4: Conversion utilities between API Skill
 * entities, form values, and request bodies.
 */

import { z } from "zod";

import type { Proficiency, Skill, SkillType } from "@/types/persona";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_SKILL_NAME_LENGTH = 100;
const MAX_CATEGORY_LENGTH = 100;
const MAX_LAST_USED_LENGTH = 20;
export const MAX_YEARS_USED = 70;

/** Hard skill category defaults (REQ-001 §3.4). */
export const HARD_SKILL_CATEGORIES = [
	"Programming Language",
	"Framework / Library",
	"Tool / Software",
	"Platform / Infrastructure",
	"Methodology",
	"Domain Knowledge",
] as const;

/** Soft skill category defaults (REQ-001 §3.4). */
export const SOFT_SKILL_CATEGORIES = [
	"Leadership & Management",
	"Communication",
	"Collaboration",
	"Problem Solving",
	"Adaptability",
] as const;

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

export const skillFormSchema = z.object({
	skill_name: z
		.string()
		.min(1, { message: "Skill name is required" })
		.max(MAX_SKILL_NAME_LENGTH, { message: "Skill name is too long" }),
	skill_type: z.enum(["Hard", "Soft"], {
		message: "Skill type is required",
	}),
	category: z
		.string()
		.min(1, { message: "Category is required" })
		.max(MAX_CATEGORY_LENGTH, { message: "Category is too long" }),
	proficiency: z.enum(["Learning", "Familiar", "Proficient", "Expert"], {
		message: "Proficiency is required",
	}),
	years_used: z
		.string()
		.min(1, { message: "Years used is required" })
		.refine((val) => /^\d+$/.test(val), {
			message: "Enter a valid number",
		})
		.refine((val) => Number.parseInt(val, 10) >= 1, {
			message: "Must be at least 1",
		})
		.refine((val) => Number.parseInt(val, 10) <= MAX_YEARS_USED, {
			message: `Must be at most ${MAX_YEARS_USED}`,
		}),
	last_used: z
		.string()
		.min(1, { message: "Last used is required" })
		.max(MAX_LAST_USED_LENGTH, { message: "Last used is too long" }),
});

export type SkillFormData = z.infer<typeof skillFormSchema>;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Shape of the request body sent to the skill API. */
export interface SkillRequestBody {
	skill_name: string;
	skill_type: SkillType;
	category: string;
	proficiency: Proficiency;
	years_used: number;
	last_used: string;
}

// ---------------------------------------------------------------------------
// Conversion functions
// ---------------------------------------------------------------------------

/** Convert a Skill entry to form initial values. */
export function toFormValues(entry: Skill): Partial<SkillFormData> {
	return {
		skill_name: entry.skill_name,
		skill_type: entry.skill_type,
		category: entry.category,
		proficiency: entry.proficiency,
		years_used: String(entry.years_used),
		last_used: entry.last_used,
	};
}

/** Convert form data to API request body. */
export function toRequestBody(data: SkillFormData): SkillRequestBody {
	return {
		skill_name: data.skill_name,
		skill_type: data.skill_type,
		category: data.category,
		proficiency: data.proficiency,
		years_used: Number.parseInt(data.years_used, 10),
		last_used: data.last_used,
	};
}
