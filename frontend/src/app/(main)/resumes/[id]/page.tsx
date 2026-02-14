"use client";

/**
 * Resume detail page route.
 *
 * REQ-012 §9.2: Base resume editor at /resumes/[id].
 * Only rendered for onboarded users (OnboardingGate in parent layout).
 */

import { useParams } from "next/navigation";

import { ResumeDetail } from "@/components/resume/resume-detail";
import { usePersonaStatus } from "@/hooks/use-persona-status";

/** Resume detail page — renders editor for base resume content selections. */
export default function ResumeDetailPage() {
	const personaStatus = usePersonaStatus();
	const params = useParams<{ id: string }>();

	if (personaStatus.status !== "onboarded") return null;

	return (
		<ResumeDetail resumeId={params.id} personaId={personaStatus.persona.id} />
	);
}
