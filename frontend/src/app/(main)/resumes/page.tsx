"use client";

/**
 * Resume list page route.
 *
 * REQ-012 §9.1: Card-based resume list at /resumes.
 * Only rendered for onboarded users (OnboardingGate in parent layout).
 */

import { ResumeList } from "@/components/resume/resume-list";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function ResumesPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <ResumeList />;
}
