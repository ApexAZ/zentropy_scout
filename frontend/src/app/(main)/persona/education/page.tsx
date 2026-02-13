"use client";

/**
 * Education editor page route.
 *
 * REQ-012 §7.2.3: Post-onboarding editor for education entries
 * with CRUD and reordering. Only rendered for onboarded users.
 */

import { EducationEditor } from "@/components/persona/education-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function EducationPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <EducationEditor persona={personaStatus.persona} />;
}
