"use client";

/**
 * Persona overview page route.
 *
 * REQ-012 §7.1: Hub for viewing professional profile and navigating
 * to section editors. Only rendered for onboarded users (OnboardingGate
 * in parent layout ensures this).
 */

import { PersonaOverview } from "@/components/persona/persona-overview";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function PersonaPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <PersonaOverview persona={personaStatus.persona} />;
}
