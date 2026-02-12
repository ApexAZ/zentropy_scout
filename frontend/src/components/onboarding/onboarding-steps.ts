/**
 * Onboarding wizard step definitions.
 *
 * REQ-012 §6.3: 12-step onboarding wizard.
 * Each step maps to a section of the persona data model.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Metadata for a single onboarding step. */
export interface OnboardingStepDef {
	/** Step number (1-based). */
	number: number;
	/** URL-safe key stored in persona.onboarding_step. */
	key: string;
	/** Human-readable step name shown in UI. */
	name: string;
	/** Whether the user can skip this step without completing it. */
	skippable: boolean;
}

// ---------------------------------------------------------------------------
// Step definitions
// ---------------------------------------------------------------------------

/** All 12 onboarding steps in order. */
export const ONBOARDING_STEPS: readonly OnboardingStepDef[] = [
	{ number: 1, key: "resume-upload", name: "Resume Upload", skippable: true },
	{ number: 2, key: "basic-info", name: "Basic Info", skippable: false },
	{ number: 3, key: "work-history", name: "Work History", skippable: false },
	{ number: 4, key: "education", name: "Education", skippable: true },
	{ number: 5, key: "skills", name: "Skills", skippable: false },
	{
		number: 6,
		key: "certifications",
		name: "Certifications",
		skippable: true,
	},
	{
		number: 7,
		key: "achievement-stories",
		name: "Achievement Stories",
		skippable: false,
	},
	{
		number: 8,
		key: "non-negotiables",
		name: "Non-Negotiables",
		skippable: false,
	},
	{
		number: 9,
		key: "growth-targets",
		name: "Growth Targets",
		skippable: false,
	},
	{
		number: 10,
		key: "voice-profile",
		name: "Voice Profile",
		skippable: false,
	},
	{ number: 11, key: "review", name: "Review", skippable: false },
	{
		number: 12,
		key: "base-resume",
		name: "Base Resume Setup",
		skippable: false,
	},
] as const;

/** Total number of onboarding steps. */
export const TOTAL_STEPS = ONBOARDING_STEPS.length;

// ---------------------------------------------------------------------------
// Lookups
// ---------------------------------------------------------------------------

/** Find a step definition by its 1-based number. */
export function getStepByNumber(n: number): OnboardingStepDef | undefined {
	return ONBOARDING_STEPS.find((s) => s.number === n);
}

/** Find a step definition by its URL-safe key. */
export function getStepByKey(key: string): OnboardingStepDef | undefined {
	return ONBOARDING_STEPS.find((s) => s.key === key);
}
