/**
 * Tests for shared voice profile helper functions.
 *
 * REQ-012 §7.2.6: Verify conversion between API VoiceProfile entities,
 * form values, and request bodies.
 */

import { describe, expect, it } from "vitest";

import type { VoiceProfile } from "@/types/persona";

import { toFormValues, toRequestBody } from "./voice-profile-helpers";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MOCK_TONE = "Direct and confident";
const MOCK_STYLE = "Short sentences, active voice";
const MOCK_VOCAB = "Technical when relevant, plain otherwise";
const MOCK_PERSONALITY = "Occasional dry humor";
const MOCK_PHRASES = ["I led the effort", "The result was"];
const MOCK_AVOID = ["Passionate", "Synergy"];
const MOCK_SAMPLE_TEXT = "Here is how I write...";

const MOCK_PROFILE: VoiceProfile = {
	id: "vp-001",
	persona_id: "p-001",
	tone: MOCK_TONE,
	sentence_style: MOCK_STYLE,
	vocabulary_level: MOCK_VOCAB,
	personality_markers: MOCK_PERSONALITY,
	sample_phrases: MOCK_PHRASES,
	things_to_avoid: MOCK_AVOID,
	writing_sample_text: MOCK_SAMPLE_TEXT,
	created_at: "2026-01-01T00:00:00Z",
	updated_at: "2026-01-01T00:00:00Z",
};

// ---------------------------------------------------------------------------
// toFormValues
// ---------------------------------------------------------------------------

describe("toFormValues", () => {
	it("converts a full VoiceProfile to form values", () => {
		const result = toFormValues(MOCK_PROFILE);

		expect(result).toEqual({
			tone: MOCK_TONE,
			sentence_style: MOCK_STYLE,
			vocabulary_level: MOCK_VOCAB,
			personality_markers: MOCK_PERSONALITY,
			sample_phrases: MOCK_PHRASES,
			things_to_avoid: MOCK_AVOID,
			writing_sample_text: MOCK_SAMPLE_TEXT,
		});
	});

	it("converts null optional fields to empty strings", () => {
		const profileWithNulls: VoiceProfile = {
			...MOCK_PROFILE,
			personality_markers: null,
			writing_sample_text: null,
		};

		const result = toFormValues(profileWithNulls);

		expect(result.personality_markers).toBe("");
		expect(result.writing_sample_text).toBe("");
	});

	it("preserves empty arrays for tag fields", () => {
		const profileNoTags: VoiceProfile = {
			...MOCK_PROFILE,
			sample_phrases: [],
			things_to_avoid: [],
		};

		const result = toFormValues(profileNoTags);

		expect(result.sample_phrases).toEqual([]);
		expect(result.things_to_avoid).toEqual([]);
	});

	it("does not include non-form fields like id and persona_id", () => {
		const result = toFormValues(MOCK_PROFILE);

		expect(result).not.toHaveProperty("id");
		expect(result).not.toHaveProperty("persona_id");
		expect(result).not.toHaveProperty("created_at");
		expect(result).not.toHaveProperty("updated_at");
	});
});

// ---------------------------------------------------------------------------
// toRequestBody
// ---------------------------------------------------------------------------

describe("toRequestBody", () => {
	it("converts form data to request body", () => {
		const result = toRequestBody({
			tone: MOCK_TONE,
			sentence_style: MOCK_STYLE,
			vocabulary_level: MOCK_VOCAB,
			personality_markers: MOCK_PERSONALITY,
			sample_phrases: MOCK_PHRASES,
			things_to_avoid: MOCK_AVOID,
			writing_sample_text: MOCK_SAMPLE_TEXT,
		});

		expect(result).toEqual({
			tone: MOCK_TONE,
			sentence_style: MOCK_STYLE,
			vocabulary_level: MOCK_VOCAB,
			personality_markers: MOCK_PERSONALITY,
			sample_phrases: MOCK_PHRASES,
			things_to_avoid: MOCK_AVOID,
			writing_sample_text: MOCK_SAMPLE_TEXT,
		});
	});

	it("converts empty optional strings to null", () => {
		const result = toRequestBody({
			tone: MOCK_TONE,
			sentence_style: MOCK_STYLE,
			vocabulary_level: MOCK_VOCAB,
			personality_markers: "",
			sample_phrases: [],
			things_to_avoid: [],
			writing_sample_text: "",
		});

		expect(result.personality_markers).toBeNull();
		expect(result.writing_sample_text).toBeNull();
	});

	it("preserves array fields as-is", () => {
		const result = toRequestBody({
			tone: MOCK_TONE,
			sentence_style: MOCK_STYLE,
			vocabulary_level: MOCK_VOCAB,
			personality_markers: "",
			sample_phrases: MOCK_PHRASES,
			things_to_avoid: MOCK_AVOID,
			writing_sample_text: "",
		});

		expect(result.sample_phrases).toEqual(MOCK_PHRASES);
		expect(result.things_to_avoid).toEqual(MOCK_AVOID);
	});
});
