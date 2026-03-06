/**
 * Resume generation types matching backend/app/schemas/resume.py.
 *
 * REQ-026 §4.2: Generation options panel.
 * REQ-026 §4.3: Page limit control.
 * REQ-026 §4.6: Generation request/response.
 */

// ---------------------------------------------------------------------------
// Generation method
// ---------------------------------------------------------------------------

/** Backend: GenerationMethod literal type. */
export type GenerationMethod = "ai" | "template_fill";

// ---------------------------------------------------------------------------
// Section types
// ---------------------------------------------------------------------------

/** Section identifiers for the generation options panel (REQ-026 §4.2). */
export type ResumeSection =
	| "summary"
	| "experience"
	| "education"
	| "skills"
	| "certifications"
	| "volunteer";

/** Labels for display in the generation options panel. */
export const RESUME_SECTION_LABELS: Record<ResumeSection, string> = {
	summary: "Professional Summary",
	experience: "Work Experience",
	education: "Education",
	skills: "Skills",
	certifications: "Certifications",
	volunteer: "Volunteer Experience",
} as const;

/** Sections checked by default (REQ-026 §4.2). */
export const DEFAULT_INCLUDE_SECTIONS: readonly ResumeSection[] = [
	"summary",
	"experience",
	"education",
	"skills",
] as const;

/** All available sections. */
export const ALL_RESUME_SECTIONS: readonly ResumeSection[] = [
	"summary",
	"experience",
	"education",
	"skills",
	"certifications",
	"volunteer",
] as const;

// ---------------------------------------------------------------------------
// Emphasis types
// ---------------------------------------------------------------------------

/** Emphasis options for AI generation (REQ-026 §4.2). */
export type EmphasisOption =
	| "technical"
	| "leadership"
	| "balanced"
	| "industry-specific";

/** Labels for emphasis dropdown. */
export const EMPHASIS_LABELS: Record<EmphasisOption, string> = {
	technical: "Technical",
	leadership: "Leadership",
	balanced: "Balanced",
	"industry-specific": "Industry-specific",
} as const;

/** All emphasis options. */
export const ALL_EMPHASIS_OPTIONS: readonly EmphasisOption[] = [
	"technical",
	"leadership",
	"balanced",
	"industry-specific",
] as const;

// ---------------------------------------------------------------------------
// Page limit
// ---------------------------------------------------------------------------

/** Page limit options (REQ-026 §4.3). */
export const PAGE_LIMIT_OPTIONS = [1, 2, 3] as const;
export type PageLimit = (typeof PAGE_LIMIT_OPTIONS)[number];

// ---------------------------------------------------------------------------
// Composite types
// ---------------------------------------------------------------------------

/** Frontend generation options collected by the panel. */
export interface GenerationOptions {
	pageLimit: PageLimit;
	emphasis: EmphasisOption;
	includeSections: ResumeSection[];
}

/** Request body for POST /base-resumes/{id}/generate. */
export interface GenerateResumeRequest {
	method: GenerationMethod;
	page_limit?: number;
	emphasis?: string;
	include_sections?: string[];
	template_id?: string;
}

/** Response body from POST /base-resumes/{id}/generate. */
export interface GenerateResumeResponse {
	markdown_content: string;
	word_count: number;
	method: GenerationMethod;
	model_used: string | null;
	generation_cost_cents: number;
}
