import { describe, expect, it } from "vitest";

import { queryKeys } from "./query-keys";

// ---------------------------------------------------------------------------
// Test constants
// ---------------------------------------------------------------------------

const TEST_UUID = "550e8400-e29b-41d4-a716-446655440000";
const TYPEOF_STRING = "string";

// ---------------------------------------------------------------------------
// queryKeys — shape and immutability
// ---------------------------------------------------------------------------

describe("queryKeys", () => {
	describe("list keys (no arguments)", () => {
		it("returns ['personas'] for personas", () => {
			expect(queryKeys.personas).toEqual(["personas"]);
		});

		it("returns ['jobs'] for jobs", () => {
			expect(queryKeys.jobs).toEqual(["jobs"]);
		});

		it("returns ['applications'] for applications", () => {
			expect(queryKeys.applications).toEqual(["applications"]);
		});

		it("returns ['resumes'] for resumes", () => {
			expect(queryKeys.resumes).toEqual(["resumes"]);
		});

		it("returns ['variants'] for variants", () => {
			expect(queryKeys.variants).toEqual(["variants"]);
		});

		it("returns ['cover-letters'] for coverLetters", () => {
			expect(queryKeys.coverLetters).toEqual(["cover-letters"]);
		});

		it("returns ['change-flags'] for changeFlags", () => {
			expect(queryKeys.changeFlags).toEqual(["change-flags"]);
		});
	});

	describe("detail keys (with id argument)", () => {
		it("returns ['personas', id] for persona(id)", () => {
			expect(queryKeys.persona(TEST_UUID)).toEqual(["personas", TEST_UUID]);
		});

		it("returns ['jobs', id] for job(id)", () => {
			expect(queryKeys.job(TEST_UUID)).toEqual(["jobs", TEST_UUID]);
		});

		it("returns ['applications', id] for application(id)", () => {
			expect(queryKeys.application(TEST_UUID)).toEqual([
				"applications",
				TEST_UUID,
			]);
		});
	});

	describe("detail key structure", () => {
		it("detail key starts with list key prefix for personas", () => {
			const listKey = queryKeys.personas;
			const detailKey = queryKeys.persona(TEST_UUID);
			expect(detailKey[0]).toBe(listKey[0]);
		});

		it("detail key starts with list key prefix for jobs", () => {
			const listKey = queryKeys.jobs;
			const detailKey = queryKeys.job(TEST_UUID);
			expect(detailKey[0]).toBe(listKey[0]);
		});

		it("detail key starts with list key prefix for applications", () => {
			const listKey = queryKeys.applications;
			const detailKey = queryKeys.application(TEST_UUID);
			expect(detailKey[0]).toBe(listKey[0]);
		});
	});

	describe("type safety", () => {
		it("list keys are readonly tuples", () => {
			// If these were mutable arrays, spreading and modifying would
			// change the original — readonly prevents this at compile time.
			// At runtime we verify the shape is correct.
			const key = queryKeys.personas;
			expect(key).toHaveLength(1);
			expect(typeof key[0]).toBe(TYPEOF_STRING);
		});

		it("detail keys are readonly tuples with two elements", () => {
			const key = queryKeys.persona(TEST_UUID);
			expect(key).toHaveLength(2);
			expect(typeof key[0]).toBe(TYPEOF_STRING);
			expect(typeof key[1]).toBe(TYPEOF_STRING);
		});

		it("different ids produce different detail keys", () => {
			const id1 = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
			const id2 = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";
			expect(queryKeys.persona(id1)).not.toEqual(queryKeys.persona(id2));
		});
	});
});
