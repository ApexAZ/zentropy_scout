"use client";

/**
 * "Mark as Applied" card for the job detail page.
 *
 * REQ-012 §11.4: Three-step flow — download materials, apply externally,
 * confirm application creation. Shows "Already applied" if application exists.
 * Hidden when no approved resume variant exists for this job.
 */

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle, Download, ExternalLink, Loader2 } from "lucide-react";

import { apiGet, apiPost, buildUrl } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { getHostname, isSafeUrl } from "@/lib/url-utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { Application, CoverLetter } from "@/types/application";
import type { JobVariant } from "@/types/resume";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SUCCESS_MESSAGE = "Application created!";
const ERROR_MESSAGE = "Failed to create application.";
const STEP_LABEL_CLASS = "text-muted-foreground text-sm font-medium";
const LINK_ICON_CLASS = "mr-1 h-4 w-4";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MarkAsAppliedCardProps {
	jobId: string;
	applyUrl: string | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MarkAsAppliedCard({ jobId, applyUrl }: MarkAsAppliedCardProps) {
	const router = useRouter();
	const queryClient = useQueryClient();
	const [submitting, setSubmitting] = useState(false);

	// -----------------------------------------------------------------------
	// Data fetching
	// -----------------------------------------------------------------------

	const { data: variantsData, isLoading: variantsLoading } = useQuery({
		queryKey: [...queryKeys.variants, "job", jobId],
		queryFn: () =>
			apiGet<ApiListResponse<JobVariant>>("/variants", {
				job_posting_id: jobId,
				status: "Approved",
			}),
	});

	const { data: coverLettersData, isLoading: coverLettersLoading } = useQuery({
		queryKey: [...queryKeys.coverLetters, "job", jobId],
		queryFn: () =>
			apiGet<ApiListResponse<CoverLetter>>("/cover-letters", {
				job_posting_id: jobId,
				status: "Approved",
			}),
	});

	const { data: applicationsData, isLoading: applicationsLoading } = useQuery({
		queryKey: [...queryKeys.applications, "job", jobId],
		queryFn: () =>
			apiGet<ApiListResponse<Application>>("/applications", {
				job_posting_id: jobId,
			}),
	});

	// -----------------------------------------------------------------------
	// Derived data
	// -----------------------------------------------------------------------

	const isLoading =
		variantsLoading || coverLettersLoading || applicationsLoading;
	const variant = variantsData?.data[0] ?? null;
	const coverLetter = coverLettersData?.data[0] ?? null;
	const existingApp = applicationsData?.data[0] ?? null;

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	const handleConfirmApplied = useCallback(async () => {
		if (!variant) return;
		setSubmitting(true);
		try {
			const response = await apiPost<ApiResponse<Application>>(
				"/applications",
				{
					job_posting_id: jobId,
					job_variant_id: variant.id,
					cover_letter_id: coverLetter?.id ?? null,
				},
			);
			await queryClient.invalidateQueries({
				queryKey: queryKeys.applications,
			});
			await queryClient.invalidateQueries({
				queryKey: queryKeys.job(jobId),
			});
			showToast.success(SUCCESS_MESSAGE);
			router.push(`/applications/${response.data.id}`);
		} catch {
			showToast.error(ERROR_MESSAGE);
		} finally {
			setSubmitting(false);
		}
	}, [variant, coverLetter, jobId, queryClient, router]);

	// -----------------------------------------------------------------------
	// Loading
	// -----------------------------------------------------------------------

	if (isLoading) {
		return (
			<div
				data-testid="mark-as-applied-loading"
				className="flex justify-center py-6"
			>
				<Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
			</div>
		);
	}

	// -----------------------------------------------------------------------
	// No approved variant — hide card
	// -----------------------------------------------------------------------

	if (!variant) {
		return null;
	}

	// -----------------------------------------------------------------------
	// Already applied
	// -----------------------------------------------------------------------

	if (existingApp) {
		return (
			<Card data-testid="already-applied-notice">
				<CardContent className="flex items-center gap-3 pt-6">
					<CheckCircle className="h-5 w-5 shrink-0 text-green-500" />
					<p className="text-sm">
						Already applied{" "}
						<a
							href={`/applications/${existingApp.id}`}
							className="text-primary hover:underline"
						>
							View application
						</a>
					</p>
				</CardContent>
			</Card>
		);
	}

	// -----------------------------------------------------------------------
	// Ready to apply
	// -----------------------------------------------------------------------

	const showApplyLink = applyUrl && isSafeUrl(applyUrl);

	return (
		<Card data-testid="mark-as-applied-card">
			<CardHeader>
				<CardTitle>Ready to Apply</CardTitle>
			</CardHeader>
			<CardContent className="space-y-4">
				{/* Step 1: Download materials */}
				<div className="space-y-2">
					<p className={STEP_LABEL_CLASS}>1. Download your materials:</p>
					<div className="flex flex-wrap gap-2">
						<Button
							variant="outline"
							size="sm"
							asChild
							data-testid="resume-download-link"
						>
							<a
								href={buildUrl(
									`/base-resumes/${variant.base_resume_id}/download`,
								)}
								target="_blank"
								rel="noopener noreferrer"
							>
								<Download className={LINK_ICON_CLASS} />
								Download Resume PDF
							</a>
						</Button>
						{coverLetter && (
							<Button
								variant="outline"
								size="sm"
								asChild
								data-testid="cover-letter-download-link"
							>
								<a
									href={buildUrl(`/cover-letters/${coverLetter.id}/download`)}
									target="_blank"
									rel="noopener noreferrer"
								>
									<Download className={LINK_ICON_CLASS} />
									Download Cover Letter PDF
								</a>
							</Button>
						)}
					</div>
				</div>

				{/* Step 2: Apply externally */}
				{showApplyLink && (
					<div className="space-y-2">
						<p className={STEP_LABEL_CLASS}>2. Submit at:</p>
						<Button
							variant="outline"
							size="sm"
							asChild
							data-testid="apply-external-link"
						>
							<a href={applyUrl} target="_blank" rel="noopener noreferrer">
								<ExternalLink className={LINK_ICON_CLASS} />
								Apply on {getHostname(applyUrl)}
							</a>
						</Button>
					</div>
				)}

				{/* Step 3: Confirm */}
				<div className="space-y-2">
					<p className={STEP_LABEL_CLASS}>
						{showApplyLink ? "3" : "2"}. Come back and confirm:
					</p>
					<Button
						data-testid="confirm-applied-button"
						disabled={submitting}
						onClick={() => void handleConfirmApplied()}
						className="gap-2"
					>
						{submitting && <Loader2 className="h-4 w-4 animate-spin" />}
						I&apos;ve Applied
					</Button>
				</div>
			</CardContent>
		</Card>
	);
}
