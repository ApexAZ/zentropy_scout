"use client";

/**
 * @fileoverview Achievement stories editor page route.
 *
 * Layer: page
 * Feature: persona
 *
 * REQ-012 §7.2.5: Post-onboarding editor for achievement story
 * entries with C/A/O, skill links, and reordering.
 * Only rendered for onboarded users.
 *
 * Coordinates with:
 * - components/persona/achievement-stories-editor.tsx: editor UI component
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /persona/achievement-stories
 */

import { AchievementStoriesEditor } from "@/components/persona/achievement-stories-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function AchievementStoriesPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <AchievementStoriesEditor persona={personaStatus.persona} />;
}
