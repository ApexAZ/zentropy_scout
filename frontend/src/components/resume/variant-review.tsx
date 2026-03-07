"use client";

/**
 * Variant review page with side-by-side diff (§8.6, §8.7).
 *
 * REQ-012 §9.3: Side-by-side comparison of base resume and
 * tailored variant with diff highlighting, move indicators,
 * and Approve/Regenerate/Archive actions.
 * REQ-012 §9.3-9.4: Agent reasoning display and guardrail
 * violation banners with blocking behavior.
 */

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";

import { apiDelete, apiGet, apiPost } from "@/lib/api-client";
import { computeBulletMoves, computeWordDiff } from "@/lib/diff-utils";
import { queryKeys } from "@/lib/query-keys";
import { orderBullets } from "@/lib/resume-helpers";
import { showToast } from "@/lib/toast";
import { DiffView } from "@/components/editor/diff-view";
import { DiffText } from "@/components/resume/diff-text";
import { ExportButtons } from "@/components/resume/export-buttons";
import { GuardrailViolationBanner } from "@/components/resume/guardrail-violation-banner";
import { AgentReasoning } from "@/components/ui/agent-reasoning";
import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import { FailedState } from "@/components/ui/error-states";
import { StatusBadge } from "@/components/ui/status-badge";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { PersonaJobResponse } from "@/types/job";
import type { WorkHistory } from "@/types/persona";
import type { BaseResume, JobVariant } from "@/types/resume";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface VariantReviewProps {
	baseResumeId: string;
	variantId: string;
	personaId: string;
	hideActions?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function VariantReview({
	baseResumeId,
	variantId,
	personaId,
	hideActions,
}: Readonly<VariantReviewProps>) {
	const router = useRouter();
	const queryClient = useQueryClient();
	const [showApproveDialog, setShowApproveDialog] = useState(false);
	const [isApproving, setIsApproving] = useState(false);
	const [showArchiveDialog, setShowArchiveDialog] = useState(false);
	const [isArchiving, setIsArchiving] = useState(false);

	// -----------------------------------------------------------------------
	// Data fetching (all queries fire in parallel)
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
		data: resumeData,
		isLoading: resumeLoading,
		error: resumeError,
	} = useQuery({
		queryKey: queryKeys.baseResume(baseResumeId),
		queryFn: () =>
			apiGet<ApiResponse<BaseResume>>(`/base-resumes/${baseResumeId}`),
	});

	const {
		data: workHistoryData,
		isLoading: workHistoryLoading,
		error: workHistoryError,
	} = useQuery({
		queryKey: queryKeys.workHistory(personaId),
		queryFn: () =>
			apiGet<ApiListResponse<WorkHistory>>(
				`/personas/${personaId}/work-history`,
			),
	});

	const variant = variantData?.data;
	const resume = resumeData?.data;

	// Job posting depends on variant data (conditional)
	const {
		data: jobPostingData,
		isLoading: jobPostingLoading,
		error: jobPostingError,
	} = useQuery({
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

	const jobs = useMemo(
		() => workHistoryData?.data ?? [],
		[workHistoryData?.data],
	);
	const jobPosting = jobPostingData?.data?.job;

	const includedJobs = useMemo(() => {
		if (!resume || jobs.length === 0) return [];
		return jobs.filter((j) => resume.included_jobs.includes(j.id));
	}, [resume, jobs]);

	const summaryDiff = useMemo(() => {
		if (!resume || !variant) return [];
		return computeWordDiff(resume.summary, variant.summary);
	}, [resume, variant]);

	const headerTitle = jobPosting
		? `${jobPosting.job_title} at ${jobPosting.company_name}`
		: "Variant Review";

	const guardrailViolations = variant?.guardrail_result?.violations ?? [];
	const hasGuardrailErrors = guardrailViolations.some(
		(v) => v.severity === "error",
	);

	const isDraft = variant?.status === "Draft";

	const hasMarkdownDiff =
		!!resume?.markdown_content &&
		!!variant?.markdown_content &&
		resume.markdown_content !== variant.markdown_content;

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	const handleApproveConfirm = useCallback(async () => {
		setIsApproving(true);
		try {
			await apiPost(`/job-variants/${variantId}/approve`);
			showToast.success("Variant approved.");
			await queryClient.invalidateQueries({
				queryKey: queryKeys.variants,
			});
			router.push(`/resumes/${baseResumeId}`);
		} catch {
			showToast.error("Failed to approve variant.");
		} finally {
			setIsApproving(false);
			setShowApproveDialog(false);
		}
	}, [variantId, baseResumeId, queryClient, router]);

	const handleArchiveConfirm = useCallback(async () => {
		setIsArchiving(true);
		try {
			await apiDelete(`/job-variants/${variantId}`);
			showToast.success("Variant archived.");
			await queryClient.invalidateQueries({
				queryKey: queryKeys.variants,
			});
			router.push(`/resumes/${baseResumeId}`);
		} catch {
			showToast.error("Failed to archive variant.");
		} finally {
			setIsArchiving(false);
			setShowArchiveDialog(false);
		}
	}, [variantId, baseResumeId, queryClient, router]);

	// -----------------------------------------------------------------------
	// Loading / Error
	// -----------------------------------------------------------------------

	const isLoading =
		variantLoading || resumeLoading || workHistoryLoading || jobPostingLoading;
	const error =
		variantError ?? resumeError ?? workHistoryError ?? jobPostingError;

	if (isLoading) {
		return (
			<div data-testid="loading-spinner" className="flex justify-center py-8">
				<Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
			</div>
		);
	}

	if (error || !variant || !resume) {
		return <FailedState />;
	}

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<div data-testid="variant-review">
			{/* Header (hidden when embedded in unified review) */}
			{!hideActions && (
				<div className="mb-6 flex items-center gap-3">
					<Link
						href={`/resumes/${baseResumeId}`}
						data-testid="back-link"
						aria-label="Back to resume detail"
						className="text-muted-foreground hover:text-foreground"
					>
						<ArrowLeft className="h-5 w-5" />
					</Link>
					<h1 className="text-xl font-semibold">{headerTitle}</h1>
					<StatusBadge status={variant.status} />
				</div>
			)}

			{/* Side-by-side comparison */}
			<div className="grid grid-cols-1 gap-4 md:grid-cols-2">
				{/* Base panel */}
				<div data-testid="base-panel" className="bg-card rounded-lg border p-4">
					<h2 className="mb-3 font-semibold">Base Resume</h2>

					{/* Summary diff (base side) */}
					<div className="mb-4">
						<h3 className="text-muted-foreground mb-1 text-sm font-medium">
							Summary
						</h3>
						<DiffText tokens={summaryDiff} side="base" />
					</div>

					{/* Bullets (base order) */}
					{includedJobs.map((job) => {
						const selectedBulletIds =
							resume.job_bullet_selections[job.id] ?? [];
						const selectedBullets = job.bullets.filter((b) =>
							selectedBulletIds.includes(b.id),
						);
						const baseBullets = orderBullets(
							selectedBullets,
							resume.job_bullet_order[job.id],
						);

						return (
							<div key={job.id} className="mb-4">
								<h3 className="text-muted-foreground mb-1 text-sm font-medium">
									{job.company_name}
								</h3>
								<ol className="list-decimal space-y-1 pl-5 text-sm">
									{baseBullets.map((bullet) => (
										<li key={bullet.id}>{bullet.text}</li>
									))}
								</ol>
							</div>
						);
					})}
				</div>

				{/* Variant panel */}
				<div
					data-testid="variant-panel"
					className="bg-card rounded-lg border p-4"
				>
					<h2 className="mb-3 font-semibold">Tailored Variant</h2>

					{/* Summary diff (variant side) */}
					<div className="mb-4">
						<h3 className="text-muted-foreground mb-1 text-sm font-medium">
							Summary
						</h3>
						<DiffText tokens={summaryDiff} side="variant" />
					</div>

					{/* Bullets (variant order) */}
					{includedJobs.map((job) => {
						const selectedBulletIds =
							resume.job_bullet_selections[job.id] ?? [];
						const selectedBullets = job.bullets.filter((b) =>
							selectedBulletIds.includes(b.id),
						);
						const variantBullets = orderBullets(
							selectedBullets,
							variant.job_bullet_order[job.id],
						);
						const baseOrder = resume.job_bullet_order[job.id] ?? [];
						const variantOrder = variant.job_bullet_order[job.id] ?? [];
						const moves = computeBulletMoves(baseOrder, variantOrder);

						return (
							<div key={job.id} className="mb-4">
								<h3 className="text-muted-foreground mb-1 text-sm font-medium">
									{job.company_name}
								</h3>
								<ol className="list-decimal space-y-1 pl-5 text-sm">
									{variantBullets.map((bullet) => {
										const fromPos = moves.get(bullet.id);
										return (
											<li key={bullet.id}>
												{bullet.text}
												{fromPos !== undefined && (
													<span className="text-muted-foreground ml-2 text-xs">
														from #{fromPos}
													</span>
												)}
											</li>
										);
									})}
								</ol>
							</div>
						);
					})}
				</div>
			</div>

			{/* Markdown diff (REQ-027 §4.1–§4.4) — LLM-generated variants only */}
			{hasMarkdownDiff && (
				<div className="mt-6">
					<DiffView
						masterMarkdown={resume.markdown_content ?? ""}
						variantMarkdown={variant.markdown_content ?? ""}
					/>
				</div>
			)}

			{/* Agent Reasoning (§8.7) */}
			{variant.agent_reasoning && (
				<AgentReasoning reasoning={variant.agent_reasoning} />
			)}

			{/* Guardrail Violations (§8.7) */}
			{guardrailViolations.length > 0 && (
				<GuardrailViolationBanner violations={guardrailViolations} />
			)}

			{/* Actions (hidden when embedded in unified review) */}
			{!hideActions && (
				<>
					<div className="mt-6 flex flex-wrap items-center gap-3">
						{isDraft && (
							<>
								<Button
									onClick={() => setShowApproveDialog(true)}
									disabled={isApproving || hasGuardrailErrors}
								>
									Approve
								</Button>
								<Button variant="outline" disabled={!hasGuardrailErrors}>
									Regenerate
								</Button>
								<Button variant="outline" asChild>
									<Link
										href={`/resumes/${baseResumeId}/variants/${variantId}/edit`}
										aria-label="Edit"
									>
										Edit
									</Link>
								</Button>
							</>
						)}
						<Button
							variant="ghost"
							onClick={() => setShowArchiveDialog(true)}
							disabled={isArchiving}
						>
							Archive
						</Button>
						<ExportButtons exportBasePath={`/job-variants/${variantId}`} />
					</div>

					<ConfirmationDialog
						open={showApproveDialog}
						onOpenChange={(open) => {
							if (!open) setShowApproveDialog(false);
						}}
						title="Approve Variant"
						description="Approve this variant? It will be locked for editing."
						confirmLabel="Approve"
						loading={isApproving}
						onConfirm={handleApproveConfirm}
					/>

					<ConfirmationDialog
						open={showArchiveDialog}
						onOpenChange={(open) => {
							if (!open) setShowArchiveDialog(false);
						}}
						title="Archive Variant"
						description="Are you sure you want to archive this variant?"
						confirmLabel="Archive"
						variant="destructive"
						loading={isArchiving}
						onConfirm={handleArchiveConfirm}
					/>
				</>
			)}
		</div>
	);
}
