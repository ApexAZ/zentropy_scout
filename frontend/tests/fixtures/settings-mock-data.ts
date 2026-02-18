/**
 * Mock data factories for settings page E2E tests.
 *
 * Provides job sources, user source preferences, and an onboarded persona
 * matching backend models (job_source.py, user_source_preference.py).
 */

import type { ApiListResponse, PaginationMeta } from "@/types/api";
import type { Persona } from "@/types/persona";
import type { JobSource, UserSourcePreference } from "@/types/source";

import { PERSONA_ID } from "./onboarding-mock-data";

// ---------------------------------------------------------------------------
// Re-exports
// ---------------------------------------------------------------------------

export { PERSONA_ID } from "./onboarding-mock-data";

// ---------------------------------------------------------------------------
// Consistent IDs
// ---------------------------------------------------------------------------

export const JOB_SOURCE_IDS = ["js-001", "js-002", "js-003", "js-004"] as const;

export const PREFERENCE_IDS = [
	"pref-001",
	"pref-002",
	"pref-003",
	"pref-004",
] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const NOW = "2026-02-15T12:00:00Z";

function listMeta(total: number): PaginationMeta {
	return { total, page: 1, per_page: 100, total_pages: 1 };
}

// ---------------------------------------------------------------------------
// Persona (for persona status guard)
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

/** Onboarded persona list for the persona status guard. */
export function onboardedPersonaList(): ApiListResponse<Persona> {
	return { data: [{ ...ONBOARDED_PERSONA }], meta: listMeta(1) };
}

// ---------------------------------------------------------------------------
// Job Sources
// ---------------------------------------------------------------------------

const JOB_SOURCES: JobSource[] = [
	{
		id: JOB_SOURCE_IDS[0],
		source_name: "Adzuna",
		source_type: "API",
		description: "Good US/UK coverage",
		api_endpoint: "https://api.adzuna.com/v1",
		is_active: true,
		display_order: 0,
	},
	{
		id: JOB_SOURCE_IDS[1],
		source_name: "The Muse",
		source_type: "API",
		description: "Curated companies",
		api_endpoint: "https://www.themuse.com/api/public",
		is_active: true,
		display_order: 1,
	},
	{
		id: JOB_SOURCE_IDS[2],
		source_name: "RemoteOK",
		source_type: "API",
		description: "Remote-first positions",
		api_endpoint: "https://remoteok.com/api",
		is_active: true,
		display_order: 2,
	},
	{
		id: JOB_SOURCE_IDS[3],
		source_name: "Chrome Extension",
		source_type: "Extension",
		description: "Capture from any job board",
		api_endpoint: null,
		is_active: false,
		display_order: 3,
	},
];

/** 4 job sources — 3 active APIs + 1 inactive extension. */
export function jobSourcesList(): ApiListResponse<JobSource> {
	return { data: [...JOB_SOURCES], meta: listMeta(4) };
}

// ---------------------------------------------------------------------------
// User Source Preferences
// ---------------------------------------------------------------------------

const USER_SOURCE_PREFERENCES: UserSourcePreference[] = [
	{
		id: PREFERENCE_IDS[0],
		persona_id: PERSONA_ID,
		source_id: JOB_SOURCE_IDS[0],
		is_enabled: true,
		display_order: 0,
	},
	{
		id: PREFERENCE_IDS[1],
		persona_id: PERSONA_ID,
		source_id: JOB_SOURCE_IDS[1],
		is_enabled: false,
		display_order: 1,
	},
	{
		id: PREFERENCE_IDS[2],
		persona_id: PERSONA_ID,
		source_id: JOB_SOURCE_IDS[2],
		is_enabled: true,
		display_order: 2,
	},
	{
		id: PREFERENCE_IDS[3],
		persona_id: PERSONA_ID,
		source_id: JOB_SOURCE_IDS[3],
		is_enabled: false,
		display_order: 3,
	},
];

/** 4 preferences — 2 enabled, 2 disabled (The Muse + Chrome Extension). */
export function userSourcePreferencesList(): ApiListResponse<UserSourcePreference> {
	return { data: [...USER_SOURCE_PREFERENCES], meta: listMeta(4) };
}

/** PATCH response for toggling a preference. */
export function patchPreferenceResponse(
	preferenceId: string,
	overrides: Partial<UserSourcePreference>,
): { data: UserSourcePreference } {
	const pref =
		USER_SOURCE_PREFERENCES.find((p) => p.id === preferenceId) ??
		USER_SOURCE_PREFERENCES[0];
	return { data: { ...pref, ...overrides } };
}
