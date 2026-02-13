"use client";

/**
 * Certifications editor page route.
 *
 * REQ-012 §7.2.3: Post-onboarding editor for certification entries
 * with CRUD, reordering, and "Does not expire" toggle. Only rendered
 * for onboarded users.
 */

import { CertificationEditor } from "@/components/persona/certification-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function CertificationsPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <CertificationEditor persona={personaStatus.persona} />;
}
