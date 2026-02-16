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
import type {
	CellContext,
	ColumnDef,
	HeaderContext,
	SortingState,
	Table as ReactTable,
} from "@tanstack/react-table";
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
// Column renderers (extracted to module scope per S6478)
// ---------------------------------------------------------------------------

function JobTitleHeader({ column }: HeaderContext<Application, unknown>) {
	return <DataTableColumnHeader column={column} title="Job Title" />;
}

function JobTitleCell({ row }: CellContext<Application, unknown>) {
	return (
		<div>
			<div className="font-medium">{row.original.job_snapshot.title}</div>
			<div className="text-muted-foreground text-sm">
				{row.original.job_snapshot.company_name}
			</div>
		</div>
	);
}

function StatusHeader({ column }: HeaderContext<Application, unknown>) {
	return <DataTableColumnHeader column={column} title="Status" />;
}

function StatusCell({ row }: CellContext<Application, unknown>) {
	return <StatusBadge status={row.original.status} />;
}

function InterviewStageHeader({ column }: HeaderContext<Application, unknown>) {
	return <DataTableColumnHeader column={column} title="Interview Stage" />;
}

function InterviewStageCell({ row }: CellContext<Application, unknown>) {
	const stage = row.original.current_interview_stage;
	if (stage) {
		return (
			<span className="bg-warning/20 text-warning-foreground inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium">
				{stage}
			</span>
		);
	}
	return EM_DASH;
}

function AppliedAtHeader({ column }: HeaderContext<Application, unknown>) {
	return <DataTableColumnHeader column={column} title="Applied" />;
}

function LastUpdatedHeader({ column }: HeaderContext<Application, unknown>) {
	return <DataTableColumnHeader column={column} title="Last Updated" />;
}

const APPLICATION_COLUMNS: ColumnDef<Application, unknown>[] = [
	{
		id: "job_title",
		accessorFn: (row) =>
			`${row.job_snapshot.title} ${row.job_snapshot.company_name}`,
		header: JobTitleHeader,
		cell: JobTitleCell,
		enableSorting: false,
	},
	{
		accessorKey: "status",
		header: StatusHeader,
		cell: StatusCell,
		enableSorting: false,
	},
	{
		id: "interview_stage",
		accessorFn: (row) => row.current_interview_stage,
		header: InterviewStageHeader,
		cell: InterviewStageCell,
		enableSorting: false,
	},
	{
		accessorKey: "applied_at",
		header: AppliedAtHeader,
		cell: ({ row }) => formatDateTimeAgo(row.original.applied_at),
	},
	{
		accessorKey: "status_updated_at",
		header: LastUpdatedHeader,
		cell: ({ row }) => formatDateTimeAgo(row.original.status_updated_at),
	},
];

// ---------------------------------------------------------------------------
// Toolbar (extracted to module scope per S6478)
// ---------------------------------------------------------------------------

interface ApplicationsTableToolbarProps {
	table: ReactTable<Application>;
	statusFilter: string;
	onStatusFilterChange: (value: string) => void;
	statusOptions: readonly { readonly value: string; readonly label: string }[];
	sortField: string;
	onSortFieldChange: (field: string) => void;
	isHistory: boolean;
	showArchived: boolean;
	onShowArchivedChange: (value: boolean) => void;
}

function ApplicationsTableToolbar({
	table,
	statusFilter,
	onStatusFilterChange,
	statusOptions,
	sortField,
	onSortFieldChange,
	isHistory,
	showArchived,
	onShowArchivedChange,
}: Readonly<ApplicationsTableToolbarProps>) {
	return (
		<DataTableToolbar table={table} searchPlaceholder="Search applications...">
			<Select value={statusFilter} onValueChange={onStatusFilterChange}>
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

			<Select value={sortField} onValueChange={onSortFieldChange}>
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
						onCheckedChange={(v) => onShowArchivedChange(!!v)}
						aria-label="Show archived"
					/>
					<span className="text-sm whitespace-nowrap">Show archived</span>
				</div>
			)}
		</DataTableToolbar>
	);
}

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

	const renderToolbar = useCallback(
		(table: ReactTable<Application>) => (
			<ApplicationsTableToolbar
				table={table}
				statusFilter={statusFilter}
				onStatusFilterChange={setStatusFilter}
				statusOptions={statusOptions}
				sortField={sortField}
				onSortFieldChange={handleSortFieldChange}
				isHistory={isHistory}
				showArchived={showArchived}
				onShowArchivedChange={setShowArchived}
			/>
		),
		[
			statusFilter,
			statusOptions,
			sortField,
			handleSortFieldChange,
			isHistory,
			showArchived,
		],
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
				columns={APPLICATION_COLUMNS}
				data={applications}
				onRowClick={handleRowClick}
				getRowId={(app) => app.id}
				emptyMessage={EMPTY_MESSAGE}
				sorting={sorting}
				onSortingChange={setSorting}
				toolbar={renderToolbar}
			/>
		</div>
	);
}
