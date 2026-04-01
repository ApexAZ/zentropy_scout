"use client";

/**
 * @fileoverview Skills editor page route.
 *
 * Layer: page
 * Feature: persona
 *
 * REQ-012 §7.2.4: Post-onboarding editor for skill entries
 * with Hard/Soft tabs, CRUD, and per-type reordering. Only
 * rendered for onboarded users.
 *
 * Coordinates with:
 * - components/persona/skills-editor.tsx: editor UI component
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /persona/skills
 */

import { SkillsEditor } from "@/components/persona/skills-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function SkillsPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <SkillsEditor persona={personaStatus.persona} />;
}
