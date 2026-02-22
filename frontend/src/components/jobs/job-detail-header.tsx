"use client";

/**
 * Job detail page header with metadata, ghost detection breakdown,
 * and repost history.
 *
 * REQ-012 §8.3: Job detail page header section.
 * REQ-003 §7: Ghost detection signals display.
 * REQ-015 §8.2: Privacy — also_found_on excluded from UI.
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
import { formatDateTimeAgo, formatSalary } from "@/lib/job-formatters";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { isSafeUrl } from "@/lib/url-utils";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { FailedState, NotFoundState } from "@/components/ui/error-states";
import { StatusBadge } from "@/components/ui/status-badge";
import type { ApiResponse } from "@/types/api";
import type { GhostScoreTier, PersonaJobResponse } from "@/types/job";

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

function JobDetailHeader({ jobId }: Readonly<JobDetailHeaderProps>) {
	const router = useRouter();
	const queryClient = useQueryClient();
	const [togglingFavorite, setTogglingFavorite] = useState(false);

	const { data, isLoading, error, refetch } = useQuery({
		queryKey: queryKeys.job(jobId),
		queryFn: () =>
			apiGet<ApiResponse<PersonaJobResponse>>(`/job-postings/${jobId}`),
	});

	const handleFavoriteToggle = useCallback(async () => {
		if (!data) return;
		const personaJob = data.data;
		setTogglingFavorite(true);
		try {
			await apiPatch(`/job-postings/${personaJob.id}`, {
				is_favorite: !personaJob.is_favorite,
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

	const personaJob = data!.data;
	const posting = personaJob.job;
	const ghostTier = getGhostTier(posting.ghost_score);
	const hasGhostRisk = posting.ghost_score > 0;
	const hasRepostHistory = posting.repost_count > 0;

	// Build metadata parts
	const metadataParts: string[] = [posting.company_name];
	if (posting.location) metadataParts.push(posting.location);
	if (posting.work_model) metadataParts.push(posting.work_model);
	if (posting.seniority_level) metadataParts.push(posting.seniority_level);

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
					<h1 className="text-2xl font-bold">{posting.job_title}</h1>
					<div data-testid="job-status-badge">
						<StatusBadge status={personaJob.status} />
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
							personaJob.is_favorite && "fill-current text-red-500",
						)}
					/>
					{personaJob.is_favorite ? "Unfavorite" : "Favorite"}
				</Button>
			</div>

			{/* Metadata line */}
			<p data-testid="job-metadata" className="text-muted-foreground text-sm">
				{metadataParts.join(DOT_SEPARATOR)}
			</p>

			{/* Salary */}
			<p data-testid="job-salary" className="text-sm font-medium">
				{formatSalary(posting)}
			</p>

			{/* Dates */}
			<p data-testid="job-dates" className="text-muted-foreground text-sm">
				{posting.posted_date && (
					<>
						Posted {formatDateTimeAgo(posting.posted_date)}
						{DOT_SEPARATOR}
					</>
				)}
				Discovered {formatDateTimeAgo(personaJob.discovered_at)}
			</p>

			{/* External links */}
			<div className="flex gap-2">
				{posting.source_url && isSafeUrl(posting.source_url) && (
					<Button
						variant="outline"
						size="sm"
						asChild
						data-testid="view-original-link"
					>
						<a
							href={posting.source_url}
							target="_blank"
							rel="noopener noreferrer"
						>
							<ExternalLink className="mr-1 h-4 w-4" />
							View Original
						</a>
					</Button>
				)}
				{posting.apply_url && isSafeUrl(posting.apply_url) && (
					<Button variant="outline" size="sm" asChild data-testid="apply-link">
						<a
							href={posting.apply_url}
							target="_blank"
							rel="noopener noreferrer"
						>
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
							Ghost Risk: {posting.ghost_score} ({ghostTier.tier})
						</span>
					</div>

					{posting.ghost_signals && (
						<div
							data-testid="ghost-signals"
							className="text-muted-foreground space-y-1 text-sm"
						>
							<p>
								Open {posting.ghost_signals.days_open} days
								{DOT_SEPARATOR}
								Reposted {formatRepostCount(posting.ghost_signals.repost_count)}
							</p>
							{posting.ghost_signals.missing_fields.length > 0 && (
								<p>
									Missing fields:{" "}
									{posting.ghost_signals.missing_fields.join(", ")}
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
								{formatPreviousPostings(posting.repost_count)} detected.
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
