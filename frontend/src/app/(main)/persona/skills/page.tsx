"use client";

/**
 * Skills editor page route.
 *
 * REQ-012 §7.2.4: Post-onboarding editor for skill entries
 * with Hard/Soft tabs, CRUD, and per-type reordering. Only
 * rendered for onboarded users.
 */

import { SkillsEditor } from "@/components/persona/skills-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function SkillsPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <SkillsEditor persona={personaStatus.persona} />;
}
