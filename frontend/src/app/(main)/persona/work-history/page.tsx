"use client";

/**
 * Work history editor page route.
 *
 * REQ-012 §7.2.2: Post-onboarding editor for work history
 * entries with CRUD and reordering. Only rendered for onboarded users.
 */

import { WorkHistoryEditor } from "@/components/persona/work-history-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function WorkHistoryPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <WorkHistoryEditor persona={personaStatus.persona} />;
}
