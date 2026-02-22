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
import { AlertTriangle, ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";

import { apiDelete, apiGet, apiPost } from "@/lib/api-client";
import { computeBulletMoves, computeWordDiff } from "@/lib/diff-utils";
import type { DiffToken } from "@/lib/diff-utils";
import { queryKeys } from "@/lib/query-keys";
import { orderBullets } from "@/lib/resume-helpers";
import { showToast } from "@/lib/toast";
import { AgentReasoning } from "@/components/ui/agent-reasoning";
import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import { FailedState } from "@/components/ui/error-states";
import type { ApiListResponse, ApiResponse } from "@/types/api";
import type { PersonaJobResponse } from "@/types/job";
import type { WorkHistory } from "@/types/persona";
import type {
	BaseResume,
	GuardrailViolation,
	JobVariant,
} from "@/types/resume";

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
// Constants
// ---------------------------------------------------------------------------

/** CSS classes for diff token highlighting keyed by token type. */
const DIFF_CLASS_MAP: Readonly<Record<string, string | undefined>> = {
	same: undefined,
	added: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
	removed:
		"bg-red-100 text-red-800 line-through dark:bg-red-900 dark:text-red-200",
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function DiffText({
	tokens,
	side,
}: Readonly<{
	tokens: DiffToken[];
	side: "base" | "variant";
}>) {
	const filtered =
		side === "base"
			? tokens.filter((t) => t.type !== "added")
			: tokens.filter((t) => t.type !== "removed");

	return (
		<p className="text-sm leading-relaxed">
			{filtered.map((token, idx) => {
				const diffType = token.type === "same" ? undefined : token.type;

				const className = DIFF_CLASS_MAP[token.type];

				return (
					<span key={`${token.type}-${idx}`}>
						{idx > 0 ? " " : ""}
						<span data-diff={diffType} className={className}>
							{token.text}
						</span>
					</span>
				);
			})}
		</p>
	);
}

function GuardrailViolationBanner({
	violations,
}: Readonly<{
	violations: GuardrailViolation[];
}>) {
	return (
		<div
			data-testid="guardrail-violations"
			role="alert"
			className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950"
		>
			<div className="mb-2 flex items-center gap-2">
				<AlertTriangle className="h-4 w-4 text-red-600 dark:text-red-400" />
				<span className="text-sm font-semibold text-red-800 dark:text-red-200">
					Guardrail Violation
				</span>
			</div>
			<ul className="mb-3 list-disc space-y-1 pl-5 text-sm text-red-700 dark:text-red-300">
				{violations.map((v) => (
					<li key={v.rule}>{v.message}</li>
				))}
			</ul>
			<div className="flex items-center gap-2">
				<Link
					href="/persona"
					data-testid="go-to-persona-link"
					className="text-sm font-medium text-red-700 underline hover:text-red-900 dark:text-red-300 dark:hover:text-red-100"
				>
					Go to Persona
				</Link>
			</div>
		</div>
	);
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

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	const handleApprove = useCallback(async () => {
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
				</div>
			)}

			{/* Side-by-side comparison */}
			<div className="grid grid-cols-2 gap-4">
				{/* Base panel */}
				<div data-testid="base-panel" className="rounded-lg border p-4">
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
				<div data-testid="variant-panel" className="rounded-lg border p-4">
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
					<div className="mt-6 flex items-center gap-3">
						<Button
							onClick={handleApprove}
							disabled={isApproving || hasGuardrailErrors}
						>
							{isApproving ? "Approving..." : "Approve"}
						</Button>
						<Button variant="outline" disabled={!hasGuardrailErrors}>
							Regenerate
						</Button>
						<Button
							variant="ghost"
							onClick={() => setShowArchiveDialog(true)}
							disabled={isArchiving}
						>
							Archive
						</Button>
					</div>

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
