"use client";

/**
 * PersonaChangeFlags resolution page route.
 *
 * REQ-012 §7.6: Review and resolve pending change flags
 * (add to all resumes, add to some, or skip). Only rendered
 * for onboarded users.
 */

import { ChangeFlagsResolver } from "@/components/persona/change-flags-resolver";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function ChangeFlagsPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <ChangeFlagsResolver />;
}
