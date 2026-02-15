/**
 * Job source and user source preference types matching
 * backend/app/models/job_source.py.
 *
 * REQ-012 §12.2: Job source preferences.
 */

// ---------------------------------------------------------------------------
// Enum union types
// ---------------------------------------------------------------------------

/** Source type constraint from DB CHECK. */
export type SourceType = "API" | "Extension" | "Manual";

// ---------------------------------------------------------------------------
// Enum value arrays
// ---------------------------------------------------------------------------

export const SOURCE_TYPES: readonly SourceType[] = [
	"API",
	"Extension",
	"Manual",
] as const;

// ---------------------------------------------------------------------------
// Main entity interfaces
// ---------------------------------------------------------------------------

/**
 * A configured job board or extension source.
 *
 * Backend: JobSource model (job_source.py). Tier 0 — reference data.
 */
export interface JobSource {
	id: string;
	source_name: string;
	source_type: SourceType;
	description: string;
	api_endpoint: string | null;
	is_active: boolean;
	display_order: number;
}

/**
 * Per-persona preference for a job source (enable/disable, ordering).
 *
 * Backend: UserSourcePreference model (user_source_preference.py).
 */
export interface UserSourcePreference {
	id: string;
	persona_id: string;
	source_id: string;
	is_enabled: boolean;
	display_order: number | null;
}
