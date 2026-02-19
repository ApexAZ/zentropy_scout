/**
 * Mock data factories for ghostwriter review E2E tests.
 *
 * Re-exports persona sub-entity data from onboarding-mock-data.ts and
 * combines resume variant + cover letter fixtures for unified review testing.
 * Returns API response envelopes (ApiResponse / ApiListResponse).
 */

import type { ApiListResponse, ApiResponse, PaginationMeta } from "@/types/api";
import type { CoverLetter, CoverLetterValidation } from "@/types/application";
import type { JobPosting } from "@/types/job";
import type { Persona } from "@/types/persona";
import type { BaseResume, GuardrailResult, JobVariant } from "@/types/resume";

import {
	achievementStoriesList,
	BULLET_IDS,
	CERT_ID,
	emptyChangeFlagsList,
	emptyChatMessages,
	EDUCATION_ID,
	PERSONA_ID,
	personaList,
	SKILL_IDS,
	skillsList,
	STORY_IDS,
	voiceProfileResponse,
	WORK_HISTORY_IDS,
	workHistoryList,
} from "./onboarding-mock-data";

// ---------------------------------------------------------------------------
// Re-exports (used by mock controller and spec file)
// ---------------------------------------------------------------------------

export {
	achievementStoriesList,
	BULLET_IDS,
	CERT_ID,
	emptyChangeFlagsList,
	emptyChatMessages,
	EDUCATION_ID,
	PERSONA_ID,
	personaList,
	SKILL_IDS,
	skillsList,
	STORY_IDS,
	voiceProfileResponse,
	WORK_HISTORY_IDS,
	workHistoryList,
};

// ---------------------------------------------------------------------------
// Consistent IDs — JOB_POSTING_ID must be UUID (page validates with regex)
// ---------------------------------------------------------------------------

export const JOB_POSTING_ID = "00000000-0000-4000-a000-000000000001" as const;
export const VARIANT_ID = "jv-gw-e2e-001" as const;
export const COVER_LETTER_ID = "cl-gw-e2e-001" as const;
export const BASE_RESUME_ID = "br-gw-e2e-001" as const;

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
// Job Posting fixture
// ---------------------------------------------------------------------------

const JOB_POSTING: JobPosting = {
	id: JOB_POSTING_ID,
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
	description:
		"Frontend engineer position at AlphaTech building modern web applications.",
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
	description_hash: "hash-gw-001",
	repost_count: 0,
	previous_posting_ids: null,
	last_verified_at: null,
	dismissed_at: null,
	expired_at: null,
	created_at: NOW,
	updated_at: NOW,
};

/** Job posting detail. */
export function jobPostingDetail(): ApiResponse<JobPosting> {
	return { data: JOB_POSTING };
}

// ---------------------------------------------------------------------------
// Base Resume fixture
// ---------------------------------------------------------------------------

const BASE_RESUME: BaseResume = {
	id: BASE_RESUME_ID,
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
};

/** Base resume detail. */
export function baseResumeDetail(): ApiResponse<BaseResume> {
	return { data: BASE_RESUME };
}

// ---------------------------------------------------------------------------
// Job Variant fixtures
// ---------------------------------------------------------------------------

export const VARIANT_REASONING =
	"Reordered bullets to highlight mentoring before migration for frontend culture fit. Tailored summary to emphasize web application experience.";

const BASE_VARIANT: JobVariant = {
	id: VARIANT_ID,
	base_resume_id: BASE_RESUME_ID,
	job_posting_id: JOB_POSTING_ID,
	summary:
		"Experienced Scrum Master with strong facilitation skills and modern web expertise",
	job_bullet_order: {
		[WORK_HISTORY_IDS[0]]: [BULLET_IDS[1], BULLET_IDS[0]],
		[WORK_HISTORY_IDS[1]]: [BULLET_IDS[2], BULLET_IDS[3]],
	},
	modifications_description: "Reordered bullets for frontend focus",
	status: "Draft",
	snapshot_included_jobs: null,
	snapshot_job_bullet_selections: null,
	snapshot_included_education: null,
	snapshot_included_certifications: null,
	snapshot_skills_emphasis: null,
	agent_reasoning: VARIANT_REASONING,
	guardrail_result: { passed: true, violations: [] },
	approved_at: null,
	archived_at: null,
	created_at: NOW,
	updated_at: NOW,
};

/** Draft variant detail (default). */
export function variantDetail(
	overrides?: Partial<JobVariant>,
): ApiResponse<JobVariant> {
	return { data: { ...BASE_VARIANT, ...overrides } };
}

/** Variant list with one draft for the job posting. */
export function variantsList(
	overrides?: Partial<JobVariant>,
): ApiListResponse<JobVariant> {
	return {
		data: [{ ...BASE_VARIANT, ...overrides }],
		meta: listMeta(1),
	};
}

/** Empty variant list (no materials). */
export function emptyVariantsList(): ApiListResponse<JobVariant> {
	return { data: [], meta: listMeta(0) };
}

// ---------------------------------------------------------------------------
// Cover Letter fixtures
// ---------------------------------------------------------------------------

export const COVER_LETTER_REASONING =
	'Selected "Microservices Migration" because it demonstrates technical leadership and architecture skills.';

const DRAFT_TEXT = `Dear Hiring Manager,

I am writing to express my strong interest in the Frontend Engineer position at AlphaTech. With eight years of experience building scalable web applications, I bring a proven track record of delivering high-quality software.

In my current role as Senior Engineer at Acme Corp, I led the migration of our monolithic frontend to a modern microservices architecture. This initiative reduced deployment time from two hours to fifteen minutes and improved developer velocity by forty percent across the entire engineering organization. I championed the adoption of TypeScript across three teams.

My experience extends well beyond technical implementation alone. I created a structured mentoring program that helped three junior engineers earn promotions within twelve months. I believe that building strong teams is just as important as building strong code.

I am particularly drawn to your mission of making developer tools more accessible to everyone. Your commitment to open source aligns perfectly with my own values. The challenges described in this posting are areas where I have deep experience and genuine enthusiasm.

I am confident that my combination of technical skills, leadership experience, and passion for developer tooling makes me an excellent fit for this role. I would welcome the opportunity to discuss how I can contribute to your growing team.

Thank you for considering my application.

Sincerely,
Jane Doe`;

const BASE_COVER_LETTER: CoverLetter = {
	id: COVER_LETTER_ID,
	persona_id: PERSONA_ID,
	application_id: null,
	job_posting_id: JOB_POSTING_ID,
	achievement_stories_used: [STORY_IDS[0], STORY_IDS[1]],
	draft_text: DRAFT_TEXT,
	final_text: null,
	status: "Draft",
	agent_reasoning: COVER_LETTER_REASONING,
	validation_result: null,
	approved_at: null,
	created_at: NOW,
	updated_at: NOW,
	archived_at: null,
};

/** Draft cover letter detail (default). */
export function coverLetterDetail(
	overrides?: Partial<CoverLetter>,
): ApiResponse<CoverLetter> {
	return { data: { ...BASE_COVER_LETTER, ...overrides } };
}

/** Cover letter list with one draft for the job posting. */
export function coverLettersList(
	overrides?: Partial<CoverLetter>,
): ApiListResponse<CoverLetter> {
	return {
		data: [{ ...BASE_COVER_LETTER, ...overrides }],
		meta: listMeta(1),
	};
}

/** Empty cover letter list (no materials). */
export function emptyCoverLettersList(): ApiListResponse<CoverLetter> {
	return { data: [], meta: listMeta(0) };
}

// ---------------------------------------------------------------------------
// Guardrail & Validation error fixtures
// ---------------------------------------------------------------------------

export const GUARDRAIL_WITH_ERRORS: GuardrailResult = {
	passed: false,
	violations: [
		{
			severity: "error",
			rule: "new_bullets_added",
			message: "Resume contains fabricated accomplishments not in persona.",
		},
	],
};

export const VALIDATION_WITH_ERRORS: CoverLetterValidation = {
	passed: false,
	issues: [
		{
			severity: "error",
			rule: "length_min",
			message: "Cover letter is too short (minimum 250 words).",
		},
	],
	word_count: 50,
};
