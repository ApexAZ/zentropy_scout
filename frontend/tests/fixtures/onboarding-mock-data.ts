/**
 * Mock data factories for onboarding E2E tests.
 *
 * Returns API response envelopes (ApiResponse / ApiListResponse) with
 * realistic data shapes matching persona.ts, resume.ts, and api.ts.
 */

import type { ApiListResponse, ApiResponse, PaginationMeta } from "@/types/api";
import type {
	AchievementStory,
	Bullet,
	Certification,
	CustomNonNegotiable,
	Education,
	Persona,
	Skill,
	VoiceProfile,
	WorkHistory,
} from "@/types/persona";
import type { BaseResume, ResumeFile } from "@/types/resume";

// ---------------------------------------------------------------------------
// Consistent IDs
// ---------------------------------------------------------------------------

export const PERSONA_ID = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d";
export const USER_ID = "00000000-0000-4000-a000-000000000099";
export const WORK_HISTORY_IDS = ["wh-001", "wh-002"] as const;
export const BULLET_IDS = ["b-001", "b-002", "b-003", "b-004"] as const;
export const EDUCATION_ID = "edu-001";
export const SKILL_IDS = ["skill-001", "skill-002", "skill-003"] as const;
export const CERT_ID = "cert-001";
export const STORY_IDS = ["story-001", "story-002", "story-003"] as const;
export const VOICE_PROFILE_ID = "vp-001";
export const BASE_RESUME_ID = "br-001";
export const RESUME_FILE_ID = "rf-001";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const NOW = "2026-02-15T12:00:00Z";

function listMeta(total: number): PaginationMeta {
	return { total, page: 1, per_page: 100, total_pages: 1 };
}

// ---------------------------------------------------------------------------
// Persona factories
// ---------------------------------------------------------------------------

const BASE_PERSONA: Persona = {
	id: PERSONA_ID,
	user_id: USER_ID,
	full_name: "Jane Doe",
	email: "jane@example.com",
	phone: "+1 555-123-4567",
	home_city: "San Francisco",
	home_state: "CA",
	home_country: "USA",
	linkedin_url: "https://linkedin.com/in/janedoe",
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
	onboarding_complete: false,
	onboarding_step: null,
	created_at: NOW,
	updated_at: NOW,
};

/** No persona exists — gate check returns empty list. */
export function emptyPersonaList(): ApiListResponse<Persona> {
	return { data: [], meta: listMeta(0) };
}

/** Persona with all fields populated. */
export function personaList(
	overrides?: Partial<Persona>,
): ApiListResponse<Persona> {
	return {
		data: [{ ...BASE_PERSONA, ...overrides }],
		meta: listMeta(1),
	};
}

/** Single persona response (for PATCH returns). */
export function personaResponse(
	overrides?: Partial<Persona>,
): ApiResponse<Persona> {
	return { data: { ...BASE_PERSONA, ...overrides } };
}

// ---------------------------------------------------------------------------
// Work History factories
// ---------------------------------------------------------------------------

const BULLETS: Bullet[] = [
	{
		id: BULLET_IDS[0],
		work_history_id: WORK_HISTORY_IDS[0],
		text: "Led migration to microservices, reducing deploy time by 60%",
		skills_demonstrated: [SKILL_IDS[0]],
		metrics: "60% reduction",
		display_order: 0,
	},
	{
		id: BULLET_IDS[1],
		work_history_id: WORK_HISTORY_IDS[0],
		text: "Mentored 3 junior engineers through structured 1:1 program",
		skills_demonstrated: [],
		metrics: null,
		display_order: 1,
	},
	{
		id: BULLET_IDS[2],
		work_history_id: WORK_HISTORY_IDS[1],
		text: "Built real-time data pipeline processing 1M events/day",
		skills_demonstrated: [SKILL_IDS[0]],
		metrics: "1M events/day",
		display_order: 0,
	},
	{
		id: BULLET_IDS[3],
		work_history_id: WORK_HISTORY_IDS[1],
		text: "Improved API response time by 40% through caching layer",
		skills_demonstrated: [],
		metrics: "40% improvement",
		display_order: 1,
	},
];

const WORK_HISTORIES: WorkHistory[] = [
	{
		id: WORK_HISTORY_IDS[0],
		persona_id: PERSONA_ID,
		company_name: "Acme Corp",
		company_industry: "Technology",
		job_title: "Senior Engineer",
		start_date: "2022-01-15",
		end_date: null,
		is_current: true,
		location: "San Francisco, CA",
		work_model: "Hybrid",
		description: null,
		display_order: 0,
		bullets: [BULLETS[0], BULLETS[1]],
	},
	{
		id: WORK_HISTORY_IDS[1],
		persona_id: PERSONA_ID,
		company_name: "Beta Inc",
		company_industry: "SaaS",
		job_title: "Software Engineer",
		start_date: "2018-06-01",
		end_date: "2021-12-31",
		is_current: false,
		location: "Oakland, CA",
		work_model: "Remote",
		description: null,
		display_order: 1,
		bullets: [BULLETS[2], BULLETS[3]],
	},
];

export function workHistoryList(): ApiListResponse<WorkHistory> {
	return { data: WORK_HISTORIES, meta: listMeta(2) };
}

export function emptyWorkHistoryList(): ApiListResponse<WorkHistory> {
	return { data: [], meta: listMeta(0) };
}

export function postWorkHistoryResponse(
	overrides?: Partial<WorkHistory>,
): ApiResponse<WorkHistory> {
	return {
		data: {
			...WORK_HISTORIES[0],
			id: `wh-new-${Date.now()}`,
			bullets: [],
			...overrides,
		},
	};
}

export function postBulletResponse(
	workHistoryId: string,
	overrides?: Partial<Bullet>,
): ApiResponse<Bullet> {
	return {
		data: {
			id: `b-new-${Date.now()}`,
			work_history_id: workHistoryId,
			text: "New accomplishment",
			skills_demonstrated: [],
			metrics: null,
			display_order: 0,
			...overrides,
		},
	};
}

// ---------------------------------------------------------------------------
// Education factories
// ---------------------------------------------------------------------------

const EDUCATION: Education = {
	id: EDUCATION_ID,
	persona_id: PERSONA_ID,
	institution: "UC Berkeley",
	degree: "BS",
	field_of_study: "Computer Science",
	graduation_year: 2018,
	gpa: 3.7,
	honors: "Magna Cum Laude",
	display_order: 0,
};

export function educationList(): ApiListResponse<Education> {
	return { data: [EDUCATION], meta: listMeta(1) };
}

export function emptyEducationList(): ApiListResponse<Education> {
	return { data: [], meta: listMeta(0) };
}

// ---------------------------------------------------------------------------
// Skills factories
// ---------------------------------------------------------------------------

const SKILLS: Skill[] = [
	{
		id: SKILL_IDS[0],
		persona_id: PERSONA_ID,
		skill_name: "TypeScript",
		skill_type: "Hard",
		category: "Languages",
		proficiency: "Expert",
		years_used: 5,
		last_used: "Current",
		display_order: 0,
	},
	{
		id: SKILL_IDS[1],
		persona_id: PERSONA_ID,
		skill_name: "Python",
		skill_type: "Hard",
		category: "Languages",
		proficiency: "Proficient",
		years_used: 4,
		last_used: "Current",
		display_order: 1,
	},
	{
		id: SKILL_IDS[2],
		persona_id: PERSONA_ID,
		skill_name: "Leadership",
		skill_type: "Soft",
		category: "Management",
		proficiency: "Proficient",
		years_used: 3,
		last_used: "Current",
		display_order: 2,
	},
];

export function skillsList(): ApiListResponse<Skill> {
	return { data: SKILLS, meta: listMeta(3) };
}

export function emptySkillsList(): ApiListResponse<Skill> {
	return { data: [], meta: listMeta(0) };
}

export function postSkillResponse(
	overrides?: Partial<Skill>,
): ApiResponse<Skill> {
	return {
		data: {
			...SKILLS[0],
			id: `skill-new-${Date.now()}`,
			...overrides,
		},
	};
}

// ---------------------------------------------------------------------------
// Certification factories
// ---------------------------------------------------------------------------

const CERTIFICATION: Certification = {
	id: CERT_ID,
	persona_id: PERSONA_ID,
	certification_name: "AWS Solutions Architect",
	issuing_organization: "Amazon Web Services",
	date_obtained: "2023-06-15",
	expiration_date: "2026-06-15",
	credential_id: "AWS-SAA-12345",
	verification_url: null,
	display_order: 0,
};

export function certificationsList(): ApiListResponse<Certification> {
	return { data: [CERTIFICATION], meta: listMeta(1) };
}

export function emptyCertificationsList(): ApiListResponse<Certification> {
	return { data: [], meta: listMeta(0) };
}

// ---------------------------------------------------------------------------
// Achievement Stories factories
// ---------------------------------------------------------------------------

const STORIES: AchievementStory[] = [
	{
		id: STORY_IDS[0],
		persona_id: PERSONA_ID,
		title: "Microservices Migration",
		context: "Monolith was causing 2-hour deploy cycles",
		action: "Led 6-month migration to microservices architecture",
		outcome: "Reduced deploy time from 2 hours to 15 minutes",
		skills_demonstrated: [SKILL_IDS[0]],
		related_job_id: WORK_HISTORY_IDS[0],
		display_order: 0,
	},
	{
		id: STORY_IDS[1],
		persona_id: PERSONA_ID,
		title: "Mentoring Program",
		context: "Junior engineers had no structured onboarding",
		action: "Created structured 1:1 mentoring program with milestones",
		outcome: "3 engineers promoted within 12 months",
		skills_demonstrated: [SKILL_IDS[2]],
		related_job_id: WORK_HISTORY_IDS[0],
		display_order: 1,
	},
	{
		id: STORY_IDS[2],
		persona_id: PERSONA_ID,
		title: "Real-time Pipeline",
		context: "Batch processing caused 24-hour data lag",
		action: "Built Kafka-based real-time pipeline from scratch",
		outcome: "Reduced data latency from 24 hours to under 1 minute",
		skills_demonstrated: [SKILL_IDS[1]],
		related_job_id: WORK_HISTORY_IDS[1],
		display_order: 2,
	},
];

export function achievementStoriesList(): ApiListResponse<AchievementStory> {
	return { data: STORIES, meta: listMeta(3) };
}

export function emptyAchievementStoriesList(): ApiListResponse<AchievementStory> {
	return { data: [], meta: listMeta(0) };
}

export function postStoryResponse(
	overrides?: Partial<AchievementStory>,
): ApiResponse<AchievementStory> {
	return {
		data: {
			...STORIES[0],
			id: `story-new-${Date.now()}`,
			...overrides,
		},
	};
}

// ---------------------------------------------------------------------------
// Voice Profile factories
// ---------------------------------------------------------------------------

const VOICE_PROFILE: VoiceProfile = {
	id: VOICE_PROFILE_ID,
	persona_id: PERSONA_ID,
	tone: "Direct, confident, avoids buzzwords",
	sentence_style: "Short sentences, active voice",
	vocabulary_level: "Technical when relevant, plain otherwise",
	personality_markers: "Occasional dry humor",
	sample_phrases: ["I led", "The result was", "We shipped"],
	things_to_avoid: ["Passionate", "Synergy", "Leverage"],
	writing_sample_text: null,
	created_at: NOW,
	updated_at: NOW,
};

export function voiceProfileResponse(): ApiResponse<VoiceProfile> {
	return { data: VOICE_PROFILE };
}

export function emptyVoiceProfileResponse(): ApiResponse<VoiceProfile> {
	return {
		data: {
			...VOICE_PROFILE,
			tone: "",
			sentence_style: "",
			vocabulary_level: "",
			personality_markers: null,
			sample_phrases: [],
			things_to_avoid: [],
		},
	};
}

// ---------------------------------------------------------------------------
// Custom Non-Negotiables factories
// ---------------------------------------------------------------------------

export function customNonNegotiablesList(): ApiListResponse<CustomNonNegotiable> {
	return { data: [], meta: listMeta(0) };
}

// ---------------------------------------------------------------------------
// Resume File factories
// ---------------------------------------------------------------------------

export function uploadResumeResponse(): ApiResponse<ResumeFile> {
	return {
		data: {
			id: RESUME_FILE_ID,
			persona_id: PERSONA_ID,
			file_name: "resume.pdf",
			file_type: "PDF",
			file_size_bytes: 204800,
			uploaded_at: NOW,
			is_active: true,
		},
	};
}

// ---------------------------------------------------------------------------
// Base Resume factories
// ---------------------------------------------------------------------------

export function postBaseResumeResponse(
	overrides?: Partial<BaseResume>,
): ApiResponse<BaseResume> {
	return {
		data: {
			id: BASE_RESUME_ID,
			persona_id: PERSONA_ID,
			name: "My Resume",
			role_type: "Software Engineer",
			summary: "Experienced software engineer",
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
			rendered_at: null,
			is_primary: true,
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
// PATCH persona echo helper
// ---------------------------------------------------------------------------

/** Echoes the PATCH body back as a full persona response. */
export function patchPersonaResponse(
	body: Partial<Persona>,
): ApiResponse<Persona> {
	return { data: { ...BASE_PERSONA, ...body } };
}

// ---------------------------------------------------------------------------
// Persona Change Flags
// ---------------------------------------------------------------------------

export function emptyChangeFlagsList(): ApiListResponse<never> {
	return { data: [], meta: listMeta(0) };
}

// ---------------------------------------------------------------------------
// Chat messages
// ---------------------------------------------------------------------------

export function emptyChatMessages(): ApiListResponse<never> {
	return { data: [], meta: listMeta(0) };
}
