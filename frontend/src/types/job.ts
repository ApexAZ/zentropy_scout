/**
 * Job domain types matching backend/app/schemas/job_posting.py
 * and backend/app/services/ scoring dataclasses.
 *
 * REQ-001: Job posting analysis.
 * REQ-003 §7: Ghost detection signals.
 * REQ-005 §4.2: Database schema (JobPosting, ExtractedSkill).
 * REQ-008 §4–8: Scoring components (Fit, Stretch, Explanation).
 * REQ-012 §8: Job dashboard & scoring display.
 * REQ-015 §8: Shared job pool — PersonaJobResponse wraps JobPostingResponse.
 */

import type { SkillType, WorkModel } from "./persona";

// ---------------------------------------------------------------------------
// Enum union types — match backend CHECK constraints
// ---------------------------------------------------------------------------

/** Backend: JobPosting.seniority_level CHECK constraint. */
export type SeniorityLevel = "Entry" | "Mid" | "Senior" | "Lead" | "Executive";

/** Backend: PersonaJob.status CHECK constraint. */
export type JobPostingStatus =
	| "Discovered"
	| "Dismissed"
	| "Applied"
	| "Expired";

/** Backend: PersonaJob.discovery_method CHECK constraint. */
export type DiscoveryMethod = "scouter" | "manual" | "pool";

/** REQ-012 §8.4: Fit score tier labels (descending quality). */
export type FitScoreTier = "High" | "Medium" | "Low" | "Poor";

/** REQ-012 §8.4: Stretch score tier labels (descending growth). */
export type StretchScoreTier =
	| "High Growth"
	| "Moderate Growth"
	| "Lateral"
	| "Low Growth";

/** REQ-012 §8.6: Ghost score tier labels (ascending risk). */
export type GhostScoreTier = "Fresh" | "Moderate" | "Elevated" | "High Risk";

/** REQ-008 §4.1: Fit score component keys. */
export type FitScoreComponentKey =
	| "hard_skills"
	| "soft_skills"
	| "experience_level"
	| "role_title"
	| "location_logistics";

/** REQ-008 §5.1: Stretch score component keys. */
export type StretchScoreComponentKey =
	| "target_role"
	| "target_skills"
	| "growth_trajectory";

// ---------------------------------------------------------------------------
// Enum value arrays — for form dropdowns and display
// ---------------------------------------------------------------------------

export const SENIORITY_LEVELS: readonly SeniorityLevel[] = [
	"Entry",
	"Mid",
	"Senior",
	"Lead",
	"Executive",
] as const;

export const JOB_POSTING_STATUSES: readonly JobPostingStatus[] = [
	"Discovered",
	"Dismissed",
	"Applied",
	"Expired",
] as const;

export const FIT_SCORE_TIERS: readonly FitScoreTier[] = [
	"High",
	"Medium",
	"Low",
	"Poor",
] as const;

export const STRETCH_SCORE_TIERS: readonly StretchScoreTier[] = [
	"High Growth",
	"Moderate Growth",
	"Lateral",
	"Low Growth",
] as const;

export const GHOST_SCORE_TIERS: readonly GhostScoreTier[] = [
	"Fresh",
	"Moderate",
	"Elevated",
	"High Risk",
] as const;

export const FIT_SCORE_COMPONENT_KEYS: readonly FitScoreComponentKey[] = [
	"hard_skills",
	"soft_skills",
	"experience_level",
	"role_title",
	"location_logistics",
] as const;

export const STRETCH_SCORE_COMPONENT_KEYS: readonly StretchScoreComponentKey[] =
	["target_role", "target_skills", "growth_trajectory"] as const;

// ---------------------------------------------------------------------------
// Sub-entity interfaces — JSONB shapes and Tier 2 models
// ---------------------------------------------------------------------------

/**
 * A non-negotiable filter that a job posting failed.
 *
 * Backend: Stored in PersonaJob.failed_non_negotiables JSONB array.
 */
export interface FailedNonNegotiable {
	filter: string;
	job_value: string | number | null;
	persona_value: string | number | null;
}

/**
 * Skill extracted from a job posting description.
 *
 * Backend: ExtractedSkill model (job_posting.py). Tier 2 — references JobPosting.
 */
export interface ExtractedSkill {
	id: string;
	job_posting_id: string;
	skill_name: string;
	skill_type: SkillType;
	is_required: boolean;
	/** Years of experience requested. Null if not specified. */
	years_requested: number | null;
}

// ---------------------------------------------------------------------------
// Scoring interfaces — match backend service dataclasses
// ---------------------------------------------------------------------------

/**
 * Fit score aggregation result.
 *
 * Backend: FitScoreResult dataclass (fit_score.py). REQ-008 §4.7.
 * Components: hard_skills (40%), soft_skills (15%), experience_level (25%),
 * role_title (10%), location_logistics (10%).
 */
export interface FitScoreResult {
	/** Final fit score (0–100). */
	total: number;
	/** Individual component scores (0–100 each). */
	components: Record<FitScoreComponentKey, number>;
	/** Component weights (sum to 1.0). */
	weights: Record<FitScoreComponentKey, number>;
}

/**
 * Stretch score aggregation result.
 *
 * Backend: StretchScoreResult dataclass (stretch_score.py). REQ-008 §5.5.
 * Components: target_role (50%), target_skills (40%), growth_trajectory (10%).
 */
export interface StretchScoreResult {
	/** Final stretch score (0–100). */
	total: number;
	/** Individual component scores (0–100 each). */
	components: Record<StretchScoreComponentKey, number>;
	/** Component weights (sum to 1.0). */
	weights: Record<StretchScoreComponentKey, number>;
}

/**
 * Human-readable explanation of job-persona match scores.
 *
 * Backend: ScoreExplanation dataclass (score_explanation.py). REQ-008 §8.1.
 */
export interface ScoreExplanation {
	/** 2–3 sentence overview of match quality. */
	summary: string;
	/** What matches well between persona and job. */
	strengths: string[];
	/** Where the user is underqualified. */
	gaps: string[];
	/** Growth potential and career development value. */
	stretch_opportunities: string[];
	/** Concerns (undisclosed salary, ghost risk, overqualified). */
	warnings: string[];
}

/**
 * Composite JSONB stored in PersonaJob.score_details.
 *
 * Backend: Assembled by save_scores_node in strategist_graph.py.
 * REQ-012 Appendix A.3. Null when non-negotiables fail.
 */
export interface ScoreDetails {
	fit: FitScoreResult;
	stretch: StretchScoreResult;
	explanation: ScoreExplanation;
}

/**
 * Ghost detection signals for a job posting.
 *
 * Backend: GhostSignals dataclass (ghost_detection.py). REQ-003 §7.5.
 * Stored in JobPosting.ghost_signals JSONB column.
 */
export interface GhostSignals {
	days_open: number;
	days_open_score: number;
	repost_count: number;
	repost_score: number;
	/** LLM-assessed description vagueness (0–100). */
	vagueness_score: number;
	/** Field names missing from posting (e.g., "salary", "deadline"). */
	missing_fields: string[];
	missing_fields_score: number;
	requirement_mismatch: boolean;
	requirement_mismatch_score: number;
	/** ISO 8601 datetime when ghost score was calculated. */
	calculated_at: string;
	/** Final weighted ghost score (0–100). */
	ghost_score: number;
}

// ---------------------------------------------------------------------------
// JobPostingResponse — shared pool data (Tier 0)
// ---------------------------------------------------------------------------

/**
 * Shared job posting data returned by the API.
 *
 * Backend: JobPostingResponse schema (schemas/job_posting.py).
 * REQ-015 §8.3: Excludes also_found_on and raw_text (privacy).
 * Never returned directly to users — always nested in PersonaJobResponse.
 */
export interface JobPostingResponse {
	id: string;
	source_id: string | null;
	external_id: string | null;

	// Job details
	job_title: string;
	company_name: string;
	company_url: string | null;
	source_url: string | null;
	apply_url: string | null;
	location: string | null;
	work_model: WorkModel | null;
	seniority_level: SeniorityLevel | null;

	// Compensation
	salary_min: number | null;
	salary_max: number | null;
	salary_currency: string | null;

	// Description content
	description: string;
	culture_text: string | null;
	requirements: string | null;

	// Experience requirements
	years_experience_min: number | null;
	years_experience_max: number | null;

	// Dates
	/** ISO date string (YYYY-MM-DD). */
	posted_date: string | null;
	/** ISO date string (YYYY-MM-DD). */
	application_deadline: string | null;
	/** ISO date string (YYYY-MM-DD). */
	first_seen_date: string;

	// Verification timestamps
	/** ISO 8601 datetime. */
	last_verified_at: string | null;
	/** ISO 8601 datetime. Set when job expires. */
	expired_at: string | null;

	// Ghost detection
	ghost_signals: GhostSignals | null;
	/** 0–100 integer. Default 0. */
	ghost_score: number;

	// Deduplication & repost tracking
	/** SHA-256 hash of description for deduplication. */
	description_hash: string;
	repost_count: number;
	previous_posting_ids: string[] | null;

	// Active status
	/** False when job has expired or been removed. */
	is_active: boolean;
}

// ---------------------------------------------------------------------------
// PersonaJobResponse — per-user job relationship (Tier 2)
// ---------------------------------------------------------------------------

/**
 * Per-user job relationship wrapping shared pool data.
 *
 * Backend: PersonaJobResponse schema (schemas/job_posting.py).
 * REQ-015 §8: All API job endpoints return this shape.
 * Per-user fields (status, scores, favorites) at top level.
 * Shared data nested under `job`.
 */
export interface PersonaJobResponse {
	id: string;
	/** Nested shared job posting data. */
	job: JobPostingResponse;

	// Per-user state
	status: JobPostingStatus;
	is_favorite: boolean;
	/** How this job was discovered for this user. */
	discovery_method: DiscoveryMethod;
	/** ISO 8601 datetime — when this user first saw this job. */
	discovered_at: string;

	// Scoring (per-user)
	/** 0–100 integer. Null when not yet scored or non-negotiables fail. */
	fit_score: number | null;
	/** 0–100 integer. Null when not yet scored or non-negotiables fail. */
	stretch_score: number | null;
	/** Component breakdown. Null when non-negotiables fail. */
	score_details: ScoreDetails | null;
	/** Filters that this posting failed. Null when all pass. */
	failed_non_negotiables: FailedNonNegotiable[] | null;

	// Timestamps
	/** ISO 8601 datetime. Null when not yet scored. */
	scored_at: string | null;
	/** ISO 8601 datetime. Set when status transitions to Dismissed. */
	dismissed_at: string | null;
}
