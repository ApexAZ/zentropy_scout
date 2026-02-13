/**
 * Tests for growth targets shared helpers.
 *
 * REQ-012 §7.2.8: Verifies toFormValues and toRequestBody conversion
 * functions produce correct output for various persona states.
 */

import { describe, expect, it } from "vitest";

import type { Persona } from "@/types/persona";

import { toFormValues, toRequestBody } from "./growth-targets-helpers";
import type { GrowthTargetsFormData } from "./growth-targets-helpers";

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
	target_roles: ["Engineering Manager", "Staff Engineer"],
	target_skills: ["Kubernetes", "People Management"],
	stretch_appetite: "High",
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
	minimum_fit_threshold: 50,
	auto_draft_threshold: 90,
	polling_frequency: "Daily",
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
			target_roles: ["Engineering Manager", "Staff Engineer"],
			target_skills: ["Kubernetes", "People Management"],
			stretch_appetite: "High",
		});
	});

	it("returns empty arrays and default appetite when persona has defaults", () => {
		const persona: Persona = {
			...FULL_PERSONA,
			target_roles: [],
			target_skills: [],
			stretch_appetite: "Medium",
		};
		const result = toFormValues(persona);

		expect(result).toEqual({
			target_roles: [],
			target_skills: [],
			stretch_appetite: "Medium",
		});
	});
});

// ---------------------------------------------------------------------------
// toRequestBody
// ---------------------------------------------------------------------------

describe("toRequestBody", () => {
	it("converts full form data to request body", () => {
		const data: GrowthTargetsFormData = {
			target_roles: ["VP Engineering"],
			target_skills: ["Leadership"],
			stretch_appetite: "High",
		};

		const result = toRequestBody(data);

		expect(result).toEqual({
			target_roles: ["VP Engineering"],
			target_skills: ["Leadership"],
			stretch_appetite: "High",
		});
	});

	it("converts empty arrays and default appetite", () => {
		const data: GrowthTargetsFormData = {
			target_roles: [],
			target_skills: [],
			stretch_appetite: "Medium",
		};

		const result = toRequestBody(data);

		expect(result).toEqual({
			target_roles: [],
			target_skills: [],
			stretch_appetite: "Medium",
		});
	});
});
