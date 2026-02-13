/**
 * Tests for shared education helper functions.
 *
 * REQ-012 §7.2.3: Verify conversion between API Education entities,
 * form values, and request bodies.
 */

import { describe, expect, it } from "vitest";

import type { Education } from "@/types/persona";

import { toFormValues, toRequestBody } from "./education-helpers";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const MOCK_ENTRY: Education = {
	id: "ed-001",
	persona_id: "p-001",
	institution: "MIT",
	degree: "Bachelor of Science",
	field_of_study: "Computer Science",
	graduation_year: 2020,
	gpa: 3.8,
	honors: "Magna Cum Laude",
	display_order: 0,
};

// ---------------------------------------------------------------------------
// toFormValues
// ---------------------------------------------------------------------------

describe("toFormValues", () => {
	it("converts a full Education entry to form values", () => {
		const result = toFormValues(MOCK_ENTRY);

		expect(result).toEqual({
			institution: "MIT",
			degree: "Bachelor of Science",
			field_of_study: "Computer Science",
			graduation_year: "2020",
			gpa: "3.8",
			honors: "Magna Cum Laude",
		});
	});

	it("converts null optional fields to empty strings", () => {
		const entryWithNulls: Education = {
			...MOCK_ENTRY,
			gpa: null,
			honors: null,
		};

		const result = toFormValues(entryWithNulls);

		expect(result.gpa).toBe("");
		expect(result.honors).toBe("");
	});
});

// ---------------------------------------------------------------------------
// toRequestBody
// ---------------------------------------------------------------------------

describe("toRequestBody", () => {
	it("converts form data to request body with numeric types", () => {
		const result = toRequestBody({
			institution: "Stanford",
			degree: "Master of Science",
			field_of_study: "AI",
			graduation_year: "2023",
			gpa: "3.95",
			honors: "With Distinction",
		});

		expect(result).toEqual({
			institution: "Stanford",
			degree: "Master of Science",
			field_of_study: "AI",
			graduation_year: 2023,
			gpa: 3.95,
			honors: "With Distinction",
		});
	});

	it("converts empty optional strings to null", () => {
		const result = toRequestBody({
			institution: "Stanford",
			degree: "Master of Science",
			field_of_study: "AI",
			graduation_year: "2023",
			gpa: "",
			honors: "",
		});

		expect(result.gpa).toBeNull();
		expect(result.honors).toBeNull();
	});

	it("converts undefined gpa to null", () => {
		const result = toRequestBody({
			institution: "Stanford",
			degree: "Master of Science",
			field_of_study: "AI",
			graduation_year: "2023",
		});

		expect(result.gpa).toBeNull();
		expect(result.honors).toBeNull();
	});
});
