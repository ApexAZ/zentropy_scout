"use client";

/**
 * Opportunities tab content — job table with scoring and favorites.
 *
 * REQ-012 §8.2: Table/list view with favorite, title, location,
 * salary, fit, stretch, ghost, and discovered columns.
 * Toolbar: search, status filter, min-fit filter, sort dropdown.
 * Multi-select mode with bulk dismiss/favorite (REQ-006 §2.6).
 * Default sort: fit score descending, favorites pinned to top.
 * REQ-012 §8.5: "Show filtered jobs" toggle — dimmed rows,
 * Filtered badge, expandable failure reasons.
 * REQ-012 §8.6: Ghost detection — severity-based icon and tooltip.
 */

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type {
	ColumnDef,
	RowSelectionState,
	SortingState,
} from "@tanstack/react-table";
import { ChevronDown, Heart, Loader2, TriangleAlert } from "lucide-react";

import { apiGet, apiPatch, apiPost } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { cn } from "@/lib/utils";
import { DataTable } from "@/components/data-table/data-table";
import { DataTableColumnHeader } from "@/components/data-table/data-table-column-header";
import { getSelectColumn } from "@/components/data-table/data-table-select-column";
import { DataTableToolbar } from "@/components/data-table/data-table-toolbar";
import { StatusBadge } from "@/components/ui/status-badge";
import { ScoreTierBadge } from "@/components/ui/score-tier-badge";
import { FailedState } from "@/components/ui/error-states";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import type {
	ApiListResponse,
	ApiResponse,
	BulkActionResult,
} from "@/types/api";
import type {
	FailedNonNegotiable,
	JobPosting,
	JobPostingStatus,
} from "@/types/job";
import { JOB_POSTING_STATUSES } from "@/types/job";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const GHOST_TIER_CONFIG = [
	{
		minScore: 76,
		colorClass: "text-red-500",
		ariaLabel: "High ghost risk",
		tooltip: "High ghost risk \u2014 likely stale or fake",
	},
	{
		minScore: 51,
		colorClass: "text-orange-500",
		ariaLabel: "Elevated ghost risk",
		tooltip: "Elevated ghost risk \u2014 verify before applying",
	},
	{
		minScore: 26,
		colorClass: "text-amber-500",
		ariaLabel: "Moderate ghost risk",
		tooltip: "Moderate ghost risk \u2014 posting may be stale",
	},
] as const;

function getGhostTierConfig(score: number) {
	return GHOST_TIER_CONFIG.find((tier) => score >= tier.minScore) ?? null;
}

const EMPTY_MESSAGE = "No opportunities found.";
const FAVORITE_ERROR_MESSAGE = "Failed to update favorite.";
const BULK_ACTION_ERROR = "Bulk action failed.";
const LOCATION_SEPARATOR = " \u00b7 ";
const DEFAULT_STATUS: JobPostingStatus = "Discovered";
const DEFAULT_SORT_FIELD = "fit_score";

const FAVORITE_PINNED_SORT = { id: "is_favorite", desc: true } as const;

const DEFAULT_SORTING: SortingState = [
	FAVORITE_PINNED_SORT,
	{ id: "fit_score", desc: true },
];

const MIN_FIT_OPTIONS = [
	{ value: "0", label: "Any" },
	{ value: "25", label: "25+" },
	{ value: "50", label: "50+" },
	{ value: "60", label: "60+" },
	{ value: "70", label: "70+" },
	{ value: "80", label: "80+" },
	{ value: "90", label: "90+" },
] as const;

const SORT_OPTIONS = [
	{ value: "fit_score", label: "Fit" },
	{ value: "stretch_score", label: "Stretch" },
	{ value: "salary_min", label: "Salary" },
	{ value: "job_title", label: "Title" },
	{ value: "first_seen_date", label: "Discovered" },
] as const;

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

const FILTER_LABELS: Record<string, string> = {
	salary_min: "Salary",
	salary_max: "Salary",
	work_model: "Work model",
	location: "Location",
	seniority_level: "Seniority",
};

function formatFilterLabel(filter: string): string {
	return (
		FILTER_LABELS[filter] ??
		filter.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase())
	);
}

function formatFailureReason(f: FailedNonNegotiable): {
	text: string;
	isWarning: boolean;
} {
	const label = formatFilterLabel(f.filter);
	if (f.job_value === null) {
		return { text: `${label} not disclosed`, isWarning: true };
	}
	if (f.filter === "salary_min" || f.filter === "salary_max") {
		const fmtVal = (v: string | number) =>
			typeof v === "number" ? `$${Math.round(v / 1000)}k` : v;
		const personaFmt =
			f.persona_value !== null ? fmtVal(f.persona_value) : "N/A";
		return {
			text: `${label} below minimum (${fmtVal(f.job_value)} < ${personaFmt})`,
			isWarning: false,
		};
	}
	return {
		text: `${label}: ${f.job_value} \u2014 your preference: ${f.persona_value}`,
		isWarning: false,
	};
}

function isFilteredJob(job: JobPosting): boolean {
	return (
		job.failed_non_negotiables !== null && job.failed_non_negotiables.length > 0
	);
}

// ---------------------------------------------------------------------------
// Sub-component: Filtered job info (badge + expandable reasons)
// ---------------------------------------------------------------------------

function FilteredJobInfo({ job }: { job: JobPosting }) {
	const [expanded, setExpanded] = useState(false);

	if (!job.failed_non_negotiables?.length) return null;

	return (
		<div className="mt-1">
			<button
				type="button"
				data-testid={`expand-reasons-${job.id}`}
				className="inline-flex items-center gap-1"
				onClick={(e) => {
					e.stopPropagation();
					setExpanded(!expanded);
				}}
			>
				<StatusBadge status="Filtered" />
				<ChevronDown
					className={cn(
						"h-3 w-3 transition-transform",
						expanded && "rotate-180",
					)}
				/>
			</button>
			{expanded && (
				<ul
					data-testid={`failure-reasons-${job.id}`}
					className="mt-1 space-y-0.5 text-xs"
				>
					{job.failed_non_negotiables.map((f) => {
						const { text, isWarning } = formatFailureReason(f);
						return (
							<li
								key={f.filter}
								className={isWarning ? "text-amber-500" : "text-destructive"}
							>
								{text}
							</li>
						);
					})}
				</ul>
			)}
		</div>
	);
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
	const [statusFilter, setStatusFilter] =
		useState<JobPostingStatus>(DEFAULT_STATUS);
	const [minFit, setMinFit] = useState(0);
	const [sortField, setSortField] = useState(DEFAULT_SORT_FIELD);
	const [showFiltered, setShowFiltered] = useState(false);
	const [selectMode, setSelectMode] = useState(false);
	const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
	const [bulkActionInProgress, setBulkActionInProgress] = useState(false);

	const queryParams = useMemo(() => {
		const params: Record<string, string | number> = {
			status: statusFilter,
		};
		if (minFit > 0) params.fit_score_min = minFit;
		return params;
	}, [statusFilter, minFit]);

	const { data, isLoading, error, refetch } = useQuery({
		queryKey: [...queryKeys.jobs, queryParams],
		queryFn: () =>
			apiGet<ApiListResponse<JobPosting>>("/job-postings", queryParams),
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

	const handleSortFieldChange = useCallback((field: string) => {
		setSortField(field);
		const desc = field !== "job_title";
		setSorting([FAVORITE_PINNED_SORT, { id: field, desc }]);
	}, []);

	const selectedIds = useMemo(
		() => Object.keys(rowSelection).filter((id) => rowSelection[id]),
		[rowSelection],
	);
	const selectedCount = selectedIds.length;

	const exitSelectMode = useCallback(() => {
		setSelectMode(false);
		setRowSelection({});
	}, []);

	const handleBulkDismiss = useCallback(async () => {
		setBulkActionInProgress(true);
		try {
			const res = await apiPost<ApiResponse<BulkActionResult>>(
				"/job-postings/bulk-dismiss",
				{ ids: selectedIds },
			);
			const { succeeded, failed } = res.data;
			if (failed.length === 0) {
				const n = succeeded.length;
				showToast.success(`${n} ${n === 1 ? "job" : "jobs"} dismissed.`);
			} else if (succeeded.length === 0) {
				showToast.error(BULK_ACTION_ERROR);
			} else {
				showToast.warning(
					`${succeeded.length} dismissed, ${failed.length} failed.`,
				);
			}
			await queryClient.invalidateQueries({ queryKey: queryKeys.jobs });
			exitSelectMode();
		} catch {
			showToast.error(BULK_ACTION_ERROR);
		} finally {
			setBulkActionInProgress(false);
		}
	}, [selectedIds, queryClient, exitSelectMode]);

	const handleBulkFavorite = useCallback(async () => {
		setBulkActionInProgress(true);
		try {
			const res = await apiPost<ApiResponse<BulkActionResult>>(
				"/job-postings/bulk-favorite",
				{ ids: selectedIds, is_favorite: true },
			);
			const { succeeded, failed } = res.data;
			if (failed.length === 0) {
				const n = succeeded.length;
				showToast.success(`${n} ${n === 1 ? "job" : "jobs"} favorited.`);
			} else if (succeeded.length === 0) {
				showToast.error(BULK_ACTION_ERROR);
			} else {
				showToast.warning(
					`${succeeded.length} favorited, ${failed.length} failed.`,
				);
			}
			await queryClient.invalidateQueries({ queryKey: queryKeys.jobs });
			exitSelectMode();
		} catch {
			showToast.error(BULK_ACTION_ERROR);
		} finally {
			setBulkActionInProgress(false);
		}
	}, [selectedIds, queryClient, exitSelectMode]);

	const columns = useMemo<ColumnDef<JobPosting, unknown>[]>(
		() => [
			...(selectMode ? [getSelectColumn<JobPosting>()] : []),
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
						<FilteredJobInfo job={row.original} />
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
					const tier = getGhostTierConfig(job.ghost_score);
					if (!tier) return null;
					return (
						<TooltipProvider>
							<Tooltip>
								<TooltipTrigger asChild>
									<TriangleAlert
										data-testid={`ghost-warning-${job.id}`}
										className={cn("h-4 w-4", tier.colorClass)}
										aria-label={tier.ariaLabel}
									/>
								</TooltipTrigger>
								<TooltipContent>{tier.tooltip}</TooltipContent>
							</Tooltip>
						</TooltipProvider>
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
		[selectMode, togglingFavoriteId, handleFavoriteToggle],
	);

	const getRowClassName = useCallback(
		(job: JobPosting) => (isFilteredJob(job) ? "opacity-50" : undefined),
		[],
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

	const allJobs = data?.data ?? [];
	const jobs = showFiltered
		? allJobs
		: allJobs.filter((j) => !isFilteredJob(j));

	return (
		<div data-testid="opportunities-table">
			<DataTable
				columns={columns}
				data={jobs}
				onRowClick={selectMode ? undefined : handleRowClick}
				getRowId={(job) => job.id}
				emptyMessage={EMPTY_MESSAGE}
				sorting={sorting}
				onSortingChange={setSorting}
				getRowClassName={getRowClassName}
				enableRowSelection={selectMode}
				rowSelection={rowSelection}
				onRowSelectionChange={setRowSelection}
				toolbar={(table) =>
					selectMode ? (
						<div
							data-testid="selection-action-bar"
							className="flex items-center gap-2"
						>
							<span
								data-testid="selected-count"
								className="text-sm font-medium"
							>
								{selectedCount} selected
							</span>
							<Button
								data-testid="bulk-dismiss-button"
								variant="outline"
								size="sm"
								disabled={selectedCount === 0 || bulkActionInProgress}
								onClick={handleBulkDismiss}
							>
								Bulk Dismiss
							</Button>
							<Button
								data-testid="bulk-favorite-button"
								variant="outline"
								size="sm"
								disabled={selectedCount === 0 || bulkActionInProgress}
								onClick={handleBulkFavorite}
							>
								Bulk Favorite
							</Button>
							<Button
								data-testid="cancel-select-button"
								variant="ghost"
								size="sm"
								onClick={exitSelectMode}
							>
								Cancel
							</Button>
						</div>
					) : (
						<DataTableToolbar table={table} searchPlaceholder="Search jobs...">
							<Select
								value={statusFilter}
								onValueChange={(v) => setStatusFilter(v as JobPostingStatus)}
							>
								<SelectTrigger aria-label="Status filter" size="sm">
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									{JOB_POSTING_STATUSES.map((s) => (
										<SelectItem key={s} value={s}>
											{s}
										</SelectItem>
									))}
								</SelectContent>
							</Select>

							<Select
								value={String(minFit)}
								onValueChange={(v) => setMinFit(Number(v))}
							>
								<SelectTrigger aria-label="Minimum fit score" size="sm">
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									{MIN_FIT_OPTIONS.map((opt) => (
										<SelectItem key={opt.value} value={opt.value}>
											{opt.label}
										</SelectItem>
									))}
								</SelectContent>
							</Select>

							<Select value={sortField} onValueChange={handleSortFieldChange}>
								<SelectTrigger aria-label="Sort by" size="sm">
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									{SORT_OPTIONS.map((opt) => (
										<SelectItem key={opt.value} value={opt.value}>
											{opt.label}
										</SelectItem>
									))}
								</SelectContent>
							</Select>

							<Button
								data-testid="select-mode-button"
								variant="outline"
								size="sm"
								onClick={() => setSelectMode(true)}
							>
								Select
							</Button>

							<div className="flex items-center gap-1.5">
								<Checkbox
									id="show-filtered"
									checked={showFiltered}
									onCheckedChange={(v) => setShowFiltered(!!v)}
									aria-label="Show filtered jobs"
								/>
								<span className="text-sm whitespace-nowrap">Show filtered</span>
							</div>
						</DataTableToolbar>
					)
				}
			/>
		</div>
	);
}
