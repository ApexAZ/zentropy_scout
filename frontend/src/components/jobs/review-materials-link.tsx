"use client";

/**
 * "Review Materials" link for the job detail page.
 *
 * REQ-012 §10.7, §15.8: After the ghostwriter completes, show a link
 * to the unified review at /jobs/[id]/review. Visible when both a
 * non-archived variant AND cover letter exist, and at least one is Draft.
 *
 * Complement to DraftMaterialsCard — that shows when no materials exist,
 * this shows when materials exist and need review.
 */

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { FileCheck, Loader2 } from "lucide-react";

import { apiGet } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
// Types
// ---------------------------------------------------------------------------

export interface ReviewMaterialsLinkProps {
	jobId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ReviewMaterialsLink({
	jobId,
}: Readonly<ReviewMaterialsLinkProps>) {
	// -----------------------------------------------------------------------
	// Validation
	// -----------------------------------------------------------------------

	const isValidId = UUID_PATTERN.test(jobId);

	// -----------------------------------------------------------------------
	// Data fetching — check for existing materials
	// -----------------------------------------------------------------------

	const { data: variantsData, isLoading: variantsLoading } = useQuery({
		queryKey: [...queryKeys.variants, "job", jobId],
		queryFn: () =>
			apiGet<ApiListResponse<JobVariant>>("/variants", {
				job_posting_id: jobId,
			}),
		enabled: isValidId,
	});

	const { data: coverLettersData, isLoading: coverLettersLoading } = useQuery({
		queryKey: [...queryKeys.coverLetters, "job", jobId],
		queryFn: () =>
			apiGet<ApiListResponse<CoverLetter>>("/cover-letters", {
				job_posting_id: jobId,
			}),
		enabled: isValidId,
	});

	// -----------------------------------------------------------------------
	// Invalid ID guard
	// -----------------------------------------------------------------------

	if (!isValidId) return null;

	// -----------------------------------------------------------------------
	// Loading
	// -----------------------------------------------------------------------

	const isLoading = variantsLoading || coverLettersLoading;

	if (isLoading) {
		return (
			<div
				data-testid="review-materials-loading"
				className="flex justify-center py-6"
			>
				<Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
			</div>
		);
	}

	// -----------------------------------------------------------------------
	// Visibility logic
	// -----------------------------------------------------------------------

	const activeVariant =
		variantsData?.data.find((v) => v.status !== "Archived") ?? null;
	const activeCoverLetter =
		coverLettersData?.data.find((cl) => cl.status !== "Archived") ?? null;

	// Need both materials to exist
	if (!activeVariant || !activeCoverLetter) return null;

	// At least one must be Draft (still needs review)
	const anyDraft =
		activeVariant.status === "Draft" || activeCoverLetter.status === "Draft";
	if (!anyDraft) return null;

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<Card data-testid="review-materials-link">
			<CardHeader>
				<CardTitle>Review Materials</CardTitle>
			</CardHeader>
			<CardContent className="space-y-3">
				<p className="text-muted-foreground text-sm">
					Your resume variant and cover letter are ready for review.
				</p>
				<Button asChild className="gap-2">
					<Link
						data-testid="review-materials-anchor"
						href={`/jobs/${jobId}/review`}
					>
						<FileCheck className="h-4 w-4" />
						Review Materials
					</Link>
				</Button>
			</CardContent>
		</Card>
	);
}
