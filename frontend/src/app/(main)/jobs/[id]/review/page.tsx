"use client";

/**
 * Ghostwriter review page route.
 *
 * REQ-012 §10.7: Unified review of resume variant + cover letter.
 * REQ-012 §15.8: Route /jobs/[id]/review — resolves materials for a job
 * and renders GhostwriterReview with tabbed approve actions.
 *
 * Only rendered for onboarded users (OnboardingGate in parent layout).
 */

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { apiGet } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { GhostwriterReview } from "@/components/ghostwriter/ghostwriter-review";
import { usePersonaStatus } from "@/hooks/use-persona-status";
import type { ApiListResponse } from "@/types/api";
import type { CoverLetter } from "@/types/application";
import type { JobVariant } from "@/types/resume";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** UUID v4 format pattern for job ID validation (defense-in-depth). */
const UUID_PATTERN =
	/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/** Ghostwriter review page — resolves variant + cover letter for a job. */
export default function GhostwriterReviewPage() {
	const personaStatus = usePersonaStatus();
	const params = useParams<{ id: string }>();
	const isOnboarded = personaStatus.status === "onboarded";
	const isValidId = UUID_PATTERN.test(params.id);

	// -----------------------------------------------------------------------
	// Data fetching — find materials for this job
	// -----------------------------------------------------------------------

	const { data: variantsData, isLoading: variantsLoading } = useQuery({
		queryKey: [...queryKeys.variants, "job", params.id],
		queryFn: () =>
			apiGet<ApiListResponse<JobVariant>>("/variants", {
				job_posting_id: params.id,
			}),
		enabled: isOnboarded && isValidId,
	});

	const { data: coverLettersData, isLoading: coverLettersLoading } = useQuery({
		queryKey: [...queryKeys.coverLetters, "job", params.id],
		queryFn: () =>
			apiGet<ApiListResponse<CoverLetter>>("/cover-letters", {
				job_posting_id: params.id,
			}),
		enabled: isOnboarded && isValidId,
	});

	// -----------------------------------------------------------------------
	// Guard clause
	// -----------------------------------------------------------------------

	if (!isOnboarded) return null;
	if (!isValidId) return null;

	// -----------------------------------------------------------------------
	// Loading
	// -----------------------------------------------------------------------

	const isLoading = variantsLoading || coverLettersLoading;

	if (isLoading) {
		return (
			<div
				data-testid="review-page-loading"
				className="flex justify-center py-8"
			>
				<Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
			</div>
		);
	}

	// -----------------------------------------------------------------------
	// Resolve materials — first non-archived variant and cover letter
	// -----------------------------------------------------------------------

	const activeVariant =
		variantsData?.data.find((v) => v.status !== "Archived") ?? null;
	const activeCoverLetter =
		coverLettersData?.data.find((cl) => cl.status !== "Archived") ?? null;

	if (!activeVariant || !activeCoverLetter) {
		return (
			<div
				data-testid="review-page-no-materials"
				className="mx-auto max-w-4xl px-4 py-8 text-center"
			>
				<p className="text-muted-foreground">
					No materials found for this job. Use &quot;Draft Materials&quot; on
					the job detail page to generate a resume variant and cover letter.
				</p>
			</div>
		);
	}

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<div className="mx-auto max-w-4xl px-4 py-6">
			<GhostwriterReview
				variantId={activeVariant.id}
				coverLetterId={activeCoverLetter.id}
				baseResumeId={activeVariant.base_resume_id}
				personaId={personaStatus.persona.id}
			/>
		</div>
	);
}
