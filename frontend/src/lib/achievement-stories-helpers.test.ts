/**
 * Tests for shared achievement story helper functions.
 *
 * REQ-012 §7.2.5: Verify conversion between API AchievementStory
 * entities, form values, and request bodies.
 */

import { describe, expect, it } from "vitest";

import type { AchievementStory } from "@/types/persona";

import { toFormValues, toRequestBody } from "./achievement-stories-helpers";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const MOCK_TITLE = "Turned around failing project";
const MOCK_CONTEXT = "Team was behind schedule by 3 weeks";
const MOCK_ACTION = "Reorganized sprints and delegated tasks";
const MOCK_OUTCOME = "Delivered 2 weeks early with 98% test coverage";
const MOCK_SKILL_IDS = ["skill-001", "skill-002"];

const MOCK_ENTRY: AchievementStory = {
	id: "story-001",
	persona_id: "p-001",
	title: MOCK_TITLE,
	context: MOCK_CONTEXT,
	action: MOCK_ACTION,
	outcome: MOCK_OUTCOME,
	skills_demonstrated: MOCK_SKILL_IDS,
	related_job_id: "wh-001",
	display_order: 0,
};

// ---------------------------------------------------------------------------
// toFormValues
// ---------------------------------------------------------------------------

describe("toFormValues", () => {
	it("converts a full AchievementStory entry to form values", () => {
		const result = toFormValues(MOCK_ENTRY);

		expect(result).toEqual({
			title: MOCK_TITLE,
			context: MOCK_CONTEXT,
			action: MOCK_ACTION,
			outcome: MOCK_OUTCOME,
			skills_demonstrated: MOCK_SKILL_IDS,
		});
	});

	it("preserves empty skills_demonstrated array", () => {
		const entry: AchievementStory = {
			...MOCK_ENTRY,
			skills_demonstrated: [],
		};
		const result = toFormValues(entry);

		expect(result.skills_demonstrated).toEqual([]);
	});

	it("excludes non-form fields (id, persona_id, related_job_id, display_order)", () => {
		const result = toFormValues(MOCK_ENTRY);
		const keys = Object.keys(result);

		expect(keys).not.toContain("id");
		expect(keys).not.toContain("persona_id");
		expect(keys).not.toContain("related_job_id");
		expect(keys).not.toContain("display_order");
	});
});

// ---------------------------------------------------------------------------
// toRequestBody
// ---------------------------------------------------------------------------

describe("toRequestBody", () => {
	it("converts form data to request body", () => {
		const result = toRequestBody({
			title: MOCK_TITLE,
			context: MOCK_CONTEXT,
			action: MOCK_ACTION,
			outcome: MOCK_OUTCOME,
			skills_demonstrated: MOCK_SKILL_IDS,
		});

		expect(result).toEqual({
			title: MOCK_TITLE,
			context: MOCK_CONTEXT,
			action: MOCK_ACTION,
			outcome: MOCK_OUTCOME,
			skills_demonstrated: MOCK_SKILL_IDS,
		});
	});

	it("preserves empty skills_demonstrated array in request body", () => {
		const result = toRequestBody({
			title: MOCK_TITLE,
			context: MOCK_CONTEXT,
			action: MOCK_ACTION,
			outcome: MOCK_OUTCOME,
			skills_demonstrated: [],
		});

		expect(result.skills_demonstrated).toEqual([]);
	});
});
