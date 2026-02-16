"use client";

/**
 * Resume list page showing base resume cards.
 *
 * REQ-012 §9.1: Card-based resume list with primary badge, status,
 * variant count, last updated, and actions (View & Edit, Download PDF, Archive).
 */

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Loader2, Plus, Star } from "lucide-react";

import { apiDelete, apiGet, buildUrl } from "@/lib/api-client";
import { formatDateTimeAgo } from "@/lib/job-formatters";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardAction,
	CardContent,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { StatusBadge } from "@/components/ui/status-badge";
import { EmptyState, FailedState } from "@/components/ui/error-states";
import type { ApiListResponse } from "@/types/api";
import type { BaseResume, JobVariant } from "@/types/resume";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ResumeList() {
	const router = useRouter();
	const queryClient = useQueryClient();
	const [showArchived, setShowArchived] = useState(false);

	const queryParams = useMemo(() => {
		const params: Record<string, string | boolean> = {};
		if (showArchived) {
			params.include_archived = true;
		}
		return params;
	}, [showArchived]);

	const {
		data: resumesData,
		isLoading: resumesLoading,
		error: resumesError,
		refetch: refetchResumes,
	} = useQuery({
		queryKey: [...queryKeys.baseResumes, queryParams],
		queryFn: () =>
			apiGet<ApiListResponse<BaseResume>>("/base-resumes", queryParams),
	});

	const {
		data: variantsData,
		isLoading: variantsLoading,
		error: variantsError,
	} = useQuery({
		queryKey: queryKeys.variants,
		queryFn: () => apiGet<ApiListResponse<JobVariant>>("/job-variants"),
	});

	const variantCounts = useMemo(() => {
		if (!variantsData?.data) return {};
		const counts: Record<string, { total: number; pendingReview: number }> = {};
		for (const variant of variantsData.data) {
			const resumeId = variant.base_resume_id;
			if (!counts[resumeId]) {
				counts[resumeId] = { total: 0, pendingReview: 0 };
			}
			counts[resumeId].total++;
			if (variant.status === "Draft") {
				counts[resumeId].pendingReview++;
			}
		}
		return counts;
	}, [variantsData]);

	const handleArchive = useCallback(
		async (resumeId: string) => {
			try {
				await apiDelete(`/base-resumes/${resumeId}`);
				showToast.success("Resume archived.");
				await queryClient.invalidateQueries({
					queryKey: queryKeys.baseResumes,
				});
			} catch {
				showToast.error("Failed to archive resume.");
			}
		},
		[queryClient],
	);

	const isLoading = resumesLoading || variantsLoading;
	const error = resumesError ?? variantsError;

	if (isLoading) {
		return (
			<div data-testid="loading-spinner" className="flex justify-center py-12">
				<Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
			</div>
		);
	}

	if (error) {
		return <FailedState onRetry={() => refetchResumes()} />;
	}

	const resumes = resumesData?.data ?? [];

	return (
		<div data-testid="resume-list">
			<div className="mb-6 flex items-center justify-between">
				<h1 className="text-2xl font-bold">Your Resumes</h1>
				<Button onClick={() => router.push("/resumes/new")}>
					<Plus className="mr-1 h-4 w-4" />
					New Resume
				</Button>
			</div>

			{resumes.length === 0 ? (
				<EmptyState
					icon={FileText}
					title="No resumes yet"
					description="Create your first base resume to get started."
					action={{
						label: "New Resume",
						onClick: () => router.push("/resumes/new"),
					}}
				/>
			) : (
				<div className="space-y-4">
					{resumes.map((resume) => {
						const counts = variantCounts[resume.id];
						return (
							<Card key={resume.id} data-testid="resume-card">
								<CardHeader>
									<div className="flex items-center gap-2">
										{resume.is_primary && (
											<Star className="text-warning h-4 w-4 fill-current" />
										)}
										<CardTitle>{resume.name}</CardTitle>
										{resume.is_primary && (
											<span className="bg-warning/20 text-warning-foreground rounded-full px-2 py-0.5 text-xs font-medium">
												Primary
											</span>
										)}
									</div>
									<CardAction>
										<StatusBadge status={resume.status} />
									</CardAction>
								</CardHeader>

								<CardContent>
									<div className="text-muted-foreground space-y-1 text-sm">
										<p>Target: {resume.role_type}</p>
										<p>Last updated: {formatDateTimeAgo(resume.updated_at)}</p>
										{counts && counts.total > 0 && (
											<p>
												{counts.total} variant{counts.total === 1 ? "" : "s"}
												{counts.pendingReview > 0 && (
													<> ({counts.pendingReview} pending review)</>
												)}
											</p>
										)}
									</div>
								</CardContent>

								<div className="flex items-center gap-2 px-6">
									<Button
										variant="outline"
										size="sm"
										aria-label="View & Edit"
										asChild
									>
										<a
											href={`/resumes/${resume.id}`}
											onClick={(e) => {
												e.preventDefault();
												router.push(`/resumes/${resume.id}`);
											}}
										>
											View &amp; Edit
										</a>
									</Button>
									{resume.rendered_at && (
										<Button variant="outline" size="sm" asChild>
											<a
												href={buildUrl(`/base-resumes/${resume.id}/download`)}
												aria-label="Download PDF"
												target="_blank"
												rel="noopener noreferrer"
											>
												Download PDF
											</a>
										</Button>
									)}
									{resume.status === "Active" && (
										<Button
											variant="ghost"
											size="sm"
											aria-label="Archive"
											onClick={() => handleArchive(resume.id)}
										>
											Archive
										</Button>
									)}
								</div>
							</Card>
						);
					})}
				</div>
			)}

			<div className="mt-6 flex items-center gap-1.5">
				<Checkbox
					id="show-archived"
					checked={showArchived}
					onCheckedChange={(v) => setShowArchived(!!v)}
					aria-label="Show archived"
				/>
				<span className="text-sm whitespace-nowrap">Show archived</span>
			</div>
		</div>
	);
}
