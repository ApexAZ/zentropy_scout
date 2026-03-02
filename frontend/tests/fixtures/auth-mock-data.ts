/**
 * Mock data factories for auth E2E tests.
 *
 * Provides user session responses, auth endpoint responses, and error
 * shapes matching backend models (auth endpoints in REQ-013 §7.5).
 */

import type { ApiListResponse, PaginationMeta } from "@/types/api";
import type { Persona } from "@/types/persona";

import { PERSONA_ID } from "./onboarding-mock-data";

// ---------------------------------------------------------------------------
// Re-exports
// ---------------------------------------------------------------------------

export { PERSONA_ID } from "./onboarding-mock-data";

// ---------------------------------------------------------------------------
// Consistent IDs
// ---------------------------------------------------------------------------

export const AUTH_USER_ID = "00000000-0000-4000-a000-000000000001";
export const AUTH_TEST_EMAIL = "test@example.com";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const NOW = "2026-02-20T12:00:00Z";

function listMeta(total: number): PaginationMeta {
	return { total, page: 1, per_page: 100, total_pages: 1 };
}

// ---------------------------------------------------------------------------
// Auth /me responses
// ---------------------------------------------------------------------------

interface AuthMeOptions {
	hasPassword?: boolean;
	name?: string;
	isAdmin?: boolean;
}

/** GET /auth/me — authenticated user (with password by default). */
export function authMeResponse(options?: AuthMeOptions) {
	return {
		data: {
			id: AUTH_USER_ID,
			email: AUTH_TEST_EMAIL,
			name: options?.name ?? "Test User",
			image: null,
			email_verified: true,
			has_password: options?.hasPassword ?? true,
			is_admin: options?.isAdmin ?? false,
		},
	};
}

// ---------------------------------------------------------------------------
// Auth endpoint responses
// ---------------------------------------------------------------------------

/** POST /auth/verify-password — success. */
export function verifyPasswordResponse() {
	return { data: { message: "Authenticated" } };
}

/** POST /auth/register — success (201). */
export function registerResponse() {
	return { data: { message: "Account created. Check your email." } };
}

/** POST /auth/magic-link — success. */
export function magicLinkResponse() {
	return { data: { message: "Magic link sent." } };
}

/** PATCH /auth/profile — success with updated name. */
export function profilePatchResponse(name: string) {
	return {
		data: {
			id: AUTH_USER_ID,
			email: AUTH_TEST_EMAIL,
			name,
			image: null,
			email_verified: true,
			has_password: true,
		},
	};
}

/** POST /auth/change-password — success. */
export function changePasswordResponse() {
	return { data: { message: "Password updated." } };
}

/** POST /auth/logout — success. */
export function logoutResponse() {
	return { data: { message: "Logged out." } };
}

/** POST /auth/invalidate-sessions — success. */
export function invalidateSessionsResponse() {
	return { data: { message: "All sessions invalidated." } };
}

// ---------------------------------------------------------------------------
// Error responses
// ---------------------------------------------------------------------------

/** Standard error response matching backend envelope. */
export function errorResponse(code: string, message: string, status?: number) {
	return {
		error: { code, message, ...(status ? { status } : {}) },
	};
}

// ---------------------------------------------------------------------------
// Persona (for settings page persona status guard)
// ---------------------------------------------------------------------------

const ONBOARDED_PERSONA: Persona = {
	id: PERSONA_ID,
	user_id: AUTH_USER_ID,
	full_name: "Test User",
	email: AUTH_TEST_EMAIL,
	phone: "+1 555-123-4567",
	home_city: "San Francisco",
	home_state: "CA",
	home_country: "USA",
	linkedin_url: null,
	portfolio_url: null,
	professional_summary: "Experienced software engineer",
	years_experience: 8,
	current_role: "Senior Engineer",
	current_company: "Acme Corp",
	target_roles: ["Staff Engineer"],
	target_skills: ["Kubernetes"],
	stretch_appetite: "Medium",
	commutable_cities: ["San Francisco"],
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
