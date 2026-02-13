/**
 * Tests for shared skill helper functions.
 *
 * REQ-012 §7.2.4: Verify conversion between API Skill entities,
 * form values, and request bodies.
 */

import { describe, expect, it } from "vitest";

import type { Skill } from "@/types/persona";

import { toFormValues, toRequestBody } from "./skills-helpers";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const MOCK_CATEGORY_HARD = "Programming Language";
const MOCK_CATEGORY_SOFT = "Leadership & Management";
const MOCK_LAST_USED_CURRENT = "Current";

const MOCK_ENTRY: Skill = {
	id: "skill-001",
	persona_id: "p-001",
	skill_name: "Python",
	skill_type: "Hard",
	category: MOCK_CATEGORY_HARD,
	proficiency: "Expert",
	years_used: 8,
	last_used: MOCK_LAST_USED_CURRENT,
	display_order: 0,
};

// ---------------------------------------------------------------------------
// toFormValues
// ---------------------------------------------------------------------------

describe("toFormValues", () => {
	it("converts a full Skill entry to form values", () => {
		const result = toFormValues(MOCK_ENTRY);

		expect(result).toEqual({
			skill_name: MOCK_ENTRY.skill_name,
			skill_type: MOCK_ENTRY.skill_type,
			category: MOCK_ENTRY.category,
			proficiency: MOCK_ENTRY.proficiency,
			years_used: String(MOCK_ENTRY.years_used),
			last_used: MOCK_ENTRY.last_used,
		});
	});

	it("converts years_used number to string", () => {
		const entry: Skill = { ...MOCK_ENTRY, years_used: 1 };
		const result = toFormValues(entry);

		expect(result.years_used).toBe("1");
	});

	it("preserves Soft skill type and category", () => {
		const softEntry: Skill = {
			...MOCK_ENTRY,
			skill_type: "Soft",
			category: MOCK_CATEGORY_SOFT,
		};
		const result = toFormValues(softEntry);

		expect(result.skill_type).toBe("Soft");
		expect(result.category).toBe(MOCK_CATEGORY_SOFT);
	});
});

// ---------------------------------------------------------------------------
// toRequestBody
// ---------------------------------------------------------------------------

describe("toRequestBody", () => {
	it("converts form data to request body with numeric years_used", () => {
		const result = toRequestBody({
			skill_name: "JavaScript",
			skill_type: "Hard",
			category: MOCK_CATEGORY_HARD,
			proficiency: "Proficient",
			years_used: "5",
			last_used: MOCK_LAST_USED_CURRENT,
		});

		expect(result).toEqual({
			skill_name: "JavaScript",
			skill_type: "Hard",
			category: MOCK_CATEGORY_HARD,
			proficiency: "Proficient",
			years_used: 5,
			last_used: MOCK_LAST_USED_CURRENT,
		});
	});

	it("parses years_used string to integer", () => {
		const result = toRequestBody({
			skill_name: "Leadership",
			skill_type: "Soft",
			category: MOCK_CATEGORY_SOFT,
			proficiency: "Expert",
			years_used: "12",
			last_used: "2024",
		});

		expect(result.years_used).toBe(12);
		expect(typeof result.years_used).toBe("number");
	});

	it("preserves last_used year string", () => {
		const result = toRequestBody({
			skill_name: "Go",
			skill_type: "Hard",
			category: MOCK_CATEGORY_HARD,
			proficiency: "Learning",
			years_used: "1",
			last_used: "2023",
		});

		expect(result.last_used).toBe("2023");
	});
});
