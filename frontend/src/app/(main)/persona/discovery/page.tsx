"use client";

/**
 * @fileoverview Discovery preferences editor page route.
 *
 * Layer: page
 * Feature: persona
 *
 * REQ-012 §7.2.9: Post-onboarding editor for discovery preferences
 * with threshold sliders and polling frequency select.
 * Only rendered for onboarded users.
 *
 * Coordinates with:
 * - components/persona/discovery-preferences-editor.tsx: editor UI component
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /persona/discovery
 */

import { DiscoveryPreferencesEditor } from "@/components/persona/discovery-preferences-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function DiscoveryPreferencesPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <DiscoveryPreferencesEditor persona={personaStatus.persona} />;
}
