/**
 * Shared helpers for achievement story forms (onboarding + post-onboarding editor).
 *
 * REQ-012 §7.2.5: Conversion utilities between API AchievementStory
 * entities, form values, and request bodies.
 */

import { z } from "zod";

import type { AchievementStory } from "@/types/persona";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_TITLE_LENGTH = 255;
const MAX_TEXT_LENGTH = 5000;

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

export const storyFormSchema = z.object({
	title: z
		.string()
		.min(1, { message: "Title is required" })
		.max(MAX_TITLE_LENGTH, { message: "Title is too long" }),
	context: z
		.string()
		.min(1, { message: "Context is required" })
		.max(MAX_TEXT_LENGTH, { message: "Context is too long" }),
	action: z
		.string()
		.min(1, { message: "Action is required" })
		.max(MAX_TEXT_LENGTH, { message: "Action is too long" }),
	outcome: z
		.string()
		.min(1, { message: "Outcome is required" })
		.max(MAX_TEXT_LENGTH, { message: "Outcome is too long" }),
	skills_demonstrated: z
		.array(z.uuid({ message: "Invalid skill ID" }))
		.max(50, { message: "Too many skills selected" }),
});

export type StoryFormData = z.infer<typeof storyFormSchema>;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Shape of the request body sent to the achievement stories API. */
export interface AchievementStoryRequestBody {
	title: string;
	context: string;
	action: string;
	outcome: string;
	skills_demonstrated: string[];
}

// ---------------------------------------------------------------------------
// Conversion functions
// ---------------------------------------------------------------------------

/** Convert an AchievementStory entry to form initial values. */
export function toFormValues(entry: AchievementStory): Partial<StoryFormData> {
	return {
		title: entry.title,
		context: entry.context,
		action: entry.action,
		outcome: entry.outcome,
		skills_demonstrated: entry.skills_demonstrated,
	};
}

/** Convert form data to API request body. */
export function toRequestBody(
	data: StoryFormData,
): AchievementStoryRequestBody {
	return {
		title: data.title,
		context: data.context,
		action: data.action,
		outcome: data.outcome,
		skills_demonstrated: data.skills_demonstrated,
	};
}
