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

/** UUID v4 format pattern for resume ID validation (defense-in-depth). */
const UUID_PATTERN =
	/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Resume detail page — renders editor for base resume content selections. */
export default function ResumeDetailPage() {
	const personaStatus = usePersonaStatus();
	const params = useParams<{ id: string }>();

	if (personaStatus.status !== "onboarded") return null;
	if (!UUID_PATTERN.test(params.id)) return null;

	return (
		<ResumeDetail resumeId={params.id} personaId={personaStatus.persona.id} />
	);
}
