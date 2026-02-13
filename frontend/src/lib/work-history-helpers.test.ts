/**
 * Tests for shared work history helper functions.
 *
 * REQ-012 §7.2.2: Verify conversion between API WorkHistory,
 * form values, and request bodies.
 */

import { describe, expect, it } from "vitest";

import type { WorkHistory } from "@/types/persona";

import { toFormValues, toIsoDate, toRequestBody } from "./work-history-helpers";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const MOCK_ENTRY: WorkHistory = {
	id: "wh-001",
	persona_id: "p-001",
	job_title: "Software Engineer",
	company_name: "Acme Corp",
	company_industry: "Technology",
	location: "San Francisco, CA",
	work_model: "Remote",
	start_date: "2020-01-01",
	end_date: "2023-06-01",
	is_current: false,
	description: "Built web applications",
	display_order: 0,
	bullets: [],
};

// ---------------------------------------------------------------------------
// toIsoDate
// ---------------------------------------------------------------------------

describe("toIsoDate", () => {
	it("converts YYYY-MM to YYYY-MM-01", () => {
		expect(toIsoDate("2020-01")).toBe("2020-01-01");
	});

	it("returns empty string for empty input", () => {
		expect(toIsoDate("")).toBe("");
	});
});

// ---------------------------------------------------------------------------
// toFormValues
// ---------------------------------------------------------------------------

describe("toFormValues", () => {
	it("converts a full WorkHistory entry to form values", () => {
		const result = toFormValues(MOCK_ENTRY);

		expect(result).toEqual({
			job_title: "Software Engineer",
			company_name: "Acme Corp",
			company_industry: "Technology",
			location: "San Francisco, CA",
			work_model: "Remote",
			start_date: "2020-01",
			end_date: "2023-06",
			is_current: false,
			description: "Built web applications",
		});
	});

	it("converts null optional fields to empty strings", () => {
		const entryWithNulls: WorkHistory = {
			...MOCK_ENTRY,
			company_industry: null,
			end_date: null,
			description: null,
			is_current: true,
		};

		const result = toFormValues(entryWithNulls);

		expect(result.company_industry).toBe("");
		expect(result.end_date).toBe("");
		expect(result.description).toBe("");
		expect(result.is_current).toBe(true);
	});
});

// ---------------------------------------------------------------------------
// toRequestBody
// ---------------------------------------------------------------------------

describe("toRequestBody", () => {
	it("converts form data to request body with ISO dates", () => {
		const result = toRequestBody({
			job_title: "QA Engineer",
			company_name: "TestCorp",
			company_industry: "Tech",
			location: "Austin, TX",
			work_model: "Remote",
			start_date: "2024-01",
			end_date: "2024-06",
			is_current: false,
			description: "Testing things",
		});

		expect(result).toEqual({
			job_title: "QA Engineer",
			company_name: "TestCorp",
			company_industry: "Tech",
			location: "Austin, TX",
			work_model: "Remote",
			start_date: "2024-01-01",
			end_date: "2024-06-01",
			is_current: false,
			description: "Testing things",
		});
	});

	it("sets end_date to null when is_current is true", () => {
		const result = toRequestBody({
			job_title: "QA Engineer",
			company_name: "TestCorp",
			company_industry: "",
			location: "Austin, TX",
			work_model: "Remote",
			start_date: "2024-01",
			end_date: "",
			is_current: true,
			description: "",
		});

		expect(result.end_date).toBeNull();
		expect(result.is_current).toBe(true);
	});

	it("converts empty optional strings to null", () => {
		const result = toRequestBody({
			job_title: "QA Engineer",
			company_name: "TestCorp",
			company_industry: "",
			location: "Austin, TX",
			work_model: "Remote",
			start_date: "2024-01",
			end_date: "2024-06",
			is_current: false,
			description: "",
		});

		expect(result.company_industry).toBeNull();
		expect(result.description).toBeNull();
	});
});
