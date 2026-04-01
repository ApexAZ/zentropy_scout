"use client";

/**
 * @fileoverview Work history editor page route.
 *
 * Layer: page
 * Feature: persona
 *
 * REQ-012 §7.2.2: Post-onboarding editor for work history
 * entries with CRUD and reordering. Only rendered for onboarded users.
 *
 * Coordinates with:
 * - components/persona/work-history-editor.tsx: editor UI component
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /persona/work-history
 */

import { WorkHistoryEditor } from "@/components/persona/work-history-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function WorkHistoryPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <WorkHistoryEditor persona={personaStatus.persona} />;
}
