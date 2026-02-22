"use client";

/**
 * Unified Ghostwriter review: tabbed resume variant + cover letter
 * with "Approve Both" action.
 *
 * REQ-012 §10.7: Combined review experience when Ghostwriter
 * completes both resume variant and cover letter.
 */

import { useCallback, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { apiGet, apiPatch, apiPost } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { FailedState } from "@/components/ui/error-states";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CoverLetterReview } from "@/components/cover-letter/cover-letter-review";
import { VariantReview } from "@/components/resume/variant-review";
import type { ApiResponse } from "@/types/api";
import type { CoverLetter } from "@/types/application";
import type { PersonaJobResponse } from "@/types/job";
import type { JobVariant } from "@/types/resume";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GhostwriterReviewProps {
	variantId: string;
	coverLetterId: string;
	baseResumeId: string;
	personaId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function GhostwriterReview({
	variantId,
	coverLetterId,
	baseResumeId,
	personaId,
}: Readonly<GhostwriterReviewProps>) {
	const queryClient = useQueryClient();

	// -----------------------------------------------------------------------
	// Data fetching
	// -----------------------------------------------------------------------

	const {
		data: variantData,
		isLoading: variantLoading,
		error: variantError,
	} = useQuery({
		queryKey: queryKeys.variant(variantId),
		queryFn: () =>
			apiGet<ApiResponse<JobVariant>>(`/job-variants/${variantId}`),
	});

	const {
		data: coverLetterData,
		isLoading: coverLetterLoading,
		error: coverLetterError,
	} = useQuery({
		queryKey: queryKeys.coverLetter(coverLetterId),
		queryFn: () =>
			apiGet<ApiResponse<CoverLetter>>(`/cover-letters/${coverLetterId}`),
	});

	const variant = variantData?.data;
	const coverLetter = coverLetterData?.data;

	const { data: jobPostingData } = useQuery({
		queryKey: queryKeys.job(variant?.job_posting_id ?? ""),
		queryFn: () =>
			apiGet<ApiResponse<PersonaJobResponse>>(
				`/job-postings/${variant?.job_posting_id}`,
			),
		enabled: !!variant?.job_posting_id,
	});

	// -----------------------------------------------------------------------
	// Derived state
	// -----------------------------------------------------------------------

	const jobPosting = jobPostingData?.data?.job;

	const headerTitle = jobPosting
		? `Materials for: ${jobPosting.job_title} at ${jobPosting.company_name}`
		: "Materials Review";

	const variantIsDraft = variant?.status === "Draft";
	const coverLetterIsDraft = coverLetter?.status === "Draft";
	const bothDraft = variantIsDraft && coverLetterIsDraft;
	const anyDraft = variantIsDraft || coverLetterIsDraft;

	const hasVariantGuardrailErrors = useMemo(
		() =>
			variant?.guardrail_result?.violations.some(
				(v) => v.severity === "error",
			) ?? false,
		[variant?.guardrail_result],
	);

	const hasCoverLetterValidationErrors = useMemo(
		() =>
			coverLetter?.validation_result?.issues.some(
				(i) => i.severity === "error",
			) ?? false,
		[coverLetter?.validation_result],
	);

	const approveBothDisabled =
		hasVariantGuardrailErrors || hasCoverLetterValidationErrors;
	const approveResumeDisabled = hasVariantGuardrailErrors;
	const approveLetterDisabled = hasCoverLetterValidationErrors;

	// -----------------------------------------------------------------------
	// Form state
	// -----------------------------------------------------------------------

	const [isApproving, setIsApproving] = useState(false);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	const handleApproveBoth = useCallback(async () => {
		setIsApproving(true);
		const results = await Promise.allSettled([
			apiPost(`/job-variants/${variantId}/approve`),
			apiPatch(`/cover-letters/${coverLetterId}`, {
				status: "Approved",
			}),
		]);
		const resumeOk = results[0].status === "fulfilled";
		const letterOk = results[1].status === "fulfilled";

		await Promise.all([
			resumeOk &&
				queryClient.invalidateQueries({
					queryKey: queryKeys.variant(variantId),
				}),
			letterOk &&
				queryClient.invalidateQueries({
					queryKey: queryKeys.coverLetter(coverLetterId),
				}),
		]);

		if (resumeOk && letterOk) {
			showToast.success("Both materials approved.");
		} else if (resumeOk) {
			showToast.warning(
				"Resume approved, but cover letter failed. Try approving the letter separately.",
			);
		} else if (letterOk) {
			showToast.warning(
				"Cover letter approved, but resume failed. Try approving the resume separately.",
			);
		} else {
			showToast.error("Failed to approve materials.");
		}
		setIsApproving(false);
	}, [variantId, coverLetterId, queryClient]);

	const handleApproveResumeOnly = useCallback(async () => {
		setIsApproving(true);
		try {
			await apiPost(`/job-variants/${variantId}/approve`);
			await queryClient.invalidateQueries({
				queryKey: queryKeys.variant(variantId),
			});
			showToast.success("Resume variant approved.");
		} catch {
			showToast.error("Failed to approve resume variant.");
		} finally {
			setIsApproving(false);
		}
	}, [variantId, queryClient]);

	const handleApproveLetterOnly = useCallback(async () => {
		setIsApproving(true);
		try {
			await apiPatch(`/cover-letters/${coverLetterId}`, {
				status: "Approved",
			});
			await queryClient.invalidateQueries({
				queryKey: queryKeys.coverLetter(coverLetterId),
			});
			showToast.success("Cover letter approved.");
		} catch {
			showToast.error("Failed to approve cover letter.");
		} finally {
			setIsApproving(false);
		}
	}, [coverLetterId, queryClient]);

	// -----------------------------------------------------------------------
	// Loading / Error
	// -----------------------------------------------------------------------

	if (variantLoading || coverLetterLoading) {
		return (
			<div data-testid="loading-spinner" className="flex justify-center py-8">
				<Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
			</div>
		);
	}

	if (variantError || coverLetterError || !variant || !coverLetter) {
		return <FailedState />;
	}

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<div data-testid="ghostwriter-review">
			{/* Header */}
			<h1 className="mb-6 text-xl font-semibold">{headerTitle}</h1>

			{/* Tabbed Review */}
			<Tabs defaultValue="variant">
				<TabsList>
					<TabsTrigger value="variant">Resume Variant</TabsTrigger>
					<TabsTrigger value="cover-letter">Cover Letter</TabsTrigger>
				</TabsList>

				<TabsContent value="variant">
					<VariantReview
						baseResumeId={baseResumeId}
						variantId={variantId}
						personaId={personaId}
						hideActions
					/>
				</TabsContent>

				<TabsContent value="cover-letter">
					<CoverLetterReview coverLetterId={coverLetterId} hideActions />
				</TabsContent>
			</Tabs>

			{/* Unified Approval Actions (§10.7) */}
			{anyDraft && (
				<div className="mt-6 flex items-center gap-3">
					{bothDraft && (
						<Button
							onClick={handleApproveBoth}
							disabled={isApproving || approveBothDisabled}
							className="gap-2"
						>
							{isApproving && (
								<Loader2
									data-testid="approve-both-spinner"
									className="h-4 w-4 animate-spin"
									aria-hidden="true"
								/>
							)}
							Approve Both
						</Button>
					)}
					{variantIsDraft && (
						<Button
							variant="outline"
							onClick={handleApproveResumeOnly}
							disabled={isApproving || approveResumeDisabled}
						>
							Approve Resume Only
						</Button>
					)}
					{coverLetterIsDraft && (
						<Button
							variant="outline"
							onClick={handleApproveLetterOnly}
							disabled={isApproving || approveLetterDisabled}
						>
							Approve Letter Only
						</Button>
					)}
				</div>
			)}
		</div>
	);
}
