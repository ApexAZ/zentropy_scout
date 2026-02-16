"use client";

/**
 * Application data table for In Progress and History dashboard tabs.
 *
 * REQ-012 §8.1: In Progress (Applied, Interviewing, Offer) and
 * History (Accepted, Rejected, Withdrawn) tabs share the same table
 * columns but differ in statuses fetched, default sort, and toolbar options.
 */

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import type { ColumnDef, SortingState } from "@tanstack/react-table";
import { Loader2 } from "lucide-react";

import { apiGet } from "@/lib/api-client";
import { formatDateTimeAgo } from "@/lib/job-formatters";
import { queryKeys } from "@/lib/query-keys";
import { DataTable } from "@/components/data-table/data-table";
import { DataTableColumnHeader } from "@/components/data-table/data-table-column-header";
import { DataTableToolbar } from "@/components/data-table/data-table-toolbar";
import { StatusBadge } from "@/components/ui/status-badge";
import { FailedState } from "@/components/ui/error-states";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import type { ApiListResponse } from "@/types/api";
import type { Application } from "@/types/application";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ApplicationsTableProps {
	variant: "in-progress" | "history";
}

// ---------------------------------------------------------------------------
// Variant configuration
// ---------------------------------------------------------------------------

const STATUS_FILTER_ALL = "all";
const IN_PROGRESS_STATUSES = "Applied,Interviewing,Offer";
const HISTORY_STATUSES = "Accepted,Rejected,Withdrawn";

const IN_PROGRESS_STATUS_OPTIONS = [
	{ value: STATUS_FILTER_ALL, label: "All" },
	{ value: "Applied", label: "Applied" },
	{ value: "Interviewing", label: "Interviewing" },
	{ value: "Offer", label: "Offer" },
] as const;

const HISTORY_STATUS_OPTIONS = [
	{ value: STATUS_FILTER_ALL, label: "All" },
	{ value: "Accepted", label: "Accepted" },
	{ value: "Rejected", label: "Rejected" },
	{ value: "Withdrawn", label: "Withdrawn" },
] as const;

const SORT_OPTIONS = [
	{ value: "status_updated_at", label: "Last Updated" },
	{ value: "applied_at", label: "Applied" },
	{ value: "job_title", label: "Job Title" },
] as const;

const EMPTY_MESSAGE = "No applications found.";
const EM_DASH = "\u2014";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ApplicationsTable({
	variant,
}: Readonly<ApplicationsTableProps>) {
	const router = useRouter();

	const isHistory = variant === "history";
	const defaultSortField = isHistory ? "applied_at" : "status_updated_at";
	const statusString = isHistory ? HISTORY_STATUSES : IN_PROGRESS_STATUSES;
	const statusOptions = isHistory
		? HISTORY_STATUS_OPTIONS
		: IN_PROGRESS_STATUS_OPTIONS;

	const [sorting, setSorting] = useState<SortingState>([
		{ id: defaultSortField, desc: true },
	]);
	const [sortField, setSortField] = useState(defaultSortField);
	const [statusFilter, setStatusFilter] = useState(STATUS_FILTER_ALL);
	const [showArchived, setShowArchived] = useState(false);

	const queryParams = useMemo(() => {
		const params: Record<string, string | number | boolean> = {
			status: statusFilter === STATUS_FILTER_ALL ? statusString : statusFilter,
		};
		if (isHistory && showArchived) {
			params.include_archived = true;
		}
		return params;
	}, [statusFilter, statusString, isHistory, showArchived]);

	const { data, isLoading, error, refetch } = useQuery({
		queryKey: [...queryKeys.applications, variant, queryParams],
		queryFn: () =>
			apiGet<ApiListResponse<Application>>("/applications", queryParams),
	});

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

	const columns = useMemo<ColumnDef<Application, unknown>[]>(
		() => [
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

	const applications = data?.data ?? [];

	return (
		<div data-testid="applications-table">
			<DataTable
				columns={columns}
				data={applications}
				onRowClick={handleRowClick}
				getRowId={(app) => app.id}
				emptyMessage={EMPTY_MESSAGE}
				sorting={sorting}
				onSortingChange={setSorting}
				toolbar={(table) => (
					<DataTableToolbar
						table={table}
						searchPlaceholder="Search applications..."
					>
						<Select value={statusFilter} onValueChange={setStatusFilter}>
							<SelectTrigger aria-label="Status filter" size="sm">
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								{statusOptions.map((opt) => (
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

						{isHistory && (
							<div className="flex items-center gap-1.5">
								<Checkbox
									id="show-archived"
									checked={showArchived}
									onCheckedChange={(v) => setShowArchived(!!v)}
									aria-label="Show archived"
								/>
								<span className="text-sm whitespace-nowrap">Show archived</span>
							</div>
						)}
					</DataTableToolbar>
				)}
			/>
		</div>
	);
}
