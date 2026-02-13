/**
 * Tests for discovery preferences shared helpers.
 *
 * REQ-012 §7.2.9: Verifies toFormValues and toRequestBody conversion
 * functions, plus schema validation for threshold and polling fields.
 */

import { describe, expect, it } from "vitest";

import type { Persona } from "@/types/persona";

import {
	discoveryPreferencesSchema,
	toFormValues,
	toRequestBody,
} from "./discovery-preferences-helpers";
import type { DiscoveryPreferencesFormData } from "./discovery-preferences-helpers";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const FULL_PERSONA: Persona = {
	id: "00000000-0000-4000-a000-000000000001",
	user_id: "00000000-0000-4000-a000-000000000002",
	full_name: "Jane Doe",
	email: "jane@example.com",
	phone: "+1-555-0123",
	home_city: "San Francisco",
	home_state: "CA",
	home_country: "USA",
	linkedin_url: null,
	portfolio_url: null,
	professional_summary: null,
	years_experience: null,
	current_role: null,
	current_company: null,
	target_roles: [],
	target_skills: [],
	stretch_appetite: "Medium",
	commutable_cities: [],
	max_commute_minutes: null,
	remote_preference: "No Preference",
	relocation_open: false,
	relocation_cities: [],
	minimum_base_salary: null,
	salary_currency: "USD",
	visa_sponsorship_required: false,
	industry_exclusions: [],
	company_size_preference: "No Preference",
	max_travel_percent: "None",
	minimum_fit_threshold: 70,
	auto_draft_threshold: 85,
	polling_frequency: "Weekly",
	onboarding_complete: true,
	onboarding_step: null,
	created_at: "2026-01-01T00:00:00Z",
	updated_at: "2026-01-01T00:00:00Z",
};

// ---------------------------------------------------------------------------
// toFormValues
// ---------------------------------------------------------------------------

describe("toFormValues", () => {
	it("converts full persona to form values", () => {
		const result = toFormValues(FULL_PERSONA);

		expect(result).toEqual({
			minimum_fit_threshold: 70,
			auto_draft_threshold: 85,
			polling_frequency: "Weekly",
		});
	});

	it("returns default values when persona has default settings", () => {
		const persona: Persona = {
			...FULL_PERSONA,
			minimum_fit_threshold: 50,
			auto_draft_threshold: 90,
			polling_frequency: "Daily",
		};
		const result = toFormValues(persona);

		expect(result).toEqual({
			minimum_fit_threshold: 50,
			auto_draft_threshold: 90,
			polling_frequency: "Daily",
		});
	});
});

// ---------------------------------------------------------------------------
// toRequestBody
// ---------------------------------------------------------------------------

describe("toRequestBody", () => {
	it("converts form data to request body", () => {
		const data: DiscoveryPreferencesFormData = {
			minimum_fit_threshold: 60,
			auto_draft_threshold: 95,
			polling_frequency: "Twice Daily",
		};

		const result = toRequestBody(data);

		expect(result).toEqual({
			minimum_fit_threshold: 60,
			auto_draft_threshold: 95,
			polling_frequency: "Twice Daily",
		});
	});
});

// ---------------------------------------------------------------------------
// Schema validation
// ---------------------------------------------------------------------------

describe("discoveryPreferencesSchema", () => {
	it("accepts valid data", () => {
		const result = discoveryPreferencesSchema.safeParse({
			minimum_fit_threshold: 50,
			auto_draft_threshold: 90,
			polling_frequency: "Daily",
		});

		expect(result.success).toBe(true);
	});

	it("rejects threshold below 0", () => {
		const result = discoveryPreferencesSchema.safeParse({
			minimum_fit_threshold: -1,
			auto_draft_threshold: 90,
			polling_frequency: "Daily",
		});

		expect(result.success).toBe(false);
	});

	it("rejects threshold above 100", () => {
		const result = discoveryPreferencesSchema.safeParse({
			minimum_fit_threshold: 50,
			auto_draft_threshold: 101,
			polling_frequency: "Daily",
		});

		expect(result.success).toBe(false);
	});

	it("rejects non-integer threshold", () => {
		const result = discoveryPreferencesSchema.safeParse({
			minimum_fit_threshold: 50.5,
			auto_draft_threshold: 90,
			polling_frequency: "Daily",
		});

		expect(result.success).toBe(false);
	});

	it("rejects invalid polling frequency", () => {
		const result = discoveryPreferencesSchema.safeParse({
			minimum_fit_threshold: 50,
			auto_draft_threshold: 90,
			polling_frequency: "Hourly",
		});

		expect(result.success).toBe(false);
	});
});
