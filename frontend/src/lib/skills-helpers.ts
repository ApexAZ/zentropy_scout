/**
 * Shared helpers for skill forms (onboarding + post-onboarding editor).
 *
 * REQ-012 §7.2.4: Conversion utilities between API Skill
 * entities, form values, and request bodies.
 */

import type { SkillFormData } from "@/components/onboarding/steps/skills-form";
import type { Proficiency, Skill, SkillType } from "@/types/persona";

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
