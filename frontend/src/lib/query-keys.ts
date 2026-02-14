/**
 * TanStack Query key factory.
 *
 * REQ-012 §4.2.1: Query key hierarchy for cache management and
 * SSE-driven invalidation. List keys are prefixes of detail keys
 * so that `invalidateQueries({ queryKey: ['jobs'] })` also clears
 * individual job entries.
 */

const PERSONAS = "personas" as const;

export const queryKeys = {
	// List keys
	personas: [PERSONAS] as const,
	jobs: ["jobs"] as const,
	applications: ["applications"] as const,
	resumes: ["resumes"] as const,
	variants: ["variants"] as const,
	coverLetters: ["cover-letters"] as const,
	changeFlags: ["change-flags"] as const,
	baseResumes: ["base-resumes"] as const,

	// Detail keys
	persona: (id: string) => [PERSONAS, id] as const,
	job: (id: string) => ["jobs", id] as const,
	application: (id: string) => ["applications", id] as const,

	// Sub-entity keys (nested under persona for prefix invalidation)
	workHistory: (personaId: string) =>
		[PERSONAS, personaId, "work-history"] as const,
	skills: (personaId: string) => [PERSONAS, personaId, "skills"] as const,
	education: (personaId: string) => [PERSONAS, personaId, "education"] as const,
	certifications: (personaId: string) =>
		[PERSONAS, personaId, "certifications"] as const,
	achievementStories: (personaId: string) =>
		[PERSONAS, personaId, "achievement-stories"] as const,
	voiceProfile: (personaId: string) =>
		[PERSONAS, personaId, "voice-profile"] as const,
	customNonNegotiables: (personaId: string) =>
		[PERSONAS, personaId, "custom-non-negotiables"] as const,

	// Sub-entity keys (nested under job for prefix invalidation)
	extractedSkills: (jobId: string) =>
		["jobs", jobId, "extracted-skills"] as const,
} as const;
