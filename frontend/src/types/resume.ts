/**
 * Resume domain types matching backend/app/models/resume.py and
 * backend/app/services/ guardrail structures.
 *
 * REQ-002: Resume generation and management.
 * REQ-005 §4.2: Database schema (ResumeFile, BaseResume, JobVariant, SubmittedResumePDF).
 * REQ-012 §9: Resume management page.
 */

// ---------------------------------------------------------------------------
// Enum union types — match backend CHECK constraints
// ---------------------------------------------------------------------------

/** Backend: ResumeFile.file_type CHECK constraint. */
export type ResumeFileType = "PDF" | "DOCX";

/** Backend: BaseResume.status CHECK constraint. */
export type BaseResumeStatus = "Active" | "Archived";

/** Backend: JobVariant.status CHECK constraint. */
export type JobVariantStatus = "Draft" | "Approved" | "Archived";

/** Backend: SubmittedResumePDF.resume_source_type CHECK constraint. */
export type ResumeSourceType = "Base" | "Variant";

/** REQ-012 §9.4: Guardrail violation severity levels. */
export type GuardrailSeverity = "error" | "warning";

// ---------------------------------------------------------------------------
// Enum value arrays — for form dropdowns and display
// ---------------------------------------------------------------------------

export const RESUME_FILE_TYPES: readonly ResumeFileType[] = [
	"PDF",
	"DOCX",
] as const;

export const BASE_RESUME_STATUSES: readonly BaseResumeStatus[] = [
	"Active",
	"Archived",
] as const;

export const JOB_VARIANT_STATUSES: readonly JobVariantStatus[] = [
	"Draft",
	"Approved",
	"Archived",
] as const;

export const RESUME_SOURCE_TYPES: readonly ResumeSourceType[] = [
	"Base",
	"Variant",
] as const;

export const GUARDRAIL_SEVERITIES: readonly GuardrailSeverity[] = [
	"error",
	"warning",
] as const;

// ---------------------------------------------------------------------------
// Sub-entity interfaces
// ---------------------------------------------------------------------------

/**
 * A single guardrail violation found during variant validation.
 *
 * Backend: Mirrors ValidationIssue pattern from cover_letter_validation.py.
 * REQ-012 §9.4: Modification guardrails display.
 */
export interface GuardrailViolation {
	/** "error" blocks approval; "warning" is informational. */
	severity: GuardrailSeverity;
	/** Machine-readable rule identifier (e.g., "new_bullets_added"). */
	rule: string;
	/** Human-readable description of the violation. */
	message: string;
}

/**
 * Result of guardrail validation on a job variant.
 *
 * Backend: Mirrors CoverLetterValidation pattern from cover_letter_validation.py.
 * REQ-012 §9.4: Guardrail violations must be resolved before approval.
 */
export interface GuardrailResult {
	/** True if no errors (warnings allowed). */
	passed: boolean;
	/** Individual violations found. */
	violations: GuardrailViolation[];
}

// ---------------------------------------------------------------------------
// Main entity interfaces
// ---------------------------------------------------------------------------

/**
 * Uploaded resume file (PDF or DOCX).
 *
 * Backend: ResumeFile model (resume.py). Tier 2 — references Persona.
 * Binary content accessed via dedicated download endpoints, not in API response.
 */
export interface ResumeFile {
	id: string;
	persona_id: string;
	file_name: string;
	file_type: ResumeFileType;
	file_size_bytes: number;
	/** ISO 8601 datetime. */
	uploaded_at: string;
	is_active: boolean;
}

/**
 * Master resume for a specific role type.
 *
 * Backend: BaseResume model (resume.py). Tier 2 — references Persona.
 * Content selections reference Persona sub-entities by UUID.
 * REQ-002 §4.2: Base resume creation wizard.
 * REQ-012 §9.2: Resume detail page.
 */
export interface BaseResume {
	id: string;
	persona_id: string;

	// Content metadata
	name: string;
	role_type: string;
	summary: string;

	// Content selections (UUID arrays referencing Persona sub-entities)
	included_jobs: string[];
	/** Null means show all education entries. */
	included_education: string[] | null;
	/** Null means show all certification entries. */
	included_certifications: string[] | null;
	/** Skill IDs to highlight. Null means no emphasis. */
	skills_emphasis: string[] | null;

	// JSONB mappings: job_id → bullet_ids
	/** Which bullets are selected per job. */
	job_bullet_selections: Record<string, string[]>;
	/** Display order of bullets per job. */
	job_bullet_order: Record<string, string[]>;

	// Render state
	/** ISO 8601 datetime when PDF was last rendered. Null if never rendered. */
	rendered_at: string | null;

	// Status & metadata
	is_primary: boolean;
	status: BaseResumeStatus;
	display_order: number;
	/** ISO 8601 datetime. Null when status is Active. */
	archived_at: string | null;

	// Timestamps
	created_at: string;
	updated_at: string;
}

/**
 * Job-tailored resume variant derived from a BaseResume.
 *
 * Backend: JobVariant model (resume.py). Tier 3 — references BaseResume, JobPosting.
 * Draft stores only modifications; inherited fields read from BaseResume.
 * On approval, all inherited fields are snapshotted and immutable.
 * REQ-002 §4.3: Job variant workflow.
 * REQ-012 §9.3: Variant review page.
 */
export interface JobVariant {
	id: string;
	base_resume_id: string;
	job_posting_id: string;

	// Variant-specific content
	summary: string;
	/** Bullet order overrides per job. */
	job_bullet_order: Record<string, string[]>;
	/** Plain-language description of what was modified. */
	modifications_description: string | null;

	// Status
	status: JobVariantStatus;

	// Approval snapshots (populated on approval, null while Draft)
	snapshot_included_jobs: string[] | null;
	snapshot_job_bullet_selections: Record<string, string[]> | null;
	snapshot_included_education: string[] | null;
	snapshot_included_certifications: string[] | null;
	snapshot_skills_emphasis: string[] | null;

	// Lifecycle
	/** ISO 8601 datetime. Set when status transitions to Approved. */
	approved_at: string | null;
	/** ISO 8601 datetime. Set when status transitions to Archived. */
	archived_at: string | null;

	// Timestamps (TimestampMixin)
	created_at: string;
	updated_at: string;
}

/**
 * Immutable PDF snapshot submitted with a job application.
 *
 * Backend: SubmittedResumePDF model (resume.py). Tier 4 — references Application.
 * Binary content accessed via GET /submitted-resume-pdfs/{id}/download.
 */
export interface SubmittedResumePDF {
	id: string;
	/** Null before application association. */
	application_id: string | null;
	/** Whether the source is a BaseResume or JobVariant. */
	resume_source_type: ResumeSourceType;
	/** UUID of the BaseResume or JobVariant this was generated from. */
	resume_source_id: string;
	file_name: string;
	/** ISO 8601 datetime. */
	generated_at: string;
}
