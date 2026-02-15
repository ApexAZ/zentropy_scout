/**
 * Mock data factories for job discovery E2E tests.
 *
 * Returns API response envelopes (ApiResponse / ApiListResponse) with
 * realistic data shapes matching job.ts, resume.ts, application.ts, and api.ts.
 */

import type { ApiListResponse, ApiResponse, PaginationMeta } from "@/types/api";
import type {
	Application,
	CoverLetter,
	JobSnapshot,
} from "@/types/application";
import type {
	ExtractedSkill,
	FailedNonNegotiable,
	GhostSignals,
	JobPosting,
	ScoreDetails,
} from "@/types/job";
import type { Persona } from "@/types/persona";
import type { JobVariant } from "@/types/resume";

// ---------------------------------------------------------------------------
// Consistent IDs
// ---------------------------------------------------------------------------

import { PERSONA_ID } from "./onboarding-mock-data";

export { PERSONA_ID };

export const JOB_IDS = [
	"job-001",
	"job-002",
	"job-003",
	"job-004",
	"job-005",
] as const;
export const VARIANT_ID = "var-001";
export const COVER_LETTER_ID = "cl-001";
export const APPLICATION_ID = "app-001";
export const BASE_RESUME_ID = "br-001";
export const EXTRACTED_SKILL_IDS = [
	"es-001",
	"es-002",
	"es-003",
	"es-004",
] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const NOW = "2026-02-15T12:00:00Z";

function listMeta(total: number): PaginationMeta {
	return { total, page: 1, per_page: 100, total_pages: 1 };
}

// ---------------------------------------------------------------------------
// Score detail fixtures
// ---------------------------------------------------------------------------

const JOB_001_SCORE_DETAILS: ScoreDetails = {
	fit: {
		total: 85,
		components: {
			hard_skills: 90,
			soft_skills: 80,
			experience_level: 85,
			role_title: 75,
			location_logistics: 90,
		},
		weights: {
			hard_skills: 0.4,
			soft_skills: 0.15,
			experience_level: 0.25,
			role_title: 0.1,
			location_logistics: 0.1,
		},
	},
	stretch: {
		total: 60,
		components: {
			target_role: 70,
			target_skills: 55,
			growth_trajectory: 50,
		},
		weights: {
			target_role: 0.5,
			target_skills: 0.4,
			growth_trajectory: 0.1,
		},
	},
	explanation: {
		summary:
			"Strong technical match with room for growth into leadership responsibilities.",
		strengths: [
			"Core TypeScript and Python skills align well",
			"Experience level matches Senior requirement",
		],
		gaps: ["No Kubernetes experience listed", "Limited team lead experience"],
		stretch_opportunities: [
			"Opportunity to lead a small team",
			"Exposure to infrastructure automation",
		],
		warnings: ["Salary range not disclosed"],
	},
};

const JOB_003_GHOST_SIGNALS: GhostSignals = {
	days_open: 120,
	days_open_score: 85,
	repost_count: 3,
	repost_score: 70,
	vagueness_score: 65,
	missing_fields: ["salary", "application_deadline"],
	missing_fields_score: 60,
	requirement_mismatch: false,
	requirement_mismatch_score: 0,
	calculated_at: NOW,
	ghost_score: 82,
};

// ---------------------------------------------------------------------------
// Job posting fixtures
// ---------------------------------------------------------------------------

const BASE_JOB: JobPosting = {
	id: JOB_IDS[0],
	persona_id: PERSONA_ID,
	external_id: "ext-001",
	source_id: "linkedin",
	also_found_on: { sources: [] },
	job_title: "Senior Software Engineer",
	company_name: "TechCorp",
	company_url: "https://techcorp.example.com",
	source_url: "https://linkedin.example.com/jobs/12345",
	apply_url: "https://techcorp.example.com/careers/apply",
	location: "San Francisco, CA",
	work_model: "Hybrid",
	seniority_level: "Senior",
	salary_min: 160000,
	salary_max: 200000,
	salary_currency: "USD",
	description:
		"We are looking for a Senior Software Engineer to join our platform team.",
	culture_text: "We value collaboration, autonomy, and continuous learning.",
	requirements:
		"5+ years experience with TypeScript. Strong backend fundamentals.",
	years_experience_min: 5,
	years_experience_max: 10,
	posted_date: "2026-02-01",
	application_deadline: null,
	first_seen_date: "2026-02-10",
	status: "Discovered",
	is_favorite: false,
	fit_score: 85,
	stretch_score: 60,
	score_details: JOB_001_SCORE_DETAILS,
	failed_non_negotiables: null,
	ghost_score: 10,
	ghost_signals: null,
	description_hash: "abc123",
	repost_count: 0,
	previous_posting_ids: null,
	last_verified_at: NOW,
	dismissed_at: null,
	expired_at: null,
	created_at: NOW,
	updated_at: NOW,
};

const MOCK_JOBS: JobPosting[] = [
	// job-001: Standard scored job (navigable, full score details)
	BASE_JOB,

	// job-002: Favorited job (pinned to top)
	{
		...BASE_JOB,
		id: JOB_IDS[1],
		external_id: "ext-002",
		job_title: "Full Stack Developer",
		company_name: "StartupXYZ",
		company_url: "https://startupxyz.example.com",
		source_url: "https://indeed.example.com/jobs/67890",
		apply_url: "https://startupxyz.example.com/apply",
		location: "Remote",
		work_model: "Remote",
		salary_min: 140000,
		salary_max: 180000,
		fit_score: 72,
		stretch_score: 45,
		score_details: null,
		is_favorite: true,
		ghost_score: 0,
		first_seen_date: "2026-02-08",
	},

	// job-003: High ghost risk
	{
		...BASE_JOB,
		id: JOB_IDS[2],
		external_id: "ext-003",
		job_title: "Platform Engineer",
		company_name: "MegaCorp",
		company_url: "https://megacorp.example.com",
		source_url: "https://glassdoor.example.com/jobs/11111",
		apply_url: null,
		location: "New York, NY",
		work_model: "Onsite",
		salary_min: null,
		salary_max: null,
		salary_currency: null,
		fit_score: 65,
		stretch_score: 50,
		score_details: null,
		ghost_score: 82,
		ghost_signals: JOB_003_GHOST_SIGNALS,
		repost_count: 3,
		previous_posting_ids: ["prev-1", "prev-2", "prev-3"],
		first_seen_date: "2026-01-15",
	},

	// job-004: Filtered (failed non-negotiables)
	{
		...BASE_JOB,
		id: JOB_IDS[3],
		external_id: "ext-004",
		job_title: "Backend Developer",
		company_name: "LowPay Inc",
		company_url: null,
		source_url: "https://linkedin.example.com/jobs/99999",
		apply_url: null,
		location: "Austin, TX",
		work_model: "Onsite",
		salary_min: 90000,
		salary_max: 110000,
		fit_score: null,
		stretch_score: null,
		score_details: null,
		failed_non_negotiables: [
			{
				filter: "minimum_base_salary",
				job_value: 110000,
				persona_value: 180000,
			} satisfies FailedNonNegotiable,
		],
		ghost_score: 15,
		first_seen_date: "2026-02-12",
	},

	// job-005: Lower fit (for sort testing)
	{
		...BASE_JOB,
		id: JOB_IDS[4],
		external_id: "ext-005",
		job_title: "Junior Developer",
		company_name: "SmallCo",
		company_url: "https://smallco.example.com",
		source_url: "https://indeed.example.com/jobs/55555",
		apply_url: "https://smallco.example.com/apply",
		location: "Portland, OR",
		work_model: "Remote",
		salary_min: 80000,
		salary_max: 100000,
		fit_score: 45,
		stretch_score: 30,
		score_details: null,
		ghost_score: 0,
		first_seen_date: "2026-02-14",
	},
];

// ---------------------------------------------------------------------------
// Extracted skills fixtures
// ---------------------------------------------------------------------------

const EXTRACTED_SKILLS: ExtractedSkill[] = [
	{
		id: EXTRACTED_SKILL_IDS[0],
		job_posting_id: JOB_IDS[0],
		skill_name: "TypeScript",
		skill_type: "Hard",
		is_required: true,
		years_requested: 5,
	},
	{
		id: EXTRACTED_SKILL_IDS[1],
		job_posting_id: JOB_IDS[0],
		skill_name: "Python",
		skill_type: "Hard",
		is_required: true,
		years_requested: 3,
	},
	{
		id: EXTRACTED_SKILL_IDS[2],
		job_posting_id: JOB_IDS[0],
		skill_name: "Kubernetes",
		skill_type: "Hard",
		is_required: false,
		years_requested: null,
	},
	{
		id: EXTRACTED_SKILL_IDS[3],
		job_posting_id: JOB_IDS[0],
		skill_name: "Leadership",
		skill_type: "Soft",
		is_required: false,
		years_requested: null,
	},
];

// ---------------------------------------------------------------------------
// Variant fixtures
// ---------------------------------------------------------------------------

const APPROVED_VARIANT: JobVariant = {
	id: VARIANT_ID,
	base_resume_id: BASE_RESUME_ID,
	job_posting_id: JOB_IDS[0],
	summary: "Tailored summary for TechCorp Senior Software Engineer role",
	job_bullet_order: {},
	modifications_description:
		"Reordered bullets to emphasize TypeScript experience",
	status: "Approved",
	snapshot_included_jobs: ["wh-001", "wh-002"],
	snapshot_job_bullet_selections: {},
	snapshot_included_education: ["edu-001"],
	snapshot_included_certifications: null,
	snapshot_skills_emphasis: ["skill-001", "skill-002"],
	agent_reasoning: "Focused on TypeScript and backend experience",
	guardrail_result: { passed: true, violations: [] },
	approved_at: NOW,
	archived_at: null,
	created_at: NOW,
	updated_at: NOW,
};

// ---------------------------------------------------------------------------
// Cover letter fixtures
// ---------------------------------------------------------------------------

const APPROVED_COVER_LETTER: CoverLetter = {
	id: COVER_LETTER_ID,
	persona_id: PERSONA_ID,
	application_id: null,
	job_posting_id: JOB_IDS[0],
	achievement_stories_used: ["story-001", "story-002"],
	draft_text: "Dear Hiring Manager, ...",
	final_text: "Dear Hiring Manager, I am writing to express my interest...",
	status: "Approved",
	agent_reasoning:
		"Selected stories demonstrating leadership and technical skill",
	validation_result: { passed: true, issues: [], word_count: 320 },
	approved_at: NOW,
	created_at: NOW,
	updated_at: NOW,
	archived_at: null,
};

// ---------------------------------------------------------------------------
// Application fixtures
// ---------------------------------------------------------------------------

const JOB_SNAPSHOT: JobSnapshot = {
	title: "Senior Software Engineer",
	company_name: "TechCorp",
	company_url: "https://techcorp.example.com",
	description: "We are looking for a Senior Software Engineer...",
	requirements: "5+ years TypeScript experience",
	salary_min: 160000,
	salary_max: 200000,
	salary_currency: "USD",
	location: "San Francisco, CA",
	work_model: "Hybrid",
	source_url: "https://linkedin.example.com/jobs/12345",
	captured_at: NOW,
};

const EXISTING_APPLICATION: Application = {
	id: APPLICATION_ID,
	persona_id: PERSONA_ID,
	job_posting_id: JOB_IDS[0],
	job_variant_id: VARIANT_ID,
	cover_letter_id: COVER_LETTER_ID,
	submitted_resume_pdf_id: null,
	submitted_cover_letter_pdf_id: null,
	job_snapshot: JOB_SNAPSHOT,
	status: "Applied",
	current_interview_stage: null,
	offer_details: null,
	rejection_details: null,
	notes: null,
	is_pinned: false,
	applied_at: NOW,
	status_updated_at: NOW,
	created_at: NOW,
	updated_at: NOW,
	archived_at: null,
};

// ---------------------------------------------------------------------------
// Persona factory (onboarded)
// ---------------------------------------------------------------------------

const ONBOARDED_PERSONA: Persona = {
	id: PERSONA_ID,
	user_id: "00000000-0000-4000-a000-000000000099",
	full_name: "Jane Doe",
	email: "jane@example.com",
	phone: "+1 555-123-4567",
	home_city: "San Francisco",
	home_state: "CA",
	home_country: "USA",
	linkedin_url: "https://linkedin.example.com/in/janedoe",
	portfolio_url: null,
	professional_summary: "Experienced software engineer",
	years_experience: 8,
	current_role: "Senior Engineer",
	current_company: "Acme Corp",
	target_roles: ["Staff Engineer", "Engineering Manager"],
	target_skills: ["Kubernetes", "People Management"],
	stretch_appetite: "Medium",
	commutable_cities: ["San Francisco", "Oakland"],
	max_commute_minutes: 45,
	remote_preference: "Hybrid OK",
	relocation_open: false,
	relocation_cities: [],
	minimum_base_salary: 180000,
	salary_currency: "USD",
	visa_sponsorship_required: false,
	industry_exclusions: [],
	company_size_preference: "No Preference",
	max_travel_percent: "<25%",
	minimum_fit_threshold: 60,
	auto_draft_threshold: 80,
	polling_frequency: "Daily",
	onboarding_complete: true,
	onboarding_step: "base-resume",
	created_at: NOW,
	updated_at: NOW,
};

// ---------------------------------------------------------------------------
// Factory functions
// ---------------------------------------------------------------------------

/** Returns 5 mock jobs for the opportunities table. */
export function jobPostingsList(): ApiListResponse<JobPosting> {
	return { data: [...MOCK_JOBS], meta: listMeta(5) };
}

/** Returns an empty job list. */
export function emptyJobPostingsList(): ApiListResponse<JobPosting> {
	return { data: [], meta: listMeta(0) };
}

/** Returns a single job posting with full score details (job-001 by default). */
export function jobPostingDetail(id?: string): ApiResponse<JobPosting> {
	const jobId = id ?? JOB_IDS[0];
	const job = MOCK_JOBS.find((j) => j.id === jobId);
	return { data: job ?? BASE_JOB };
}

/** Returns 4 extracted skills (2 required, 2 preferred). */
export function extractedSkillsList(): ApiListResponse<ExtractedSkill> {
	return { data: [...EXTRACTED_SKILLS], meta: listMeta(4) };
}

/** Returns an empty extracted skills list. */
export function emptyExtractedSkillsList(): ApiListResponse<ExtractedSkill> {
	return { data: [], meta: listMeta(0) };
}

/** Returns 1 approved variant for a given job. */
export function approvedVariantList(
	jobId?: string,
): ApiListResponse<JobVariant> {
	return {
		data: [{ ...APPROVED_VARIANT, job_posting_id: jobId ?? JOB_IDS[0] }],
		meta: listMeta(1),
	};
}

/** Returns an empty variant list. */
export function emptyVariantList(): ApiListResponse<JobVariant> {
	return { data: [], meta: listMeta(0) };
}

/** Returns 1 approved cover letter for a given job. */
export function approvedCoverLetterList(
	jobId?: string,
): ApiListResponse<CoverLetter> {
	return {
		data: [{ ...APPROVED_COVER_LETTER, job_posting_id: jobId ?? JOB_IDS[0] }],
		meta: listMeta(1),
	};
}

/** Returns an empty cover letter list. */
export function emptyCoverLetterList(): ApiListResponse<CoverLetter> {
	return { data: [], meta: listMeta(0) };
}

/** Returns a list containing 1 existing application. */
export function applicationsList(): ApiListResponse<Application> {
	return { data: [{ ...EXISTING_APPLICATION }], meta: listMeta(1) };
}

/** Returns an empty applications list. */
export function emptyApplicationsList(): ApiListResponse<Application> {
	return { data: [], meta: listMeta(0) };
}

/** Returns a newly created application response. */
export function postApplicationResponse(
	jobId?: string,
): ApiResponse<Application> {
	return {
		data: {
			...EXISTING_APPLICATION,
			job_posting_id: jobId ?? JOB_IDS[0],
		},
	};
}

/** Returns an onboarded persona list (onboarding_complete=true). */
export function onboardedPersonaList(): ApiListResponse<Persona> {
	return { data: [{ ...ONBOARDED_PERSONA }], meta: listMeta(1) };
}
