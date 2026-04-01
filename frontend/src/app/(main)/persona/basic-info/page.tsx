"use client";

/**
 * @fileoverview Basic info editor page route.
 *
 * Layer: page
 * Feature: persona
 *
 * REQ-012 §7.2.1: Post-onboarding editor for basic info and
 * professional overview fields. Only rendered for onboarded users.
 *
 * Coordinates with:
 * - components/persona/basic-info-editor.tsx: editor UI component
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /persona/basic-info
 */

import { BasicInfoEditor } from "@/components/persona/basic-info-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function BasicInfoPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <BasicInfoEditor persona={personaStatus.persona} />;
}
