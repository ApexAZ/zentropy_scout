/**
 * Mock data factories for resume E2E tests.
 *
 * Re-exports persona sub-entity data from onboarding-mock-data.ts and adds
 * new fixtures for BaseResume, JobVariant, and related resume entities.
 * Returns API response envelopes (ApiResponse / ApiListResponse).
 */

import type { ApiListResponse, ApiResponse, PaginationMeta } from "@/types/api";
import type { JobPosting } from "@/types/job";
import type { Persona } from "@/types/persona";
import type { BaseResume, JobVariant } from "@/types/resume";

import {
	BULLET_IDS,
	CERT_ID,
	certificationsList,
	customNonNegotiablesList,
	educationList,
	emptyChangeFlagsList,
	emptyChatMessages,
	EDUCATION_ID,
	patchPersonaResponse,
	PERSONA_ID,
	personaList,
	SKILL_IDS,
	skillsList,
	WORK_HISTORY_IDS,
	workHistoryList,
} from "./onboarding-mock-data";

// ---------------------------------------------------------------------------
// Re-exports (used by mock controller and spec file)
// ---------------------------------------------------------------------------

export {
	BULLET_IDS,
	CERT_ID,
	certificationsList,
	customNonNegotiablesList,
	educationList,
	emptyChangeFlagsList,
	emptyChatMessages,
	EDUCATION_ID,
	patchPersonaResponse,
	PERSONA_ID,
	personaList,
	SKILL_IDS,
	skillsList,
	WORK_HISTORY_IDS,
	workHistoryList,
};

// ---------------------------------------------------------------------------
// Consistent IDs
// ---------------------------------------------------------------------------

export const BASE_RESUME_IDS = [
	"br-e2e-001",
	"br-e2e-002",
	"br-e2e-003",
] as const;
export const JOB_VARIANT_IDS = ["jv-e2e-001", "jv-e2e-002"] as const;
export const JOB_POSTING_IDS = ["jp-e2e-001", "jp-e2e-002"] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const NOW = "2026-02-15T12:00:00Z";

function listMeta(total: number): PaginationMeta {
	return { total, page: 1, per_page: 100, total_pages: 1 };
}

// ---------------------------------------------------------------------------
// Persona factories (onboarded overrides)
// ---------------------------------------------------------------------------

/** Persona list with onboarding_complete=true — bypasses persona gate. */
export function onboardedPersonaList(): ApiListResponse<Persona> {
	return personaList({
		onboarding_complete: true,
		onboarding_step: "base-resume",
	});
}

// ---------------------------------------------------------------------------
// BaseResume fixtures
// ---------------------------------------------------------------------------

const BASE_RESUMES: BaseResume[] = [
	{
		id: BASE_RESUME_IDS[0],
		persona_id: PERSONA_ID,
		name: "Scrum Master",
		role_type: "Scrum Master / Agile Coach",
		summary: "Experienced Scrum Master with strong facilitation skills",
		included_jobs: [...WORK_HISTORY_IDS],
		included_education: [EDUCATION_ID],
		included_certifications: [CERT_ID],
		skills_emphasis: [...SKILL_IDS],
		job_bullet_selections: {
			[WORK_HISTORY_IDS[0]]: [BULLET_IDS[0], BULLET_IDS[1]],
			[WORK_HISTORY_IDS[1]]: [BULLET_IDS[2], BULLET_IDS[3]],
		},
		job_bullet_order: {
			[WORK_HISTORY_IDS[0]]: [BULLET_IDS[0], BULLET_IDS[1]],
			[WORK_HISTORY_IDS[1]]: [BULLET_IDS[2], BULLET_IDS[3]],
		},
		rendered_at: NOW,
		is_primary: true,
		status: "Active",
		display_order: 0,
		archived_at: null,
		created_at: NOW,
		updated_at: NOW,
	},
	{
		id: BASE_RESUME_IDS[1],
		persona_id: PERSONA_ID,
		name: "Product Owner",
		role_type: "Product Owner / Product Manager",
		summary: "Results-driven product leader with technical background",
		included_jobs: [WORK_HISTORY_IDS[0]],
		included_education: [EDUCATION_ID],
		included_certifications: null,
		skills_emphasis: [SKILL_IDS[2]],
		job_bullet_selections: {
			[WORK_HISTORY_IDS[0]]: [BULLET_IDS[0]],
		},
		job_bullet_order: {
			[WORK_HISTORY_IDS[0]]: [BULLET_IDS[0]],
		},
		rendered_at: null,
		is_primary: false,
		status: "Active",
		display_order: 1,
		archived_at: null,
		created_at: NOW,
		updated_at: NOW,
	},
	{
		id: BASE_RESUME_IDS[2],
		persona_id: PERSONA_ID,
		name: "Tech Lead (Archived)",
		role_type: "Technical Lead",
		summary: "Archived resume for tech lead positions",
		included_jobs: [...WORK_HISTORY_IDS],
		included_education: null,
		included_certifications: null,
		skills_emphasis: null,
		job_bullet_selections: {},
		job_bullet_order: {},
		rendered_at: null,
		is_primary: false,
		status: "Archived",
		display_order: 2,
		archived_at: NOW,
		created_at: NOW,
		updated_at: NOW,
	},
];

/** 2 active + 1 archived base resumes. */
export function allBaseResumesList(): ApiListResponse<BaseResume> {
	return { data: [...BASE_RESUMES], meta: listMeta(3) };
}

/** 2 active base resumes (default: no archived). */
export function activeBaseResumesList(): ApiListResponse<BaseResume> {
	const active = BASE_RESUMES.filter((r) => r.status === "Active");
	return { data: [...active], meta: listMeta(active.length) };
}

/** Empty resume list for empty-state testing. */
export function emptyBaseResumesList(): ApiListResponse<BaseResume> {
	return { data: [], meta: listMeta(0) };
}

/** Single new resume response (for POST). */
export function postBaseResumeResponse(
	overrides?: Partial<BaseResume>,
): ApiResponse<BaseResume> {
	return {
		data: {
			id: "br-e2e-new-001",
			persona_id: PERSONA_ID,
			name: "New Resume",
			role_type: "Software Engineer",
			summary: "A new resume",
			included_jobs: [],
			included_education: [],
			included_certifications: [],
			skills_emphasis: [],
			job_bullet_selections: {},
			job_bullet_order: {},
			rendered_at: null,
			is_primary: false,
			status: "Active",
			display_order: 0,
			archived_at: null,
			created_at: NOW,
			updated_at: NOW,
			...overrides,
		},
	};
}

// ---------------------------------------------------------------------------
// JobPosting fixtures (minimal — only fields VariantsList uses)
// ---------------------------------------------------------------------------

const BASE_JOB_POSTING: JobPosting = {
	id: JOB_POSTING_IDS[0],
	persona_id: PERSONA_ID,
	external_id: null,
	source_id: "linkedin",
	also_found_on: { sources: [] },
	job_title: "Frontend Engineer",
	company_name: "AlphaTech",
	company_url: null,
	source_url: null,
	apply_url: null,
	location: "Remote",
	work_model: "Remote",
	seniority_level: "Mid",
	salary_min: null,
	salary_max: null,
	salary_currency: null,
	description: "Frontend engineer position at AlphaTech.",
	culture_text: null,
	requirements: null,
	years_experience_min: null,
	years_experience_max: null,
	posted_date: null,
	application_deadline: null,
	first_seen_date: "2026-02-10",
	status: "Discovered",
	is_favorite: false,
	fit_score: null,
	stretch_score: null,
	score_details: null,
	failed_non_negotiables: null,
	ghost_score: 0,
	ghost_signals: null,
	description_hash: "hash-001",
	repost_count: 0,
	previous_posting_ids: null,
	last_verified_at: null,
	dismissed_at: null,
	expired_at: null,
	created_at: NOW,
	updated_at: NOW,
};

const JOB_POSTINGS: JobPosting[] = [
	BASE_JOB_POSTING,
	{
		...BASE_JOB_POSTING,
		id: JOB_POSTING_IDS[1],
		job_title: "Backend Engineer",
		company_name: "BetaWorks",
		description_hash: "hash-002",
	},
];

/** 2 job postings matching variant job_posting_ids. */
export function jobPostingsForVariantsList(): ApiListResponse<JobPosting> {
	return { data: [...JOB_POSTINGS], meta: listMeta(2) };
}

// ---------------------------------------------------------------------------
// JobVariant fixtures
// ---------------------------------------------------------------------------

const JOB_VARIANTS: JobVariant[] = [
	{
		id: JOB_VARIANT_IDS[0],
		base_resume_id: BASE_RESUME_IDS[0],
		job_posting_id: JOB_POSTING_IDS[0],
		summary: "Tailored summary for Frontend position at AlphaTech",
		job_bullet_order: {
			[WORK_HISTORY_IDS[0]]: [BULLET_IDS[1], BULLET_IDS[0]],
		},
		modifications_description: "Reworded summary for frontend focus",
		status: "Draft",
		snapshot_included_jobs: null,
		snapshot_job_bullet_selections: null,
		snapshot_included_education: null,
		snapshot_included_certifications: null,
		snapshot_skills_emphasis: null,
		agent_reasoning:
			"Reordered bullets to highlight mentoring before migration for frontend culture fit.",
		guardrail_result: { passed: true, violations: [] },
		approved_at: null,
		archived_at: null,
		created_at: NOW,
		updated_at: NOW,
	},
	{
		id: JOB_VARIANT_IDS[1],
		base_resume_id: BASE_RESUME_IDS[0],
		job_posting_id: JOB_POSTING_IDS[1],
		summary: "Approved variant for Backend position at BetaWorks",
		job_bullet_order: {
			[WORK_HISTORY_IDS[1]]: [BULLET_IDS[3], BULLET_IDS[2]],
		},
		modifications_description: "Reordered bullets for backend emphasis",
		status: "Approved",
		snapshot_included_jobs: [...WORK_HISTORY_IDS],
		snapshot_job_bullet_selections: {
			[WORK_HISTORY_IDS[0]]: [BULLET_IDS[0], BULLET_IDS[1]],
			[WORK_HISTORY_IDS[1]]: [BULLET_IDS[2], BULLET_IDS[3]],
		},
		snapshot_included_education: [EDUCATION_ID],
		snapshot_included_certifications: [CERT_ID],
		snapshot_skills_emphasis: [...SKILL_IDS],
		agent_reasoning: "Focused on backend experience",
		guardrail_result: { passed: true, violations: [] },
		approved_at: NOW,
		archived_at: null,
		created_at: NOW,
		updated_at: NOW,
	},
];

/** 2 job variants (1 Draft, 1 Approved) — both for base resume 1. */
export function jobVariantsList(): ApiListResponse<JobVariant> {
	return { data: [...JOB_VARIANTS], meta: listMeta(2) };
}

/** Single variant detail response. */
export function jobVariantDetail(
	variantId: string,
	overrides?: Partial<JobVariant>,
): ApiResponse<JobVariant> | null {
	const variant = JOB_VARIANTS.find((v) => v.id === variantId);
	if (!variant) return null;
	return { data: { ...variant, ...overrides } };
}

/** Single job posting detail response. */
export function jobPostingDetail(
	postingId: string,
): ApiResponse<JobPosting> | null {
	const posting = JOB_POSTINGS.find((p) => p.id === postingId);
	if (!posting) return null;
	return { data: posting };
}

/** Empty variants list. */
export function emptyJobVariantsList(): ApiListResponse<JobVariant> {
	return { data: [], meta: listMeta(0) };
}

// ---------------------------------------------------------------------------
// Guardrail test helpers
// ---------------------------------------------------------------------------

export const GUARDRAIL_ERROR = {
	passed: false,
	violations: [
		{
			severity: "error" as const,
			rule: "new_bullets_added",
			message: "Resume contains fabricated accomplishments not in persona.",
		},
	],
};

export const GUARDRAIL_WARNING = {
	passed: true,
	violations: [
		{
			severity: "warning" as const,
			rule: "skill_gap",
			message: "Missing 2 of 5 required skills listed in the job posting.",
		},
	],
};
