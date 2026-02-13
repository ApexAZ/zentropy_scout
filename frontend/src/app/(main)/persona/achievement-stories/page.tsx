"use client";

/**
 * Achievement stories editor page route.
 *
 * REQ-012 §7.2.5: Post-onboarding editor for achievement story
 * entries with C/A/O, skill links, and reordering.
 * Only rendered for onboarded users.
 */

import { AchievementStoriesEditor } from "@/components/persona/achievement-stories-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function AchievementStoriesPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <AchievementStoriesEditor persona={personaStatus.persona} />;
}
