/**
 * Shared helpers for achievement story forms (onboarding + post-onboarding editor).
 *
 * REQ-012 §7.2.5: Conversion utilities between API AchievementStory
 * entities, form values, and request bodies.
 */

import type { StoryFormData } from "@/components/onboarding/steps/story-form";
import type { AchievementStory } from "@/types/persona";

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
