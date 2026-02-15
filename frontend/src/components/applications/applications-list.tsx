"use client";

/**
 * Dedicated applications list page component.
 *
 * REQ-012 §11.1: Full application tracking table with all statuses,
 * toolbar (search, filter, sort, show archived, select mode),
 * multi-select with bulk archive, and row click navigation.
 */

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type {
	ColumnDef,
	RowSelectionState,
	SortingState,
} from "@tanstack/react-table";
import { Loader2 } from "lucide-react";

import { apiGet, apiPost } from "@/lib/api-client";
import { formatDateTimeAgo } from "@/lib/job-formatters";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { DataTable } from "@/components/data-table/data-table";
import { DataTableColumnHeader } from "@/components/data-table/data-table-column-header";
import { getSelectColumn } from "@/components/data-table/data-table-select-column";
import { DataTableToolbar } from "@/components/data-table/data-table-toolbar";
import { StatusBadge } from "@/components/ui/status-badge";
import { FailedState } from "@/components/ui/error-states";
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
import type { Application } from "@/types/application";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_FILTER_ALL = "all";
const ALL_STATUSES = "Applied,Interviewing,Offer,Accepted,Rejected,Withdrawn";

const STATUS_OPTIONS = [
	{ value: STATUS_FILTER_ALL, label: "All" },
	{ value: "Applied", label: "Applied" },
	{ value: "Interviewing", label: "Interviewing" },
	{ value: "Offer", label: "Offer" },
	{ value: "Accepted", label: "Accepted" },
	{ value: "Rejected", label: "Rejected" },
	{ value: "Withdrawn", label: "Withdrawn" },
] as const;

const SORT_OPTIONS = [
	{ value: "status_updated_at", label: "Last Updated" },
	{ value: "applied_at", label: "Applied" },
	{ value: "job_title", label: "Job Title" },
] as const;

const DEFAULT_SORT_FIELD = "status_updated_at";
const EMPTY_MESSAGE = "No applications yet.";
const BULK_ACTION_ERROR = "Bulk archive failed.";
const EM_DASH = "\u2014";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ApplicationsList() {
	const router = useRouter();
	const queryClient = useQueryClient();

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	const [sorting, setSorting] = useState<SortingState>([
		{ id: DEFAULT_SORT_FIELD, desc: true },
	]);
	const [sortField, setSortField] = useState(DEFAULT_SORT_FIELD);
	const [statusFilter, setStatusFilter] = useState(STATUS_FILTER_ALL);
	const [showArchived, setShowArchived] = useState(false);
	const [selectMode, setSelectMode] = useState(false);
	const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
	const [bulkActionInProgress, setBulkActionInProgress] = useState(false);

	// -----------------------------------------------------------------------
	// Query params & data fetching
	// -----------------------------------------------------------------------

	const queryParams = useMemo(() => {
		const params: Record<string, string | number | boolean> = {
			status: statusFilter === STATUS_FILTER_ALL ? ALL_STATUSES : statusFilter,
		};
		if (showArchived) {
			params.include_archived = true;
		}
		return params;
	}, [statusFilter, showArchived]);

	const { data, isLoading, error, refetch } = useQuery({
		queryKey: [...queryKeys.applications, "list", queryParams],
		queryFn: () =>
			apiGet<ApiListResponse<Application>>("/applications", queryParams),
	});

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	const handleRowClick = useCallback(
		(app: Application) => {
			router.push(`/applications/${app.id}`);
		},
		[router],
	);

	const handleSortFieldChange = useCallback((field: string) => {
		setSortField(field);
		const desc = field !== "job_title";
		setSorting([{ id: field, desc }]);
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

	const handleBulkArchive = useCallback(async () => {
		setBulkActionInProgress(true);
		try {
			const res = await apiPost<ApiResponse<BulkActionResult>>(
				"/applications/bulk-archive",
				{ ids: selectedIds },
			);
			const { succeeded, failed } = res.data;
			if (failed.length === 0) {
				const n = succeeded.length;
				showToast.success(
					`${n} ${n === 1 ? "application" : "applications"} archived.`,
				);
			} else if (succeeded.length === 0) {
				showToast.error(BULK_ACTION_ERROR);
			} else {
				showToast.warning(
					`${succeeded.length} archived, ${failed.length} failed.`,
				);
			}
			await queryClient.invalidateQueries({
				queryKey: queryKeys.applications,
			});
			exitSelectMode();
		} catch {
			showToast.error(BULK_ACTION_ERROR);
		} finally {
			setBulkActionInProgress(false);
		}
	}, [selectedIds, queryClient, exitSelectMode]);

	// -----------------------------------------------------------------------
	// Columns
	// -----------------------------------------------------------------------

	const columns = useMemo<ColumnDef<Application, unknown>[]>(
		() => [
			...(selectMode ? [getSelectColumn<Application>()] : []),
			{
				id: "job_title",
				accessorFn: (row) =>
					`${row.job_snapshot.title} ${row.job_snapshot.company_name}`,
				header: ({ column }) => (
					<DataTableColumnHeader column={column} title="Job Title" />
				),
				cell: ({ row }) => (
					<div>
						<div className="font-medium">{row.original.job_snapshot.title}</div>
						<div className="text-muted-foreground text-sm">
							{row.original.job_snapshot.company_name}
						</div>
					</div>
				),
				enableSorting: false,
			},
			{
				accessorKey: "status",
				header: ({ column }) => (
					<DataTableColumnHeader column={column} title="Status" />
				),
				cell: ({ row }) => <StatusBadge status={row.original.status} />,
				enableSorting: false,
			},
			{
				id: "interview_stage",
				accessorFn: (row) => row.current_interview_stage,
				header: ({ column }) => (
					<DataTableColumnHeader column={column} title="Interview Stage" />
				),
				cell: ({ row }) => {
					const stage = row.original.current_interview_stage;
					if (stage) {
						return (
							<span className="bg-warning/20 text-warning-foreground inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium">
								{stage}
							</span>
						);
					}
					return EM_DASH;
				},
				enableSorting: false,
			},
			{
				accessorKey: "applied_at",
				header: ({ column }) => (
					<DataTableColumnHeader column={column} title="Applied" />
				),
				cell: ({ row }) => formatDateTimeAgo(row.original.applied_at),
			},
			{
				accessorKey: "status_updated_at",
				header: ({ column }) => (
					<DataTableColumnHeader column={column} title="Last Updated" />
				),
				cell: ({ row }) => formatDateTimeAgo(row.original.status_updated_at),
			},
		],
		[selectMode],
	);

	// -----------------------------------------------------------------------
	// Loading / Error
	// -----------------------------------------------------------------------

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

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	const applications = data?.data ?? [];

	return (
		<div data-testid="applications-list">
			<h1 className="mb-6 text-2xl font-semibold">Applications</h1>

			<DataTable
				columns={columns}
				data={applications}
				onRowClick={selectMode ? undefined : handleRowClick}
				getRowId={(app) => app.id}
				emptyMessage={EMPTY_MESSAGE}
				sorting={sorting}
				onSortingChange={setSorting}
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
								data-testid="bulk-archive-button"
								variant="outline"
								size="sm"
								disabled={selectedCount === 0 || bulkActionInProgress}
								onClick={handleBulkArchive}
							>
								Bulk Archive
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
						<DataTableToolbar
							table={table}
							searchPlaceholder="Search applications..."
						>
							<Select value={statusFilter} onValueChange={setStatusFilter}>
								<SelectTrigger aria-label="Status filter" size="sm">
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									{STATUS_OPTIONS.map((opt) => (
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
									id="show-archived"
									checked={showArchived}
									onCheckedChange={(v) => setShowArchived(!!v)}
									aria-label="Show archived"
								/>
								<span className="text-sm whitespace-nowrap">Show archived</span>
							</div>
						</DataTableToolbar>
					)
				}
			/>
		</div>
	);
}
