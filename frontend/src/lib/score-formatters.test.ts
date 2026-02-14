/**
 * Tests for shared score formatting utilities.
 *
 * REQ-008 §4.1: Fit score component display formatting.
 */

import { describe, expect, it } from "vitest";

import { FIT_COMPONENT_ORDER, formatComponentLabel } from "./score-formatters";

// ---------------------------------------------------------------------------
// formatComponentLabel
// ---------------------------------------------------------------------------

describe("formatComponentLabel", () => {
	it("converts hard_skills to 'Hard Skills'", () => {
		expect(formatComponentLabel("hard_skills")).toBe("Hard Skills");
	});

	it("converts experience_level to 'Experience Level'", () => {
		expect(formatComponentLabel("experience_level")).toBe("Experience Level");
	});

	it("converts location_logistics to 'Location Logistics'", () => {
		expect(formatComponentLabel("location_logistics")).toBe(
			"Location Logistics",
		);
	});

	it("handles single word", () => {
		expect(formatComponentLabel("skills")).toBe("Skills");
	});
});

// ---------------------------------------------------------------------------
// FIT_COMPONENT_ORDER
// ---------------------------------------------------------------------------

describe("FIT_COMPONENT_ORDER", () => {
	it("contains all 5 fit score components", () => {
		expect(FIT_COMPONENT_ORDER).toHaveLength(5);
	});

	it("has hard_skills first (highest weight)", () => {
		expect(FIT_COMPONENT_ORDER[0]).toBe("hard_skills");
	});

	it("has location_logistics last (lowest weight)", () => {
		expect(FIT_COMPONENT_ORDER[4]).toBe("location_logistics");
	});
});
