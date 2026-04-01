"use client";

/**
 * @fileoverview Growth targets editor page route.
 *
 * Layer: page
 * Feature: persona
 *
 * REQ-012 §7.2.8: Post-onboarding editor for growth targets
 * with tag inputs and stretch appetite radio group.
 * Only rendered for onboarded users.
 *
 * Coordinates with:
 * - components/persona/growth-targets-editor.tsx: editor UI component
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /persona/growth
 */

import { GrowthTargetsEditor } from "@/components/persona/growth-targets-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function GrowthTargetsPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <GrowthTargetsEditor persona={personaStatus.persona} />;
}
