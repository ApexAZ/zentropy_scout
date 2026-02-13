"use client";

/**
 * Discovery preferences editor page route.
 *
 * REQ-012 §7.2.9: Post-onboarding editor for discovery preferences
 * with threshold sliders and polling frequency select.
 * Only rendered for onboarded users.
 */

import { DiscoveryPreferencesEditor } from "@/components/persona/discovery-preferences-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function DiscoveryPreferencesPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <DiscoveryPreferencesEditor persona={personaStatus.persona} />;
}
