"use client";

/**
 * @fileoverview Voice profile editor page route.
 *
 * Layer: page
 * Feature: persona
 *
 * REQ-012 §7.2.6: Post-onboarding editor for voice profile
 * with text fields, tag inputs, and optional textarea.
 * Only rendered for onboarded users.
 *
 * Coordinates with:
 * - components/persona/voice-profile-editor.tsx: editor UI component
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /persona/voice-profile
 */

import { VoiceProfileEditor } from "@/components/persona/voice-profile-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function VoiceProfilePage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <VoiceProfileEditor persona={personaStatus.persona} />;
}
