/**
 * Mock data factories for persona update E2E tests.
 *
 * Re-exports onboarding persona/sub-entity data with onboarding_complete=true
 * and adds new fixtures for PersonaChangeFlags and BaseResumes.
 */

import type { ApiListResponse, ApiResponse, PaginationMeta } from "@/types/api";
import type {
	ChangeFlagResolution,
	Persona,
	PersonaChangeFlag,
} from "@/types/persona";
import type { BaseResume } from "@/types/resume";

import {
	achievementStoriesList,
	certificationsList,
	customNonNegotiablesList,
	educationList,
	emptyChangeFlagsList,
	emptyChatMessages,
	patchPersonaResponse,
	PERSONA_ID,
	personaList,
	personaResponse,
	postSkillResponse,
	skillsList,
	voiceProfileResponse,
	workHistoryList,
	SKILL_IDS,
	WORK_HISTORY_IDS,
	EDUCATION_ID,
	CERT_ID,
	STORY_IDS,
	BASE_RESUME_ID,
} from "./onboarding-mock-data";

// ---------------------------------------------------------------------------
// Re-exports (used by mock controller and spec file)
// ---------------------------------------------------------------------------

export {
	PERSONA_ID,
	SKILL_IDS,
	WORK_HISTORY_IDS,
	EDUCATION_ID,
	CERT_ID,
	STORY_IDS,
	BASE_RESUME_ID,
	achievementStoriesList,
	certificationsList,
	customNonNegotiablesList,
	educationList,
	emptyChangeFlagsList,
	emptyChatMessages,
	patchPersonaResponse,
	personaList,
	personaResponse,
	postSkillResponse,
	skillsList,
	voiceProfileResponse,
	workHistoryList,
};

// ---------------------------------------------------------------------------
// Consistent IDs
// ---------------------------------------------------------------------------

export const CHANGE_FLAG_IDS = ["cf-001", "cf-002", "cf-003"] as const;
export const BASE_RESUME_IDS = ["br-001", "br-002"] as const;

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

/** Persona list with onboarding_complete=true. */
export function onboardedPersonaList(
	overrides?: Partial<Persona>,
): ApiListResponse<Persona> {
	return personaList({
		onboarding_complete: true,
		onboarding_step: "base-resume",
		...overrides,
	});
}

// ---------------------------------------------------------------------------
// PersonaChangeFlag fixtures
// ---------------------------------------------------------------------------

const CHANGE_FLAGS: PersonaChangeFlag[] = [
	{
		id: CHANGE_FLAG_IDS[0],
		persona_id: PERSONA_ID,
		change_type: "skill_added",
		item_id: "skill-new-001",
		item_description: "Kubernetes",
		status: "Pending",
		resolution: null,
		resolved_at: null,
		created_at: NOW,
	},
	{
		id: CHANGE_FLAG_IDS[1],
		persona_id: PERSONA_ID,
		change_type: "job_added",
		item_id: "wh-new-001",
		item_description: "Senior Engineer at TechCorp",
		status: "Pending",
		resolution: null,
		resolved_at: null,
		created_at: NOW,
	},
	{
		id: CHANGE_FLAG_IDS[2],
		persona_id: PERSONA_ID,
		change_type: "certification_added",
		item_id: "cert-new-001",
		item_description: "AWS Solutions Architect",
		status: "Pending",
		resolution: null,
		resolved_at: null,
		created_at: NOW,
	},
];

/** 3 pending change flags. */
export function changeFlagsList(): ApiListResponse<PersonaChangeFlag> {
	return { data: [...CHANGE_FLAGS], meta: listMeta(3) };
}

/** Resolved change flag response. */
export function resolvedChangeFlagResponse(
	flagId: string,
	resolution: ChangeFlagResolution,
): ApiResponse<PersonaChangeFlag> {
	const flag = CHANGE_FLAGS.find((f) => f.id === flagId) ?? CHANGE_FLAGS[0];
	return {
		data: {
			...flag,
			status: "Resolved",
			resolution,
			resolved_at: NOW,
		},
	};
}

// ---------------------------------------------------------------------------
// BaseResume fixtures
// ---------------------------------------------------------------------------

const BASE_RESUMES: BaseResume[] = [
	{
		id: BASE_RESUME_IDS[0],
		persona_id: PERSONA_ID,
		name: "General Resume",
		role_type: "Software Engineer",
		summary: "Full-stack engineer with 8 years experience",
		included_jobs: [...WORK_HISTORY_IDS],
		included_education: [EDUCATION_ID],
		included_certifications: [CERT_ID],
		skills_emphasis: [...SKILL_IDS],
		job_bullet_selections: {},
		job_bullet_order: {},
		rendered_at: null,
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
		name: "Backend Focus",
		role_type: "Backend Engineer",
		summary: "Backend specialist with Python and distributed systems",
		included_jobs: [...WORK_HISTORY_IDS],
		included_education: [EDUCATION_ID],
		included_certifications: null,
		skills_emphasis: [SKILL_IDS[1]],
		job_bullet_selections: {},
		job_bullet_order: {},
		rendered_at: null,
		is_primary: false,
		status: "Active",
		display_order: 1,
		archived_at: null,
		created_at: NOW,
		updated_at: NOW,
	},
];

/** 2 active base resumes. */
export function baseResumesList(): ApiListResponse<BaseResume> {
	return { data: [...BASE_RESUMES], meta: listMeta(2) };
}
