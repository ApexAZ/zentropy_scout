/**
 * Application & CoverLetter domain types matching
 * backend/app/models/application.py and backend/app/models/cover_letter.py.
 *
 * REQ-004: Application tracking pipeline.
 * REQ-005 §4.5: Database schema (Application, TimelineEvent).
 * REQ-005 §4.3: Database schema (CoverLetter, SubmittedCoverLetterPDF).
 * REQ-012 §11: Application tracking page.
 */

import type { WorkModel } from "./persona";

// ---------------------------------------------------------------------------
// Enum union types — match backend CHECK constraints
// ---------------------------------------------------------------------------

/** Backend: Application.status CHECK constraint. */
export type ApplicationStatus =
	| "Applied"
	| "Interviewing"
	| "Offer"
	| "Accepted"
	| "Rejected"
	| "Withdrawn";

/** Backend: Application.current_interview_stage CHECK constraint. */
export type InterviewStage = "Phone Screen" | "Onsite" | "Final Round";

/**
 * Backend: TimelineEvent.event_type CHECK constraint.
 *
 * Auto events: applied, status_changed, note_added, offer_received,
 *   offer_accepted, rejected, withdrawn.
 * Manual events: interview_scheduled, interview_completed,
 *   follow_up_sent, response_received, custom.
 */
export type TimelineEventType =
	| "applied"
	| "status_changed"
	| "note_added"
	| "interview_scheduled"
	| "interview_completed"
	| "offer_received"
	| "offer_accepted"
	| "rejected"
	| "withdrawn"
	| "follow_up_sent"
	| "response_received"
	| "custom";

/** Backend: CoverLetter.status CHECK constraint. */
export type CoverLetterStatus = "Draft" | "Approved" | "Archived";

/** Backend: ValidationIssue.severity from cover_letter_validation.py. */
export type ValidationSeverity = "error" | "warning";

// ---------------------------------------------------------------------------
// Enum value arrays — for form dropdowns and display
// ---------------------------------------------------------------------------

export const APPLICATION_STATUSES: readonly ApplicationStatus[] = [
	"Applied",
	"Interviewing",
	"Offer",
	"Accepted",
	"Rejected",
	"Withdrawn",
] as const;

export const INTERVIEW_STAGES: readonly InterviewStage[] = [
	"Phone Screen",
	"Onsite",
	"Final Round",
] as const;

export const TIMELINE_EVENT_TYPES: readonly TimelineEventType[] = [
	"applied",
	"status_changed",
	"note_added",
	"interview_scheduled",
	"interview_completed",
	"offer_received",
	"offer_accepted",
	"rejected",
	"withdrawn",
	"follow_up_sent",
	"response_received",
	"custom",
] as const;

export const COVER_LETTER_STATUSES: readonly CoverLetterStatus[] = [
	"Draft",
	"Approved",
	"Archived",
] as const;

export const VALIDATION_SEVERITIES: readonly ValidationSeverity[] = [
	"error",
	"warning",
] as const;

// ---------------------------------------------------------------------------
// JSONB sub-entity interfaces
// ---------------------------------------------------------------------------

/**
 * Frozen copy of job posting at application time.
 *
 * Backend: Application.job_snapshot JSONB column. Immutable after creation.
 * REQ-004 §4.1a: Job snapshot structure.
 */
export interface JobSnapshot {
	title: string;
	company_name: string;
	company_url: string | null;
	description: string;
	requirements: string | null;
	salary_min: number | null;
	salary_max: number | null;
	salary_currency: string | null;
	location: string | null;
	work_model: WorkModel | null;
	source_url: string | null;
	/** ISO 8601 datetime when snapshot was captured. */
	captured_at: string;
}

/**
 * Offer details captured when application status transitions to Offer.
 *
 * Backend: Application.offer_details JSONB column. All fields optional.
 * REQ-004 §4.3: Offer details structure.
 */
export interface OfferDetails {
	base_salary?: number;
	salary_currency?: string;
	bonus_percent?: number;
	equity_value?: number;
	equity_type?: "RSU" | "Options";
	equity_vesting_years?: number;
	/** ISO date string (YYYY-MM-DD). */
	start_date?: string;
	/** ISO date string (YYYY-MM-DD). Displayed as deadline countdown. */
	response_deadline?: string;
	other_benefits?: string;
	notes?: string;
}

/**
 * Rejection details captured when application status transitions to Rejected.
 *
 * Backend: Application.rejection_details JSONB column. All fields optional.
 * REQ-004 §4.4: Rejection details structure.
 */
export interface RejectionDetails {
	/** Stage at which rejection occurred. */
	stage?: string;
	reason?: string;
	feedback?: string;
	/** ISO 8601 datetime when rejection was communicated. */
	rejected_at?: string;
}

// ---------------------------------------------------------------------------
// Validation interfaces — match backend service dataclasses
// ---------------------------------------------------------------------------

/**
 * A single validation issue found in a cover letter draft.
 *
 * Backend: ValidationIssue dataclass (cover_letter_validation.py).
 * REQ-010 §5.4: Validation display.
 */
export interface ValidationIssue {
	/** "error" blocks presentation; "warning" is informational. */
	severity: ValidationSeverity;
	/** Machine-readable rule identifier (e.g., "length_min"). */
	rule: string;
	/** Human-readable description of the issue. */
	message: string;
}

/**
 * Result of validating a cover letter draft.
 *
 * Backend: CoverLetterValidation dataclass (cover_letter_validation.py).
 * REQ-010 §5.4: Validation display.
 */
export interface CoverLetterValidation {
	/** True if no errors (warnings allowed). */
	passed: boolean;
	/** Individual validation issues found. */
	issues: ValidationIssue[];
	/** Word count of the draft. */
	word_count: number;
}

// ---------------------------------------------------------------------------
// Main entity interfaces
// ---------------------------------------------------------------------------

/**
 * Job application record tracking status and materials.
 *
 * Backend: Application model (application.py). Tier 4 — references Persona,
 * JobPosting, JobVariant, CoverLetter, SubmittedPDFs.
 * REQ-004: Application tracking pipeline.
 * REQ-012 §11: Application tracking page.
 */
export interface Application {
	id: string;
	persona_id: string;
	job_posting_id: string;
	job_variant_id: string;
	cover_letter_id: string | null;
	submitted_resume_pdf_id: string | null;
	submitted_cover_letter_pdf_id: string | null;

	/** Frozen job posting copy at application time. */
	job_snapshot: JobSnapshot;

	// Status tracking
	status: ApplicationStatus;
	/** Sub-status when Interviewing. Null otherwise. */
	current_interview_stage: InterviewStage | null;

	// Outcome details
	offer_details: OfferDetails | null;
	rejection_details: RejectionDetails | null;
	/** Free-form notes, agent-populated or user-edited. */
	notes: string | null;

	// Pin control
	is_pinned: boolean;

	// Timestamps
	/** ISO 8601 datetime when user applied. */
	applied_at: string;
	/** ISO 8601 datetime of last status change. */
	status_updated_at: string;
	created_at: string;
	updated_at: string;
	/** ISO 8601 datetime. From SoftDeleteMixin. Null when not archived. */
	archived_at: string | null;
}

/**
 * Event in an application's history timeline.
 *
 * Backend: TimelineEvent model (application.py). Tier 5 — references Application.
 * Events are immutable (append-only, no edit/delete).
 * REQ-004 §5: Timeline events.
 */
export interface TimelineEvent {
	id: string;
	application_id: string;
	event_type: TimelineEventType;
	/** ISO 8601 datetime when the event occurred. */
	event_date: string;
	/** Event details. Null for auto-generated events with no extra info. */
	description: string | null;
	/** Interview stage associated with this event. Null for non-interview events. */
	interview_stage: InterviewStage | null;
	/** ISO 8601 datetime. Record creation time (no updated_at — events are immutable). */
	created_at: string;
}

/**
 * AI-generated cover letter for a job application.
 *
 * Backend: CoverLetter model (cover_letter.py). Tier 3 — references Persona,
 * JobPosting, Application (nullable).
 * REQ-002b: Cover letter generation.
 * REQ-010 §5/§7/§9: Cover letter validation and regeneration.
 */
export interface CoverLetter {
	id: string;
	persona_id: string;
	/** Null until application is created and linked. */
	application_id: string | null;
	job_posting_id: string;

	/** Achievement story UUIDs used in this letter. */
	achievement_stories_used: string[];

	// Content
	/** Editable while Draft status. */
	draft_text: string;
	/** Set on approval, immutable after. Null while Draft. */
	final_text: string | null;

	// Status
	status: CoverLetterStatus;

	/** Agent's story selection reasoning. Null if not yet generated. */
	agent_reasoning: string | null;

	/** Validation results from content checks. Null before validation runs. */
	validation_result: CoverLetterValidation | null;

	// Lifecycle timestamps
	/** ISO 8601 datetime. Set when status transitions to Approved. */
	approved_at: string | null;
	created_at: string;
	updated_at: string;
	/** ISO 8601 datetime. From SoftDeleteMixin. Null when not archived. */
	archived_at: string | null;
}

/**
 * Immutable PDF of cover letter submitted with a job application.
 *
 * Backend: SubmittedCoverLetterPDF model (cover_letter.py). Tier 4.
 * Binary content accessed via GET /submitted-cover-letter-pdfs/{id}/download.
 */
export interface SubmittedCoverLetterPDF {
	id: string;
	cover_letter_id: string;
	/** Null before application association. */
	application_id: string | null;
	file_name: string;
	/** ISO 8601 datetime. */
	generated_at: string;
}
