/**
 * TanStack Query key factory.
 *
 * REQ-012 §4.2.1: Query key hierarchy for cache management and
 * SSE-driven invalidation. List keys are prefixes of detail keys
 * so that `invalidateQueries({ queryKey: ['jobs'] })` also clears
 * individual job entries.
 */

export const queryKeys = {
	// List keys
	personas: ["personas"] as const,
	jobs: ["jobs"] as const,
	applications: ["applications"] as const,
	resumes: ["resumes"] as const,
	variants: ["variants"] as const,
	coverLetters: ["cover-letters"] as const,
	changeFlags: ["change-flags"] as const,

	// Detail keys
	persona: (id: string) => ["personas", id] as const,
	job: (id: string) => ["jobs", id] as const,
	application: (id: string) => ["applications", id] as const,
} as const;
