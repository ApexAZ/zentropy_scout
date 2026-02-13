"use client";

/**
 * Voice profile editor page route.
 *
 * REQ-012 §7.2.6: Post-onboarding editor for voice profile
 * with text fields, tag inputs, and optional textarea.
 * Only rendered for onboarded users.
 */

import { VoiceProfileEditor } from "@/components/persona/voice-profile-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function VoiceProfilePage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <VoiceProfileEditor persona={personaStatus.persona} />;
}
