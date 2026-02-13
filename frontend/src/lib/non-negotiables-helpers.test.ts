/**
 * Tests for shared non-negotiables helper functions.
 *
 * REQ-012 §7.2.7: Verify conversion between Persona non-negotiable
 * fields, form values, and request bodies.
 */

import { describe, expect, it } from "vitest";

import type { Persona } from "@/types/persona";

import { toFormValues, toRequestBody } from "./non-negotiables-helpers";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MOCK_PERSONA: Persona = {
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
	commutable_cities: ["Boston", "NYC"],
	max_commute_minutes: 45,
	remote_preference: "Hybrid OK",
	relocation_open: true,
	relocation_cities: ["Austin", "Denver"],
	minimum_base_salary: 120000,
	salary_currency: "EUR",
	visa_sponsorship_required: true,
	industry_exclusions: ["Tobacco", "Gambling"],
	company_size_preference: "Startup",
	max_travel_percent: "<25%",
	minimum_fit_threshold: 70,
	auto_draft_threshold: 85,
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
	it("converts full persona fields to form values", () => {
		const result = toFormValues(MOCK_PERSONA);

		expect(result).toEqual({
			remote_preference: "Hybrid OK",
			commutable_cities: ["Boston", "NYC"],
			max_commute_minutes: "45",
			relocation_open: true,
			relocation_cities: ["Austin", "Denver"],
			prefer_no_salary: false,
			minimum_base_salary: "120000",
			salary_currency: "EUR",
			visa_sponsorship_required: true,
			industry_exclusions: ["Tobacco", "Gambling"],
			company_size_preference: "Startup",
			max_travel_percent: "<25%",
		});
	});

	it("derives prefer_no_salary=true when salary is null", () => {
		const persona = { ...MOCK_PERSONA, minimum_base_salary: null };
		const result = toFormValues(persona);

		expect(result.prefer_no_salary).toBe(true);
		expect(result.minimum_base_salary).toBe("");
	});

	it("derives prefer_no_salary=false when salary is set", () => {
		const result = toFormValues(MOCK_PERSONA);

		expect(result.prefer_no_salary).toBe(false);
		expect(result.minimum_base_salary).toBe("120000");
	});

	it("uses defaults for null/missing fields", () => {
		const persona = {
			...MOCK_PERSONA,
			commutable_cities: [],
			max_commute_minutes: null,
			relocation_open: false,
			relocation_cities: [],
			minimum_base_salary: null,
			industry_exclusions: [],
		};
		const result = toFormValues(persona);

		expect(result.commutable_cities).toEqual([]);
		expect(result.max_commute_minutes).toBe("");
		expect(result.relocation_open).toBe(false);
		expect(result.relocation_cities).toEqual([]);
		expect(result.minimum_base_salary).toBe("");
		expect(result.industry_exclusions).toEqual([]);
	});
});

// ---------------------------------------------------------------------------
// toRequestBody
// ---------------------------------------------------------------------------

describe("toRequestBody", () => {
	it("converts full form data to request body", () => {
		const result = toRequestBody({
			remote_preference: "Hybrid OK",
			commutable_cities: ["Boston"],
			max_commute_minutes: "45",
			relocation_open: true,
			relocation_cities: ["Austin"],
			prefer_no_salary: false,
			minimum_base_salary: "120000",
			salary_currency: "EUR",
			visa_sponsorship_required: true,
			industry_exclusions: ["Tobacco"],
			company_size_preference: "Startup",
			max_travel_percent: "<25%",
		});

		expect(result).toEqual({
			remote_preference: "Hybrid OK",
			commutable_cities: ["Boston"],
			max_commute_minutes: 45,
			relocation_open: true,
			relocation_cities: ["Austin"],
			minimum_base_salary: 120000,
			salary_currency: "EUR",
			visa_sponsorship_required: true,
			industry_exclusions: ["Tobacco"],
			company_size_preference: "Startup",
			max_travel_percent: "<25%",
		});
	});

	it("clears commute fields when Remote Only", () => {
		const result = toRequestBody({
			remote_preference: "Remote Only",
			commutable_cities: ["Boston"],
			max_commute_minutes: "45",
			relocation_open: false,
			relocation_cities: [],
			prefer_no_salary: true,
			minimum_base_salary: "",
			salary_currency: "USD",
			visa_sponsorship_required: false,
			industry_exclusions: [],
			company_size_preference: "No Preference",
			max_travel_percent: "None",
		});

		expect(result.commutable_cities).toEqual([]);
		expect(result.max_commute_minutes).toBeNull();
	});

	it("clears relocation cities when relocation_open is false", () => {
		const result = toRequestBody({
			remote_preference: "No Preference",
			commutable_cities: [],
			max_commute_minutes: "",
			relocation_open: false,
			relocation_cities: ["Austin", "Denver"],
			prefer_no_salary: true,
			minimum_base_salary: "",
			salary_currency: "USD",
			visa_sponsorship_required: false,
			industry_exclusions: [],
			company_size_preference: "No Preference",
			max_travel_percent: "None",
		});

		expect(result.relocation_cities).toEqual([]);
	});

	it("sends null salary when prefer_no_salary is true", () => {
		const result = toRequestBody({
			remote_preference: "No Preference",
			commutable_cities: [],
			max_commute_minutes: "",
			relocation_open: false,
			relocation_cities: [],
			prefer_no_salary: true,
			minimum_base_salary: "100000",
			salary_currency: "USD",
			visa_sponsorship_required: false,
			industry_exclusions: [],
			company_size_preference: "No Preference",
			max_travel_percent: "None",
		});

		expect(result.minimum_base_salary).toBeNull();
	});

	it("sends null for empty string number fields", () => {
		const result = toRequestBody({
			remote_preference: "Hybrid OK",
			commutable_cities: [],
			max_commute_minutes: "",
			relocation_open: false,
			relocation_cities: [],
			prefer_no_salary: false,
			minimum_base_salary: "",
			salary_currency: "USD",
			visa_sponsorship_required: false,
			industry_exclusions: [],
			company_size_preference: "No Preference",
			max_travel_percent: "None",
		});

		expect(result.max_commute_minutes).toBeNull();
		expect(result.minimum_base_salary).toBeNull();
	});
});
