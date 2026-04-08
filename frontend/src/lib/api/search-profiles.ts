/**
 * @fileoverview SearchProfile API client functions for job search criteria.
 *
 * Layer: lib/utility
 * Feature: jobs
 *
 * REQ-034 @4.5: Typed functions for fetching, generating, and updating
 * AI-generated search profiles (fit/stretch buckets).
 *
 * Coordinates with:
 * - lib/api-client.ts: shared HTTP wrappers (apiGet, apiPost, apiPatch)
 * - types/search-profile.ts: SearchProfile, SearchProfileUpdate type definitions
 * - types/api.ts: response envelope types (ApiResponse)
 *
 * Called by / Used by:
 * - components/onboarding/steps/search-criteria-step.tsx: onboarding step
 * - components/settings/job-search-section.tsx: settings card section
 */

import type { ApiResponse } from "@/types/api";
import type {
	SearchProfile,
	SearchProfileUpdate,
} from "@/types/search-profile";
import { apiGet, apiPatch, apiPost } from "@/lib/api-client";

// =============================================================================
// GET /search-profiles/{personaId} -- fetch current profile
// =============================================================================

/** Fetch the SearchProfile for a persona. */
export async function getSearchProfile(
	personaId: string,
): Promise<ApiResponse<SearchProfile>> {
	return apiGet(`/search-profiles/${encodeURIComponent(personaId)}`);
}

// =============================================================================
// POST /search-profiles/{personaId}/generate -- AI generation
// =============================================================================

/** Trigger AI generation (or regeneration) of a SearchProfile. */
export async function generateSearchProfile(
	personaId: string,
): Promise<ApiResponse<SearchProfile>> {
	return apiPost(`/search-profiles/${encodeURIComponent(personaId)}/generate`);
}

// =============================================================================
// PATCH /search-profiles/{personaId} -- user edits / approval
// =============================================================================

/** Partially update a SearchProfile (bucket edits or approval). */
export async function updateSearchProfile(
	personaId: string,
	data: SearchProfileUpdate,
): Promise<ApiResponse<SearchProfile>> {
	return apiPatch(`/search-profiles/${encodeURIComponent(personaId)}`, data);
}
