/**
 * @fileoverview SearchProfile and SearchBucket types matching
 * backend/app/schemas/search_profile.py.
 *
 * Layer: type-definitions
 * Feature: jobs
 *
 * REQ-034 @4.2, @4.5: AI-generated job search criteria split into
 * fit (current-role) and stretch (growth-target) buckets.
 *
 * Coordinates with:
 * - (no upstream type imports)
 *
 * Called by / Used by:
 * - lib/api/search-profiles.ts: API client functions
 * - components/onboarding/steps/search-criteria-step.tsx: onboarding step
 * - components/settings/job-search-section.tsx: settings card section
 */

// ---------------------------------------------------------------------------
// Bucket shape (JSONB stored in fit_searches / stretch_searches)
// ---------------------------------------------------------------------------

/**
 * A single search criterion bucket -- fit or stretch.
 *
 * Backend: SearchBucketSchema (search_profile.py). Each item in
 * fit_searches or stretch_searches follows this shape.
 */
export interface SearchBucket {
	label: string;
	keywords: string[];
	titles: string[];
	remoteok_tags: string[];
	location: string | null;
}

// ---------------------------------------------------------------------------
// Full profile (GET / POST generate response)
// ---------------------------------------------------------------------------

/**
 * Full SearchProfile as returned by the API.
 *
 * Backend: SearchProfileRead (search_profile.py).
 */
export interface SearchProfile {
	id: string;
	persona_id: string;
	fit_searches: SearchBucket[];
	stretch_searches: SearchBucket[];
	persona_fingerprint: string;
	is_stale: boolean;
	generated_at: string | null;
	approved_at: string | null;
	created_at: string;
	updated_at: string;
}

// ---------------------------------------------------------------------------
// User-facing update (PATCH request body)
// ---------------------------------------------------------------------------

/**
 * Partial update payload for user-driven bucket edits and approval.
 *
 * Backend: SearchProfileApiUpdate (search_profile.py). Only user-settable
 * fields -- internal fields (is_stale, persona_fingerprint, generated_at)
 * are excluded to prevent client manipulation.
 */
export interface SearchProfileUpdate {
	fit_searches?: SearchBucket[];
	stretch_searches?: SearchBucket[];
	approved_at?: string | null;
}
