"use client";

/**
 * Non-negotiables editor page route.
 *
 * REQ-012 §7.2.7: Post-onboarding editor for non-negotiable fields
 * with conditional visibility, embedded custom filters CRUD.
 * Only rendered for onboarded users.
 */

import { NonNegotiablesEditor } from "@/components/persona/non-negotiables-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function NonNegotiablesPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <NonNegotiablesEditor persona={personaStatus.persona} />;
}
