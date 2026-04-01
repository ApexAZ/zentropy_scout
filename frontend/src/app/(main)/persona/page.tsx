"use client";

/**
 * @fileoverview Persona overview page — hub for viewing and navigating to editors.
 *
 * Layer: page
 * Feature: persona
 *
 * REQ-012 §7.1: Hub for viewing professional profile and navigating
 * to section editors. Only rendered for onboarded users (OnboardingGate
 * in parent layout ensures this).
 *
 * Coordinates with:
 * - components/persona/persona-overview.tsx: overview UI component
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /persona
 */

import { PersonaOverview } from "@/components/persona/persona-overview";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function PersonaPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <PersonaOverview persona={personaStatus.persona} />;
}
