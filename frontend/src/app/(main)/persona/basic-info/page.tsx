"use client";

/**
 * Basic info editor page route.
 *
 * REQ-012 §7.2.1: Post-onboarding editor for basic info and
 * professional overview fields. Only rendered for onboarded users.
 */

import { BasicInfoEditor } from "@/components/persona/basic-info-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function BasicInfoPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <BasicInfoEditor persona={personaStatus.persona} />;
}
