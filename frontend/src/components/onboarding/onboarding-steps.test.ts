/**
 * Tests for onboarding step definitions.
 *
 * REQ-019 §7.1: 11-step onboarding wizard step metadata.
 */

import { describe, expect, it } from "vitest";

import {
	getStepByKey,
	getStepByNumber,
	ONBOARDING_STEPS,
	TOTAL_STEPS,
} from "./onboarding-steps";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ONBOARDING_STEPS", () => {
	it("has exactly 11 steps", () => {
		expect(ONBOARDING_STEPS).toHaveLength(11);
	});

	it("numbers steps 1 through 11 sequentially", () => {
		const numbers = ONBOARDING_STEPS.map((s) => s.number);
		expect(numbers).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]);
	});

	it("every step has key, name, number, and skippable fields", () => {
		for (const step of ONBOARDING_STEPS) {
			expect(typeof step.number).toBe("number");
			expect(typeof step.key).toBe("string");
			expect(typeof step.name).toBe("string");
			expect(typeof step.skippable).toBe("boolean");
			expect(step.key.length).toBeGreaterThan(0);
			expect(step.name.length).toBeGreaterThan(0);
		}
	});

	it("marks resume-upload, education, and certifications as skippable", () => {
		const skippable = ONBOARDING_STEPS.filter((s) => s.skippable).map(
			(s) => s.key,
		);
		expect(skippable).toEqual(["resume-upload", "education", "certifications"]);
	});

	it("has unique step keys", () => {
		const keys = ONBOARDING_STEPS.map((s) => s.key);
		expect(new Set(keys).size).toBe(keys.length);
	});
});

describe("TOTAL_STEPS", () => {
	it("equals 11", () => {
		expect(TOTAL_STEPS).toBe(11);
	});
});

describe("getStepByNumber", () => {
	it("returns the correct step for a valid number", () => {
		const step = getStepByNumber(5);
		expect(step).toEqual({
			number: 5,
			key: "skills",
			name: "Skills",
			skippable: false,
		});
	});

	it("returns the first step for number 1", () => {
		const step = getStepByNumber(1);
		expect(step?.key).toBe("resume-upload");
	});

	it("returns the last step for number 11", () => {
		const step = getStepByNumber(11);
		expect(step?.key).toBe("review");
	});

	it("returns undefined for number 0", () => {
		expect(getStepByNumber(0)).toBeUndefined();
	});

	it("returns undefined for number 12", () => {
		expect(getStepByNumber(12)).toBeUndefined();
	});

	it("returns undefined for negative numbers", () => {
		expect(getStepByNumber(-1)).toBeUndefined();
	});
});

describe("getStepByKey", () => {
	it("returns the correct step for a valid key", () => {
		const step = getStepByKey("work-history");
		expect(step).toEqual({
			number: 3,
			key: "work-history",
			name: "Work History",
			skippable: false,
		});
	});

	it("returns undefined for unknown key", () => {
		expect(getStepByKey("nonexistent")).toBeUndefined();
	});

	it("returns undefined for empty string", () => {
		expect(getStepByKey("")).toBeUndefined();
	});
});
