"use client";

/**
 * Job variants list for a base resume detail page.
 *
 * REQ-012 §9.2: Variant cards with status badges (Draft/Approved),
 * relative timestamps, and status-dependent actions:
 * - Draft: Review & Approve, Archive (with confirmation)
 * - Approved: View
 */

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Loader2 } from "lucide-react";

import { apiDelete, apiGet } from "@/lib/api-client";
import { formatDateTimeAgo } from "@/lib/job-formatters";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog";
import { FailedState } from "@/components/ui/error-states";
import { StatusBadge } from "@/components/ui/status-badge";
import type { ApiListResponse } from "@/types/api";
import type { JobPosting } from "@/types/job";
import type { JobVariant } from "@/types/resume";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface VariantsListProps {
	baseResumeId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function VariantsList({ baseResumeId }: VariantsListProps) {
	const router = useRouter();
	const queryClient = useQueryClient();
	const [archiveTarget, setArchiveTarget] = useState<string | null>(null);
	const [isArchiving, setIsArchiving] = useState(false);

	const {
		data: variantsData,
		isLoading: variantsLoading,
		error: variantsError,
		refetch: refetchVariants,
	} = useQuery({
		queryKey: queryKeys.variants,
		queryFn: () => apiGet<ApiListResponse<JobVariant>>("/job-variants"),
	});

	const {
		data: jobsData,
		isLoading: jobsLoading,
		error: jobsError,
	} = useQuery({
		queryKey: queryKeys.jobs,
		queryFn: () => apiGet<ApiListResponse<JobPosting>>("/job-postings"),
	});

	const jobLookup = useMemo(() => {
		const map = new Map<string, { job_title: string; company_name: string }>();
		if (jobsData?.data) {
			for (const job of jobsData.data) {
				map.set(job.id, {
					job_title: job.job_title,
					company_name: job.company_name,
				});
			}
		}
		return map;
	}, [jobsData]);

	const variants = useMemo(() => {
		if (!variantsData?.data) return [];
		return variantsData.data.filter(
			(v) => v.base_resume_id === baseResumeId && v.status !== "Archived",
		);
	}, [variantsData, baseResumeId]);

	const handleArchiveConfirm = useCallback(async () => {
		if (!archiveTarget) return;
		setIsArchiving(true);
		try {
			await apiDelete(`/job-variants/${archiveTarget}`);
			showToast.success("Variant archived.");
			await queryClient.invalidateQueries({
				queryKey: queryKeys.variants,
			});
		} catch {
			showToast.error("Failed to archive variant.");
		} finally {
			setIsArchiving(false);
			setArchiveTarget(null);
		}
	}, [archiveTarget, queryClient]);

	const isLoading = variantsLoading || jobsLoading;
	const error = variantsError ?? jobsError;

	if (isLoading) {
		return (
			<div data-testid="loading-spinner" className="flex justify-center py-8">
				<Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
			</div>
		);
	}

	if (error) {
		return <FailedState onRetry={() => refetchVariants()} />;
	}

	return (
		<div data-testid="variants-list">
			<h2 className="mb-4 text-lg font-semibold">Job Variants</h2>

			{variants.length === 0 ? (
				<p className="text-muted-foreground text-sm">No job variants yet.</p>
			) : (
				<div className="space-y-3">
					{variants.map((variant) => {
						const job = jobLookup.get(variant.job_posting_id);
						const title = job
							? `${job.job_title} at ${job.company_name}`
							: "Unknown position";

						const isDraft = variant.status === "Draft";

						return (
							<div
								key={variant.id}
								data-testid="variant-card"
								className="rounded-lg border p-4"
							>
								<div className="flex items-center justify-between">
									<div className="flex items-center gap-2">
										<FileText className="text-muted-foreground h-4 w-4" />
										<span className="font-medium">{title}</span>
									</div>
									<StatusBadge status={variant.status} />
								</div>

								<p className="text-muted-foreground mt-1 text-sm">
									{isDraft
										? `Created: ${formatDateTimeAgo(variant.created_at)}`
										: `Approved: ${formatDateTimeAgo(variant.approved_at ?? variant.created_at)}`}
								</p>

								<div className="mt-3 flex items-center gap-2">
									{isDraft ? (
										<>
											<Button
												variant="outline"
												size="sm"
												aria-label={`Review & Approve ${title}`}
												onClick={() =>
													router.push(
														`/resumes/${baseResumeId}/variants/${variant.id}/review`,
													)
												}
											>
												Review &amp; Approve
											</Button>
											<Button
												variant="ghost"
												size="sm"
												aria-label={`Archive ${title}`}
												onClick={() => setArchiveTarget(variant.id)}
											>
												Archive
											</Button>
										</>
									) : (
										<Button
											variant="outline"
											size="sm"
											aria-label={`View ${title}`}
											onClick={() =>
												router.push(
													`/resumes/${baseResumeId}/variants/${variant.id}`,
												)
											}
										>
											View
										</Button>
									)}
								</div>
							</div>
						);
					})}
				</div>
			)}

			<ConfirmationDialog
				open={archiveTarget !== null}
				onOpenChange={(open) => {
					if (!open) setArchiveTarget(null);
				}}
				title="Archive Variant"
				description="Are you sure you want to archive this variant?"
				confirmLabel="Archive"
				variant="destructive"
				loading={isArchiving}
				onConfirm={handleArchiveConfirm}
			/>
		</div>
	);
}
