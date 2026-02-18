/**
 * Mock data factories for cover letter review E2E tests.
 *
 * Re-exports persona sub-entity data from onboarding-mock-data.ts and adds
 * new fixtures for CoverLetter, validation, and related entities.
 * Returns API response envelopes (ApiResponse / ApiListResponse).
 */

import type { ApiListResponse, ApiResponse, PaginationMeta } from "@/types/api";
import type { CoverLetter, CoverLetterValidation } from "@/types/application";
import type { ExtractedSkill, JobPosting } from "@/types/job";
import type { Persona } from "@/types/persona";

import {
	achievementStoriesList,
	emptyChangeFlagsList,
	emptyChatMessages,
	PERSONA_ID,
	personaList,
	SKILL_IDS,
	skillsList,
	STORY_IDS,
	voiceProfileResponse,
} from "./onboarding-mock-data";

// ---------------------------------------------------------------------------
// Re-exports (used by mock controller and spec file)
// ---------------------------------------------------------------------------

export {
	achievementStoriesList,
	emptyChangeFlagsList,
	emptyChatMessages,
	PERSONA_ID,
	personaList,
	SKILL_IDS,
	skillsList,
	STORY_IDS,
	voiceProfileResponse,
};

// ---------------------------------------------------------------------------
// Consistent IDs
// ---------------------------------------------------------------------------

export const COVER_LETTER_ID = "cl-e2e-001" as const;
export const JOB_POSTING_ID = "jp-e2e-cl-001" as const;

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
// Draft text (~300 words, within 250-350 target range)
// ---------------------------------------------------------------------------

export const DRAFT_TEXT = `Dear Hiring Manager,

I am writing to express my strong interest in the Frontend Engineer position at AlphaTech. With eight years of experience building scalable web applications, I bring a proven track record of delivering high-quality software that delights users and drives meaningful business results.

In my current role as Senior Engineer at Acme Corp, I led the migration of our monolithic frontend to a modern microservices architecture. This initiative reduced deployment time from two hours to fifteen minutes and improved developer velocity by forty percent across the entire engineering organization. I championed the adoption of TypeScript across three teams, resulting in a fifty percent reduction in production bugs within the first six months.

My experience extends well beyond technical implementation alone. I created a structured mentoring program that helped three junior engineers earn promotions within twelve months. I believe that building strong teams is just as important as building strong code. I regularly facilitate knowledge sharing sessions and contribute to our engineering blog with articles on performance optimization.

I am particularly drawn to your mission of making developer tools more accessible to everyone. Your commitment to open source aligns perfectly with my own values. The challenges described in this posting, specifically around real-time collaboration and performance optimization, are areas where I have deep experience and genuine enthusiasm.

At my previous company, I built a real-time data pipeline from scratch that reduced data latency from twenty-four hours to under one minute. This experience taught me the importance of thoughtful architecture decisions and thorough testing practices.

I am confident that my combination of technical skills, leadership experience, and passion for developer tooling makes me an excellent fit for this role. I would welcome the opportunity to discuss how I can contribute to your growing team.

Thank you for considering my application.

Sincerely,
Jane Doe`;

/** Short draft text (~20 words, well below 250 minimum). */
export const SHORT_DRAFT_TEXT =
	"Dear Hiring Manager, I am writing to apply for the open position at your company. Thank you for your time.";

// ---------------------------------------------------------------------------
// Agent reasoning
// ---------------------------------------------------------------------------

export const AGENT_REASONING =
	'Selected "Microservices Migration" because it demonstrates technical leadership and architecture skills. Selected "Mentoring Program" to highlight team-building capabilities mentioned in the job posting.';

// ---------------------------------------------------------------------------
// Cover Letter fixtures
// ---------------------------------------------------------------------------

const BASE_COVER_LETTER: CoverLetter = {
	id: COVER_LETTER_ID,
	persona_id: PERSONA_ID,
	application_id: null,
	job_posting_id: JOB_POSTING_ID,
	achievement_stories_used: [STORY_IDS[0], STORY_IDS[1]],
	draft_text: DRAFT_TEXT,
	final_text: null,
	status: "Draft",
	agent_reasoning: AGENT_REASONING,
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

/** Cover letter list with one draft. */
export function coverLettersList(
	overrides?: Partial<CoverLetter>,
): ApiListResponse<CoverLetter> {
	return {
		data: [{ ...BASE_COVER_LETTER, ...overrides }],
		meta: listMeta(1),
	};
}

/** Empty cover letter list. */
export function emptyCoverLettersList(): ApiListResponse<CoverLetter> {
	return { data: [], meta: listMeta(0) };
}

// ---------------------------------------------------------------------------
// Validation fixtures
// ---------------------------------------------------------------------------

export const VALIDATION_WITH_ERRORS: CoverLetterValidation = {
	passed: false,
	issues: [
		{
			severity: "error",
			rule: "length_min",
			message: "Cover letter is too short (minimum 250 words).",
		},
		{
			severity: "error",
			rule: "blacklist_violation",
			message: "Contains blacklisted phrase.",
		},
	],
	word_count: 50,
};

export const VALIDATION_WITH_WARNINGS: CoverLetterValidation = {
	passed: true,
	issues: [
		{
			severity: "warning",
			rule: "company_specificity",
			message: "Company name not mentioned in opening paragraph.",
		},
	],
	word_count: 300,
};

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
	description_hash: "hash-cl-001",
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

/** Empty extracted skills list. */
export function emptyExtractedSkillsList(): ApiListResponse<ExtractedSkill> {
	return { data: [], meta: listMeta(0) };
}
