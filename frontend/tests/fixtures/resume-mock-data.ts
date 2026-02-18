/**
 * Mock data factories for resume E2E tests.
 *
 * Re-exports persona sub-entity data from onboarding-mock-data.ts and adds
 * new fixtures for BaseResume, JobVariant, and related resume entities.
 * Returns API response envelopes (ApiResponse / ApiListResponse).
 */

import type { ApiListResponse, ApiResponse, PaginationMeta } from "@/types/api";
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
// JobVariant fixtures
// ---------------------------------------------------------------------------

const JOB_VARIANTS: JobVariant[] = [
	{
		id: JOB_VARIANT_IDS[0],
		base_resume_id: BASE_RESUME_IDS[0],
		job_posting_id: JOB_POSTING_IDS[0],
		summary: "Tailored summary for Frontend position at AlphaTech",
		job_bullet_order: {
			[WORK_HISTORY_IDS[0]]: [BULLET_IDS[0], BULLET_IDS[1]],
		},
		modifications_description: "Reworded summary for frontend focus",
		status: "Draft",
		snapshot_included_jobs: null,
		snapshot_job_bullet_selections: null,
		snapshot_included_education: null,
		snapshot_included_certifications: null,
		snapshot_skills_emphasis: null,
		agent_reasoning: null,
		guardrail_result: null,
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

/** Empty variants list. */
export function emptyJobVariantsList(): ApiListResponse<JobVariant> {
	return { data: [], meta: listMeta(0) };
}
