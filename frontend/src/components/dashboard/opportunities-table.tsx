"use client";

/**
 * Opportunities tab content — job table with scoring and favorites.
 *
 * REQ-012 §8.2: Table/list view with favorite, title, location,
 * salary, fit, stretch, ghost, and discovered columns.
 * Default sort: fit score descending, favorites pinned to top.
 */

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef, SortingState } from "@tanstack/react-table";
import { Heart, Loader2, TriangleAlert } from "lucide-react";

import { apiGet, apiPatch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { cn } from "@/lib/utils";
import { DataTable } from "@/components/data-table/data-table";
import { DataTableColumnHeader } from "@/components/data-table/data-table-column-header";
import { ScoreTierBadge } from "@/components/ui/score-tier-badge";
import { FailedState } from "@/components/ui/error-states";
import { Button } from "@/components/ui/button";
import type { ApiListResponse } from "@/types/api";
import type { JobPosting } from "@/types/job";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const GHOST_WARNING_THRESHOLD = 50;
const EMPTY_MESSAGE = "No opportunities found.";
const FAVORITE_ERROR_MESSAGE = "Failed to update favorite.";
const LOCATION_SEPARATOR = " \u00b7 ";

const DEFAULT_SORTING: SortingState = [
	{ id: "is_favorite", desc: true },
	{ id: "fit_score", desc: true },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatSalary(job: JobPosting): string {
	if (job.salary_min === null && job.salary_max === null)
		return "Not disclosed";
	const currency = job.salary_currency ?? "USD";
	const fmt = (n: number) => `$${Math.round(n / 1000)}k`;
	if (job.salary_min !== null && job.salary_max !== null) {
		return `${fmt(job.salary_min)}\u2013${fmt(job.salary_max)} ${currency}`;
	}
	if (job.salary_min !== null) return `${fmt(job.salary_min)}+ ${currency}`;
	return `Up to ${fmt(job.salary_max!)} ${currency}`;
}

function formatDaysAgo(dateString: string): string {
	const [year, month, day] = dateString.split("-").map(Number);
	const jobDate = new Date(year, month - 1, day);
	const now = new Date();
	const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
	const diffMs = today.getTime() - jobDate.getTime();
	const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
	if (days === 0) return "Today";
	if (days === 1) return "1 day ago";
	return `${days} days ago`;
}

function formatLocation(job: JobPosting): string {
	const parts: string[] = [];
	if (job.location) parts.push(job.location);
	if (job.work_model) parts.push(job.work_model);
	return parts.join(LOCATION_SEPARATOR) || "\u2014";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function OpportunitiesTable() {
	const router = useRouter();
	const queryClient = useQueryClient();
	const [togglingFavoriteId, setTogglingFavoriteId] = useState<string | null>(
		null,
	);
	const [sorting, setSorting] = useState<SortingState>(DEFAULT_SORTING);

	const { data, isLoading, error, refetch } = useQuery({
		queryKey: queryKeys.jobs,
		queryFn: () =>
			apiGet<ApiListResponse<JobPosting>>("/job-postings", {
				status: "Discovered",
			}),
	});

	const handleFavoriteToggle = useCallback(
		async (job: JobPosting) => {
			setTogglingFavoriteId(job.id);
			try {
				await apiPatch(`/job-postings/${job.id}`, {
					is_favorite: !job.is_favorite,
				});
				await queryClient.invalidateQueries({ queryKey: queryKeys.jobs });
			} catch {
				showToast.error(FAVORITE_ERROR_MESSAGE);
			} finally {
				setTogglingFavoriteId(null);
			}
		},
		[queryClient],
	);

	const handleRowClick = useCallback(
		(job: JobPosting) => {
			router.push(`/jobs/${job.id}`);
		},
		[router],
	);

	const columns = useMemo<ColumnDef<JobPosting, unknown>[]>(
		() => [
			{
				accessorKey: "is_favorite",
				header: ({ column }) => (
					<DataTableColumnHeader column={column} title="Favorite" />
				),
				cell: ({ row }) => {
					const job = row.original;
					const isToggling = togglingFavoriteId === job.id;
					return (
						<Button
							variant="ghost"
							size="icon"
							data-testid={`favorite-toggle-${job.id}`}
							disabled={isToggling}
							aria-label={job.is_favorite ? "Unfavorite" : "Favorite"}
							onClick={(e) => {
								e.stopPropagation();
								handleFavoriteToggle(job);
							}}
						>
							<Heart
								className={cn(
									"h-4 w-4",
									job.is_favorite && "fill-current text-red-500",
								)}
							/>
						</Button>
					);
				},
			},
			{
				accessorKey: "job_title",
				header: ({ column }) => (
					<DataTableColumnHeader column={column} title="Job Title" />
				),
				cell: ({ row }) => (
					<div>
						<div className="font-medium">{row.original.job_title}</div>
						<div className="text-muted-foreground text-sm">
							{row.original.company_name}
						</div>
					</div>
				),
			},
			{
				id: "location",
				accessorFn: (row) => row.location,
				header: ({ column }) => (
					<DataTableColumnHeader column={column} title="Location" />
				),
				cell: ({ row }) => formatLocation(row.original),
				enableSorting: false,
			},
			{
				id: "salary",
				accessorFn: (row) => row.salary_min,
				header: ({ column }) => (
					<DataTableColumnHeader column={column} title="Salary" />
				),
				cell: ({ row }) => formatSalary(row.original),
			},
			{
				accessorKey: "fit_score",
				header: ({ column }) => (
					<DataTableColumnHeader column={column} title="Fit" />
				),
				cell: ({ row }) => (
					<ScoreTierBadge score={row.original.fit_score} scoreType="fit" />
				),
			},
			{
				accessorKey: "stretch_score",
				header: ({ column }) => (
					<DataTableColumnHeader column={column} title="Stretch" />
				),
				cell: ({ row }) => (
					<ScoreTierBadge
						score={row.original.stretch_score}
						scoreType="stretch"
					/>
				),
			},
			{
				accessorKey: "ghost_score",
				header: ({ column }) => (
					<DataTableColumnHeader column={column} title="Ghost" />
				),
				cell: ({ row }) => {
					const job = row.original;
					if (job.ghost_score < GHOST_WARNING_THRESHOLD) return null;
					return (
						<TriangleAlert
							data-testid={`ghost-warning-${job.id}`}
							className="h-4 w-4 text-amber-500"
							aria-label="Ghost risk warning"
						/>
					);
				},
				enableSorting: false,
			},
			{
				accessorKey: "first_seen_date",
				header: ({ column }) => (
					<DataTableColumnHeader column={column} title="Discovered" />
				),
				cell: ({ row }) => formatDaysAgo(row.original.first_seen_date),
			},
		],
		[togglingFavoriteId, handleFavoriteToggle],
	);

	if (isLoading) {
		return (
			<div data-testid="loading-spinner" className="flex justify-center py-12">
				<Loader2 className="text-muted-foreground h-8 w-8 animate-spin" />
			</div>
		);
	}

	if (error) {
		return <FailedState onRetry={() => refetch()} />;
	}

	const jobs = data?.data ?? [];

	return (
		<div data-testid="opportunities-table">
			<DataTable
				columns={columns}
				data={jobs}
				onRowClick={handleRowClick}
				getRowId={(job) => job.id}
				emptyMessage={EMPTY_MESSAGE}
				sorting={sorting}
				onSortingChange={setSorting}
			/>
		</div>
	);
}
