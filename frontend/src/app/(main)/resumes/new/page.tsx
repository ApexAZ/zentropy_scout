"use client";

/**
 * @fileoverview New resume creation wizard page route.
 *
 * Layer: page
 * Feature: resume
 *
 * REQ-012 §9.2, §6.3.12: Resume creation wizard at /resumes/new.
 * Only rendered for onboarded users (OnboardingGate in parent layout).
 *
 * Coordinates with:
 * - components/resume/new-resume-wizard.tsx: wizard UI component
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /resumes/new
 */

import { NewResumeWizard } from "@/components/resume/new-resume-wizard";
import { usePersonaStatus } from "@/hooks/use-persona-status";

/** New resume page — renders creation wizard for base resume. */
export default function NewResumePage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <NewResumeWizard personaId={personaStatus.persona.id} />;
}
