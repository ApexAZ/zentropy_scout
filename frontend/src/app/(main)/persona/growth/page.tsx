"use client";

/**
 * Growth targets editor page route.
 *
 * REQ-012 §7.2.8: Post-onboarding editor for growth targets
 * with tag inputs and stretch appetite radio group.
 * Only rendered for onboarded users.
 */

import { GrowthTargetsEditor } from "@/components/persona/growth-targets-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function GrowthTargetsPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <GrowthTargetsEditor persona={personaStatus.persona} />;
}
