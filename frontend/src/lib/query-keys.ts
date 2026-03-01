/**
 * TanStack Query key factory.
 *
 * REQ-012 §4.2.1: Query key hierarchy for cache management and
 * SSE-driven invalidation. List keys are prefixes of detail keys
 * so that `invalidateQueries({ queryKey: ['jobs'] })` also clears
 * individual job entries.
 */

const PERSONAS = "personas" as const;
const JOBS = "jobs" as const;
const BASE_RESUMES = "base-resumes" as const;
const USAGE = "usage" as const;

export const queryKeys = {
	// List keys
	personas: [PERSONAS] as const,
	jobs: [JOBS] as const,
	applications: ["applications"] as const,
	resumes: ["resumes"] as const,
	variants: ["variants"] as const,
	coverLetters: ["cover-letters"] as const,
	changeFlags: ["change-flags"] as const,
	baseResumes: [BASE_RESUMES] as const,
	jobSources: ["job-sources"] as const,

	// Detail keys
	persona: (id: string) => [PERSONAS, id] as const,
	job: (id: string) => [JOBS, id] as const,
	application: (id: string) => ["applications", id] as const,
	baseResume: (id: string) => [BASE_RESUMES, id] as const,
	variant: (id: string) => ["variants", id] as const,
	coverLetter: (id: string) => ["cover-letters", id] as const,

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

	// Sub-entity keys (nested under persona for prefix invalidation — sources)
	sourcePreferences: (personaId: string) =>
		[PERSONAS, personaId, "source-preferences"] as const,

	// Sub-entity keys (nested under application for prefix invalidation)
	timelineEvents: (applicationId: string) =>
		["applications", applicationId, "timeline"] as const,

	// Sub-entity keys (nested under job for prefix invalidation)
	extractedSkills: (jobId: string) =>
		[JOBS, jobId, "extracted-skills"] as const,

	// Usage & billing keys (REQ-020 §9.1)
	balance: [USAGE, "balance"] as const,
	usageSummary: (start: string, end: string) =>
		[USAGE, "summary", start, end] as const,
	usageHistory: (page: number) => [USAGE, "history", page] as const,
	usageTransactions: (page: number) => [USAGE, "transactions", page] as const,
} as const;
