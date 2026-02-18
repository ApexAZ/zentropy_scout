"use client";

/**
 * Cover letter section for the job detail page.
 *
 * REQ-012 §10.1: Cover letters accessed from job detail page.
 * REQ-012 §15.9: Shows status badge (None/Draft/Approved),
 * embeds CoverLetterReview inline when draft, download link when approved.
 */

import { useQuery } from "@tanstack/react-query";
import { Download, Loader2 } from "lucide-react";

import { apiGet, buildUrl } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { CoverLetterReview } from "@/components/cover-letter/cover-letter-review";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import type { ApiListResponse } from "@/types/api";
import type { CoverLetter, CoverLetterStatus } from "@/types/application";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CoverLetterSectionProps {
	jobId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CoverLetterSection({
	jobId,
}: Readonly<CoverLetterSectionProps>) {
	const { data, isLoading } = useQuery({
		queryKey: [...queryKeys.coverLetters, "job", jobId],
		queryFn: () =>
			apiGet<ApiListResponse<CoverLetter>>("/cover-letters", {
				job_posting_id: jobId,
			}),
	});

	// -----------------------------------------------------------------------
	// Loading
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div
				data-testid="cover-letter-section-loading"
				className="flex justify-center py-6"
			>
				<Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
			</div>
		);
	}

	// -----------------------------------------------------------------------
	// Derive active cover letter (first non-archived)
	// -----------------------------------------------------------------------

	const activeCoverLetter =
		data?.data.find((cl) => cl.status !== "Archived") ?? null;

	const displayStatus: CoverLetterStatus | "None" =
		activeCoverLetter?.status ?? "None";

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<Card data-testid="cover-letter-section">
			<CardHeader>
				<div className="flex items-center gap-3">
					<CardTitle>Cover Letter</CardTitle>
					<StatusBadge status={displayStatus} />
				</div>
			</CardHeader>
			<CardContent>
				{/* None state — no active cover letter */}
				{!activeCoverLetter && (
					<p
						data-testid="cover-letter-none-prompt"
						className="text-muted-foreground text-sm"
					>
						No cover letter yet. Use &quot;Draft Materials&quot; to generate
						one.
					</p>
				)}

				{/* Draft state — embed CoverLetterReview inline */}
				{activeCoverLetter?.status === "Draft" && (
					<CoverLetterReview coverLetterId={activeCoverLetter.id} />
				)}

				{/* Approved state — download link */}
				{activeCoverLetter?.status === "Approved" && (
					<Button variant="outline" asChild>
						<a
							data-testid="cover-letter-section-download"
							href={buildUrl(
								`/submitted-cover-letter-pdfs/${activeCoverLetter.id}/download`,
							)}
							target="_blank"
							rel="noopener noreferrer"
						>
							<Download className="mr-1 h-4 w-4" />
							Download Cover Letter PDF
						</a>
					</Button>
				)}
			</CardContent>
		</Card>
	);
}
