/**
 * Shared helpers for voice profile forms (onboarding + post-onboarding editor).
 *
 * REQ-012 §7.2.6: Conversion utilities between API VoiceProfile
 * entities, form values, and request bodies. Also exports the shared
 * Zod validation schema and default form values.
 */

import { z } from "zod";

import type { VoiceProfile } from "@/types/persona";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Form data shape for voice profile forms. */
export interface VoiceProfileFormData {
	tone: string;
	sentence_style: string;
	vocabulary_level: string;
	personality_markers: string;
	sample_phrases: string[];
	things_to_avoid: string[];
	writing_sample_text: string;
}

/** Shape of the request body sent to the voice profile API. */
export interface VoiceProfileRequestBody {
	tone: string;
	sentence_style: string;
	vocabulary_level: string;
	personality_markers: string | null;
	sample_phrases: string[];
	things_to_avoid: string[];
	writing_sample_text: string | null;
}

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

export const voiceProfileSchema = z.object({
	tone: z.string().min(1, { message: "Tone is required" }).max(500),
	sentence_style: z.string().min(1, { message: "Style is required" }).max(500),
	vocabulary_level: z
		.string()
		.min(1, { message: "Vocabulary is required" })
		.max(500),
	personality_markers: z.string().max(500),
	sample_phrases: z.array(z.string().trim().min(1).max(200)).max(20),
	things_to_avoid: z.array(z.string().trim().min(1).max(200)).max(20),
	writing_sample_text: z.string().max(3000),
});

export const VOICE_PROFILE_DEFAULT_VALUES: VoiceProfileFormData = {
	tone: "",
	sentence_style: "",
	vocabulary_level: "",
	personality_markers: "",
	sample_phrases: [],
	things_to_avoid: [],
	writing_sample_text: "",
};

// ---------------------------------------------------------------------------
// Conversion functions
// ---------------------------------------------------------------------------

/** Convert a VoiceProfile entity to form initial values. */
export function toFormValues(profile: VoiceProfile): VoiceProfileFormData {
	return {
		tone: profile.tone ?? "",
		sentence_style: profile.sentence_style ?? "",
		vocabulary_level: profile.vocabulary_level ?? "",
		personality_markers: profile.personality_markers ?? "",
		sample_phrases: profile.sample_phrases ?? [],
		things_to_avoid: profile.things_to_avoid ?? [],
		writing_sample_text: profile.writing_sample_text ?? "",
	};
}

/** Convert form data to API request body. */
export function toRequestBody(
	data: VoiceProfileFormData,
): VoiceProfileRequestBody {
	return {
		tone: data.tone,
		sentence_style: data.sentence_style,
		vocabulary_level: data.vocabulary_level,
		personality_markers: data.personality_markers || null,
		sample_phrases: data.sample_phrases,
		things_to_avoid: data.things_to_avoid,
		writing_sample_text: data.writing_sample_text || null,
	};
}
