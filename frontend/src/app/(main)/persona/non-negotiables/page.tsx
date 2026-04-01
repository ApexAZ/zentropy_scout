"use client";

/**
 * @fileoverview Non-negotiables editor page route.
 *
 * Layer: page
 * Feature: persona
 *
 * REQ-012 §7.2.7: Post-onboarding editor for non-negotiable fields
 * with conditional visibility, embedded custom filters CRUD.
 * Only rendered for onboarded users.
 *
 * Coordinates with:
 * - components/persona/non-negotiables-editor.tsx: editor UI component
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /persona/non-negotiables
 */

import { NonNegotiablesEditor } from "@/components/persona/non-negotiables-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function NonNegotiablesPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <NonNegotiablesEditor persona={personaStatus.persona} />;
}
