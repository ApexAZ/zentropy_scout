/**
 * Tests for diff utilities used by the variant review page (§8.6).
 *
 * REQ-012 §9.3: Changed text highlighted with color. Moved bullets
 * shown with position indicators.
 */

import { describe, expect, it } from "vitest";

import { computeBulletMoves, computeWordDiff } from "./diff-utils";

// ---------------------------------------------------------------------------
// computeWordDiff
// ---------------------------------------------------------------------------

describe("computeWordDiff", () => {
	it("returns all same tokens for identical strings", () => {
		const tokens = computeWordDiff("hello world", "hello world");
		expect(tokens).toEqual([
			{ text: "hello", type: "same" },
			{ text: "world", type: "same" },
		]);
	});

	it("marks removed words from base and added words in variant", () => {
		const tokens = computeWordDiff("the quick fox", "the fast fox");
		expect(tokens).toEqual([
			{ text: "the", type: "same" },
			{ text: "quick", type: "removed" },
			{ text: "fast", type: "added" },
			{ text: "fox", type: "same" },
		]);
	});

	it("handles words added at the end", () => {
		const tokens = computeWordDiff("hello", "hello world");
		expect(tokens).toEqual([
			{ text: "hello", type: "same" },
			{ text: "world", type: "added" },
		]);
	});

	it("handles words removed from the end", () => {
		const tokens = computeWordDiff("hello world", "hello");
		expect(tokens).toEqual([
			{ text: "hello", type: "same" },
			{ text: "world", type: "removed" },
		]);
	});

	it("handles completely different strings", () => {
		const tokens = computeWordDiff("alpha beta", "gamma delta");
		expect(tokens).toEqual([
			{ text: "alpha", type: "removed" },
			{ text: "beta", type: "removed" },
			{ text: "gamma", type: "added" },
			{ text: "delta", type: "added" },
		]);
	});

	it("returns empty array for two empty strings", () => {
		const tokens = computeWordDiff("", "");
		expect(tokens).toEqual([]);
	});

	it("handles base empty and variant non-empty", () => {
		const tokens = computeWordDiff("", "new text");
		expect(tokens).toEqual([
			{ text: "new", type: "added" },
			{ text: "text", type: "added" },
		]);
	});

	it("handles base non-empty and variant empty", () => {
		const tokens = computeWordDiff("old text", "");
		expect(tokens).toEqual([
			{ text: "old", type: "removed" },
			{ text: "text", type: "removed" },
		]);
	});

	it("handles multi-word insertion in the middle", () => {
		const tokens = computeWordDiff(
			"Experienced with management",
			"Experienced with scaled Agile management",
		);
		expect(tokens).toEqual([
			{ text: "Experienced", type: "same" },
			{ text: "with", type: "same" },
			{ text: "scaled", type: "added" },
			{ text: "Agile", type: "added" },
			{ text: "management", type: "same" },
		]);
	});

	it("handles multi-word replacement", () => {
		const tokens = computeWordDiff(
			"8 years of project management",
			"8 years of scaled Agile leadership",
		);
		expect(tokens).toEqual([
			{ text: "8", type: "same" },
			{ text: "years", type: "same" },
			{ text: "of", type: "same" },
			{ text: "project", type: "removed" },
			{ text: "management", type: "removed" },
			{ text: "scaled", type: "added" },
			{ text: "Agile", type: "added" },
			{ text: "leadership", type: "added" },
		]);
	});
});

// ---------------------------------------------------------------------------
// computeBulletMoves
// ---------------------------------------------------------------------------

describe("computeBulletMoves", () => {
	it("returns empty map when order is unchanged", () => {
		const moves = computeBulletMoves(["a", "b", "c"], ["a", "b", "c"]);
		expect(moves.size).toBe(0);
	});

	it("detects all bullets that changed position", () => {
		const moves = computeBulletMoves(["a", "b", "c"], ["c", "a", "b"]);
		// c: was at index 2 (1-based: 3), now at index 0 — moved
		expect(moves.get("c")).toBe(3);
		// a: was at index 0 (1-based: 1), now at index 1 — moved
		expect(moves.get("a")).toBe(1);
		// b: was at index 1 (1-based: 2), now at index 2 — moved
		expect(moves.get("b")).toBe(2);
	});

	it("returns 1-based original positions for all moved bullets", () => {
		const moves = computeBulletMoves(
			["b-1", "b-2", "b-3"],
			["b-3", "b-1", "b-2"],
		);
		// b-3: was at index 2 (1-based: 3), now at index 0 — moved
		expect(moves.get("b-3")).toBe(3);
		// b-1: was at index 0 (1-based: 1), now at index 1 — moved
		expect(moves.get("b-1")).toBe(1);
		// b-2: was at index 1 (1-based: 2), now at index 2 — moved
		expect(moves.get("b-2")).toBe(2);
	});

	it("returns empty map for both empty arrays", () => {
		const moves = computeBulletMoves([], []);
		expect(moves.size).toBe(0);
	});

	it("ignores bullets in variant that are not in base", () => {
		const moves = computeBulletMoves(["a", "b"], ["a", "b", "c"]);
		// c is new — no original position
		expect(moves.has("c")).toBe(false);
		// a and b are unchanged
		expect(moves.size).toBe(0);
	});

	it("tracks bullets removed from variant correctly", () => {
		// If base has ["a", "b", "c"] and variant has ["a", "c"],
		// a stayed at position 0→0 (same), c moved from 2→1
		const moves = computeBulletMoves(["a", "b", "c"], ["a", "c"]);
		expect(moves.get("c")).toBe(3); // was at 1-based position 3, now at 2
		expect(moves.has("a")).toBe(false); // stayed at same position
	});
});
