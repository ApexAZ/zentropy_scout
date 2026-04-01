"use client";

/**
 * @fileoverview Resume list page route.
 *
 * Layer: page
 * Feature: resume
 *
 * REQ-012 §9.1: Card-based resume list at /resumes.
 * Only rendered for onboarded users (OnboardingGate in parent layout).
 *
 * Coordinates with:
 * - components/resume/resume-list.tsx: resume card list UI
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /resumes
 */

import { ResumeList } from "@/components/resume/resume-list";
import { usePersonaStatus } from "@/hooks/use-persona-status";

export default function ResumesPage() {
	const personaStatus = usePersonaStatus();

	if (personaStatus.status !== "onboarded") return null;

	return <ResumeList />;
}
