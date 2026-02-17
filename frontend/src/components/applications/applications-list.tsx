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
	Table as ReactTable,
} from "@tanstack/react-table";
import { Loader2 } from "lucide-react";

import { apiGet, apiPost } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { showToast } from "@/lib/toast";
import { APPLICATION_COLUMNS } from "@/components/applications/application-columns";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { DataTable } from "@/components/data-table/data-table";
import { getSelectColumn } from "@/components/data-table/data-table-select-column";
import { DataTableToolbar } from "@/components/data-table/data-table-toolbar";
import { ToolbarSelect } from "@/components/data-table/toolbar-select";
import { FailedState } from "@/components/ui/error-states";
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

// ---------------------------------------------------------------------------
// Toolbars (extracted to module scope per S6478)
// ---------------------------------------------------------------------------

interface SelectionActionBarProps {
	selectedCount: number;
	bulkActionInProgress: boolean;
	onBulkArchive: () => void;
	onCancel: () => void;
}

function SelectionActionBar({
	selectedCount,
	bulkActionInProgress,
	onBulkArchive,
	onCancel,
}: Readonly<SelectionActionBarProps>) {
	return (
		<div data-testid="selection-action-bar" className="flex items-center gap-2">
			<span data-testid="selected-count" className="text-sm font-medium">
				{selectedCount} selected
			</span>
			<Button
				data-testid="bulk-archive-button"
				variant="outline"
				size="sm"
				disabled={selectedCount === 0 || bulkActionInProgress}
				onClick={onBulkArchive}
			>
				Bulk Archive
			</Button>
			<Button
				data-testid="cancel-select-button"
				variant="ghost"
				size="sm"
				onClick={onCancel}
			>
				Cancel
			</Button>
		</div>
	);
}

interface ApplicationsListToolbarProps {
	table: ReactTable<Application>;
	statusFilter: string;
	onStatusFilterChange: (value: string) => void;
	sortField: string;
	onSortFieldChange: (field: string) => void;
	showArchived: boolean;
	onShowArchivedChange: (value: boolean) => void;
	onSelectMode: () => void;
}

function ApplicationsListToolbar({
	table,
	statusFilter,
	onStatusFilterChange,
	sortField,
	onSortFieldChange,
	showArchived,
	onShowArchivedChange,
	onSelectMode,
}: Readonly<ApplicationsListToolbarProps>) {
	return (
		<DataTableToolbar table={table} searchPlaceholder="Search applications...">
			<ToolbarSelect
				value={statusFilter}
				onValueChange={onStatusFilterChange}
				label="Status filter"
				options={STATUS_OPTIONS}
			/>

			<ToolbarSelect
				value={sortField}
				onValueChange={onSortFieldChange}
				label="Sort by"
				options={SORT_OPTIONS}
			/>

			<Button
				data-testid="select-mode-button"
				variant="outline"
				size="sm"
				onClick={onSelectMode}
			>
				Select
			</Button>

			<div className="flex items-center gap-1.5">
				<Checkbox
					id="show-archived"
					checked={showArchived}
					onCheckedChange={(v) => onShowArchivedChange(!!v)}
					aria-label="Show archived"
				/>
				<span className="text-sm whitespace-nowrap">Show archived</span>
			</div>
		</DataTableToolbar>
	);
}

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

	const renderToolbar = useCallback(
		(table: ReactTable<Application>) =>
			selectMode ? (
				<SelectionActionBar
					selectedCount={selectedCount}
					bulkActionInProgress={bulkActionInProgress}
					onBulkArchive={handleBulkArchive}
					onCancel={exitSelectMode}
				/>
			) : (
				<ApplicationsListToolbar
					table={table}
					statusFilter={statusFilter}
					onStatusFilterChange={setStatusFilter}
					sortField={sortField}
					onSortFieldChange={handleSortFieldChange}
					showArchived={showArchived}
					onShowArchivedChange={setShowArchived}
					onSelectMode={() => setSelectMode(true)}
				/>
			),
		[
			selectMode,
			selectedCount,
			bulkActionInProgress,
			handleBulkArchive,
			exitSelectMode,
			statusFilter,
			sortField,
			handleSortFieldChange,
			showArchived,
		],
	);

	// -----------------------------------------------------------------------
	// Columns
	// -----------------------------------------------------------------------

	const columns = useMemo<ColumnDef<Application, unknown>[]>(
		() => [
			...(selectMode ? [getSelectColumn<Application>()] : []),
			...APPLICATION_COLUMNS,
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
				toolbar={renderToolbar}
			/>
		</div>
	);
}
