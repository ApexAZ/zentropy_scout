"use client";

/**
 * Job detail page header with metadata, cross-source links,
 * ghost detection breakdown, and repost history.
 *
 * REQ-012 §8.3: Job detail page header section.
 * REQ-003 §7: Ghost detection signals display.
 * REQ-003 §9.2: Cross-source deduplication display.
 */

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
	ArrowLeft,
	ExternalLink,
	Heart,
	Loader2,
	RefreshCw,
	TriangleAlert,
} from "lucide-react";

import { ApiError, apiGet, apiPatch } from "@/lib/api-client";
import { formatDaysAgo, formatSalary } from "@/lib/job-formatters";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { getHostname, isSafeUrl } from "@/lib/url-utils";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { FailedState, NotFoundState } from "@/components/ui/error-states";
import { StatusBadge } from "@/components/ui/status-badge";
import type { ApiResponse } from "@/types/api";
import type { GhostScoreTier, JobPosting } from "@/types/job";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FAVORITE_ERROR_MESSAGE = "Failed to update favorite.";
const DOT_SEPARATOR = " \u00b7 ";

const GHOST_TIER_CONFIG: {
	minScore: number;
	tier: GhostScoreTier;
	colorClass: string;
}[] = [
	{ minScore: 76, tier: "High Risk", colorClass: "text-red-500" },
	{ minScore: 51, tier: "Elevated", colorClass: "text-orange-500" },
	{ minScore: 26, tier: "Moderate", colorClass: "text-amber-500" },
	{ minScore: 1, tier: "Fresh", colorClass: "text-green-500" },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getGhostTier(score: number) {
	return GHOST_TIER_CONFIG.find((t) => score >= t.minScore) ?? null;
}

function formatRepostCount(count: number): string {
	return count === 1 ? "1 time" : `${count} times`;
}

function formatPreviousPostings(count: number): string {
	return count === 1 ? "1 previous posting" : `${count} previous postings`;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface JobDetailHeaderProps {
	jobId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function JobDetailHeader({ jobId }: JobDetailHeaderProps) {
	const router = useRouter();
	const queryClient = useQueryClient();
	const [togglingFavorite, setTogglingFavorite] = useState(false);

	const { data, isLoading, error, refetch } = useQuery({
		queryKey: queryKeys.job(jobId),
		queryFn: () => apiGet<ApiResponse<JobPosting>>(`/job-postings/${jobId}`),
	});

	const handleFavoriteToggle = useCallback(async () => {
		if (!data) return;
		const job = data.data;
		setTogglingFavorite(true);
		try {
			await apiPatch(`/job-postings/${job.id}`, {
				is_favorite: !job.is_favorite,
			});
			await queryClient.invalidateQueries({
				queryKey: queryKeys.job(jobId),
			});
			await queryClient.invalidateQueries({
				queryKey: queryKeys.jobs,
			});
		} catch {
			showToast.error(FAVORITE_ERROR_MESSAGE);
		} finally {
			setTogglingFavorite(false);
		}
	}, [data, jobId, queryClient]);

	// Loading state
	if (isLoading) {
		return (
			<div data-testid="loading-spinner" className="flex justify-center py-12">
				<Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
			</div>
		);
	}

	// Error states
	if (error) {
		if (error instanceof ApiError && error.status === 404) {
			return <NotFoundState itemType="job" onBack={() => router.push("/")} />;
		}
		return <FailedState onRetry={() => refetch()} />;
	}

	const job = data!.data;
	const ghostTier = getGhostTier(job.ghost_score);
	const hasGhostRisk = job.ghost_score > 0;
	const hasRepostHistory = job.repost_count > 0;

	// Filter cross-source entries to only safe URLs
	const safeCrossSources = job.also_found_on.sources.filter((s) =>
		isSafeUrl(s.source_url),
	);

	// Build metadata parts
	const metadataParts: string[] = [job.company_name];
	if (job.location) metadataParts.push(job.location);
	if (job.work_model) metadataParts.push(job.work_model);
	if (job.seniority_level) metadataParts.push(job.seniority_level);

	return (
		<div data-testid="job-detail-header" className="space-y-6">
			{/* Back link */}
			<Link
				href="/"
				data-testid="back-to-jobs"
				className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm"
			>
				<ArrowLeft className="h-4 w-4" />
				Back to Jobs
			</Link>

			{/* Title row */}
			<div className="flex items-start justify-between gap-4">
				<div className="space-y-1">
					<h1 className="text-2xl font-bold">{job.job_title}</h1>
					<div data-testid="job-status-badge">
						<StatusBadge status={job.status} />
					</div>
				</div>
				<Button
					variant="ghost"
					size="sm"
					data-testid="favorite-toggle"
					disabled={togglingFavorite}
					onClick={handleFavoriteToggle}
				>
					<Heart
						className={cn(
							"mr-1 h-4 w-4",
							job.is_favorite && "fill-current text-red-500",
						)}
					/>
					{job.is_favorite ? "Unfavorite" : "Favorite"}
				</Button>
			</div>

			{/* Metadata line */}
			<p data-testid="job-metadata" className="text-muted-foreground text-sm">
				{metadataParts.join(DOT_SEPARATOR)}
			</p>

			{/* Salary */}
			<p data-testid="job-salary" className="text-sm font-medium">
				{formatSalary(job)}
			</p>

			{/* Dates */}
			<p data-testid="job-dates" className="text-muted-foreground text-sm">
				{job.posted_date && (
					<>
						Posted {formatDaysAgo(job.posted_date)}
						{DOT_SEPARATOR}
					</>
				)}
				Discovered {formatDaysAgo(job.first_seen_date)}
			</p>

			{/* Cross-source links */}
			{safeCrossSources.length > 0 && (
				<div
					data-testid="cross-source-links"
					className="text-muted-foreground text-sm"
				>
					<span>Also found on: </span>
					{safeCrossSources.map((source, index) => (
						<span key={source.source_id}>
							{index > 0 && ", "}
							<a
								href={source.source_url}
								target="_blank"
								rel="noopener noreferrer"
								className="text-primary hover:underline"
							>
								{getHostname(source.source_url)}
							</a>
						</span>
					))}
				</div>
			)}

			{/* External links */}
			<div className="flex gap-2">
				{job.source_url && isSafeUrl(job.source_url) && (
					<Button
						variant="outline"
						size="sm"
						asChild
						data-testid="view-original-link"
					>
						<a href={job.source_url} target="_blank" rel="noopener noreferrer">
							<ExternalLink className="mr-1 h-4 w-4" />
							View Original
						</a>
					</Button>
				)}
				{job.apply_url && isSafeUrl(job.apply_url) && (
					<Button variant="outline" size="sm" asChild data-testid="apply-link">
						<a href={job.apply_url} target="_blank" rel="noopener noreferrer">
							<ExternalLink className="mr-1 h-4 w-4" />
							Apply
						</a>
					</Button>
				)}
			</div>

			{/* Ghost risk section */}
			{hasGhostRisk && ghostTier && (
				<div
					data-testid="ghost-risk-section"
					className="space-y-3 rounded-lg border p-4"
				>
					<div className="flex items-center gap-2">
						<TriangleAlert className={cn("h-5 w-5", ghostTier.colorClass)} />
						<span className="font-medium">
							Ghost Risk: {job.ghost_score} ({ghostTier.tier})
						</span>
					</div>

					{job.ghost_signals && (
						<div
							data-testid="ghost-signals"
							className="text-muted-foreground space-y-1 text-sm"
						>
							<p>
								Open {job.ghost_signals.days_open} days
								{DOT_SEPARATOR}
								Reposted {formatRepostCount(job.ghost_signals.repost_count)}
							</p>
							{job.ghost_signals.missing_fields.length > 0 && (
								<p>
									Missing fields: {job.ghost_signals.missing_fields.join(", ")}
								</p>
							)}
						</div>
					)}

					{/* Repost history */}
					{hasRepostHistory && (
						<div
							data-testid="repost-history"
							className="space-y-1 border-t pt-3"
						>
							<div className="flex items-center gap-1 text-sm font-medium">
								<RefreshCw className="h-4 w-4" />
								Repost History
							</div>
							<p className="text-muted-foreground text-sm">
								{formatPreviousPostings(job.repost_count)} detected.
							</p>
						</div>
					)}
				</div>
			)}
		</div>
	);
}

export { JobDetailHeader };
export type { JobDetailHeaderProps };
