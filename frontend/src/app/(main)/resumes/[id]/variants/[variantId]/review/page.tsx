"use client";

/**
 * @fileoverview Variant review page with side-by-side diff comparison.
 *
 * Layer: page
 * Feature: resume
 *
 * REQ-012 §9.3: Side-by-side comparison at
 * /resumes/[id]/variants/[variantId]/review.
 * Only rendered for onboarded users (OnboardingGate in parent layout).
 *
 * Coordinates with:
 * - components/resume/variant-review.tsx: diff review UI component
 * - hooks/use-persona-status.ts: persona status check for guard
 *
 * Called by / Used by:
 * - Next.js framework: route /resumes/[id]/variants/[variantId]/review
 */

import { useParams } from "next/navigation";

import { VariantReview } from "@/components/resume/variant-review";
import { usePersonaStatus } from "@/hooks/use-persona-status";

/** Variant review page — renders side-by-side diff for a draft variant. */
export default function VariantReviewPage() {
	const personaStatus = usePersonaStatus();
	const params = useParams<{ id: string; variantId: string }>();

	if (personaStatus.status !== "onboarded") return null;

	return (
		<VariantReview
			baseResumeId={params.id}
			variantId={params.variantId}
			personaId={personaStatus.persona.id}
		/>
	);
}
