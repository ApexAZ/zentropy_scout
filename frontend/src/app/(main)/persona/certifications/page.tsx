"use client";

/**
 * @fileoverview Certifications editor page route.
 *
 * Layer: page
 * Feature: persona
 *
 * REQ-012 §7.2.3: Post-onboarding editor for certification entries
 * with CRUD, reordering, and "Does not expire" toggle. Only rendered
 * for onboarded users.
 *
 * Coordinates with:
 * - components/persona/certification-editor.tsx: editor UI component
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /persona/certifications
 */

import { CertificationEditor } from "@/components/persona/certification-editor";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function CertificationsPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <CertificationEditor persona={personaStatus.persona} />;
}
