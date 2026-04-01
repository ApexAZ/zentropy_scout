"use client";

/**
 * @fileoverview Education editor page route.
 *
 * Layer: page
 * Feature: persona
 *
 * REQ-012 §7.2.3: Post-onboarding editor for education entries
 * with CRUD and reordering. Only rendered for onboarded users.
 *
 * Coordinates with:
 * - components/persona/education-editor.tsx: editor UI component
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /persona/education
 */

import { EducationEditor } from "@/components/persona/education-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function EducationPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <EducationEditor persona={personaStatus.persona} />;
}
