/**
 * TypeScript types for the two-step job ingest flow.
 *
 * REQ-006 §5.6: Chrome extension / manual job posting ingest.
 * Mirrors backend schemas in backend/app/schemas/ingest.py.
 */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Known job-board source names for the ingest source dropdown. */
export const INGEST_SOURCE_NAMES = [
	"LinkedIn",
	"Indeed",
	"Glassdoor",
	"Adzuna",
	"The Muse",
	"RemoteOK",
	"USAJobs",
	"Other",
] as const;

/** Union type of valid ingest source names. */
export type IngestSourceName = (typeof INGEST_SOURCE_NAMES)[number];

// ---------------------------------------------------------------------------
// Request Types
// ---------------------------------------------------------------------------

/** Request body for POST /job-postings/ingest. */
export interface IngestJobPostingRequest {
	raw_text: string;
	source_url?: string;
	source_name: string;
}

/** Request body for POST /job-postings/ingest/confirm. */
export interface IngestConfirmRequest {
	confirmation_token: string;
	modifications?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Response Types
// ---------------------------------------------------------------------------

/** A skill extracted from job posting text. */
export interface ExtractedSkillPreview {
	skill_name: string;
	skill_type: string;
	is_required: boolean;
	years_requested: number | null;
}

/** Preview of extracted job posting data. */
export interface IngestPreview {
	job_title: string | null;
	company_name: string | null;
	location: string | null;
	salary_min: number | null;
	salary_max: number | null;
	salary_currency: string | null;
	employment_type: string | null;
	extracted_skills: ExtractedSkillPreview[];
	culture_text: string | null;
	description_snippet: string | null;
}

/** Response for POST /job-postings/ingest. */
export interface IngestJobPostingResponse {
	preview: IngestPreview;
	confirmation_token: string;
	expires_at: string;
}

/** Response for POST /job-postings/ingest/confirm. */
export interface IngestConfirmResponse {
	id: string;
	job_title: string | null;
	company_name: string | null;
	status: string;
}
